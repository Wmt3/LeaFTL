#include <vector>
#include <algorithm>
#include <cmath>
#include <chrono>
#include <utility>
#include <iostream>

// Python으로 결과를 전달하기 위한 구조체
struct SegmentResult {
    double k;
    double b;
    long x1;
    long x2;
};

// 시간 측정 결과를 전달하기 위한 구조체
struct TimingResult {
    double total_duration_sec;
    double sorting_duration_sec;
    double training_duration_sec;
};

// C++ 함수가 반환할 모든 결과를 담는 구조체
struct PlrResult {
    SegmentResult* segments;
    int segment_count;
    TimingResult timings;
};

// 내부 계산용 SimpleSegment 구조체
struct SimpleSegment {
    double k = 0.0, b = 0.0;
};

class PLR_Optimizer {
public:
    PLR_Optimizer(double gamma) : gamma_(gamma) {}

    std::vector<SegmentResult> learn(const std::vector<std::pair<long, long>>& points) {
        init();
        if (points.empty()) {
            return segments_;
        }
        
        for (const auto& point : points) {
            process(point);
        }
        
        auto last_seg = build_segment();
        if (last_seg.x2 >= last_seg.x1) {
            segments_.push_back(last_seg);
        }
        return segments_;
    }

private:
    enum State { FIRST, SECOND, READY };

    double gamma_;
    
    State state_;
    std::pair<long, long> s0_, s1_;
    SimpleSegment rho_upper_, rho_lower_;
    std::pair<double, double> sint_;
    std::vector<SegmentResult> segments_;
    std::vector<std::pair<long, long>> current_points_;

    void init() {
        state_ = FIRST;
        segments_.clear();
        current_points_.clear();
    }

    SimpleSegment from_points(std::pair<double, double> p1, std::pair<double, double> p2) {
        if (p2.first == p1.first) return {0.0, 0.0};
        double k = (p2.second - p1.second) / (p2.first - p1.first);
        double b = -k * p1.first + p1.second;
        return {k, b};
    }

    std::pair<double, double> intersection(const SimpleSegment& s1, const SimpleSegment& s2) {
        if (s1.k == s2.k) return {0.0, 0.0};
        double x = (s2.b - s1.b) / (s1.k - s2.k);
        double y = s1.k * x + s1.b;
        return {x, y};
    }

    bool is_above(const std::pair<long, long>& pt, const SimpleSegment& s) {
        return static_cast<double>(pt.second) > s.k * pt.first + s.b;
    }

    bool is_below(const std::pair<long, long>& pt, const SimpleSegment& s) {
        return static_cast<double>(pt.second) < s.k * pt.first + s.b;
    }

    SegmentResult build_segment() {
        if (state_ == FIRST) {
            return {0, 0, 0, -1}; // Invalid
        }
        if (state_ == SECOND) {
            return {1.0, static_cast<double>(s0_.second - s0_.first), s0_.first, s0_.first};
        }
        // state_ == READY
        double avg_slope = (rho_lower_.k + rho_upper_.k) / 2.0;
        double intercept = sint_.second - sint_.first * avg_slope;
        return {avg_slope, intercept, s0_.first, s1_.first};
    }
    void process(const std::pair<long, long>& point) {
        if (state_ == FIRST) {
            s0_ = point;
            state_ = SECOND;
        } else if (state_ == SECOND) {
            s1_ = point;
            rho_upper_ = from_points({(double)s0_.first, (double)s0_.second - gamma_}, {(double)s1_.first, (double)s1_.second + gamma_});
            rho_lower_ = from_points({(double)s0_.first, (double)s0_.second + gamma_}, {(double)s1_.first, (double)s1_.second - gamma_});
            sint_ = intersection(rho_upper_, rho_lower_);
            state_ = READY;
        } else if (state_ == READY) {
            if (is_above(point, rho_lower_) && is_below(point, rho_upper_)) {
                s1_ = point;
                if (is_below({point.first, point.second + (long)gamma_}, rho_upper_)) {
                    rho_upper_ = from_points(sint_, {(double)point.first, (double)point.second + gamma_});
                }
                if (is_above({point.first, point.second - (long)gamma_}, rho_lower_)) {
                    rho_lower_ = from_points(sint_, {(double)point.first, (double)point.second - gamma_});
                }
            } else {
                segments_.push_back(build_segment());
                s0_ = point;
                state_ = SECOND;
            }
        }
        current_points_.push_back(point);
    }
};

extern "C" {
    PlrResult* learn_and_time_segments(long* lpns, long* ppns, int num_points, double gamma) {
        auto total_start = std::chrono::high_resolution_clock::now();

        if (num_points == 0) {
            PlrResult* result = new PlrResult();
            result->segment_count = 0;
            result->segments = nullptr;
            result->timings = {0.0, 0.0, 0.0};
            return result;
        }

        std::vector<std::pair<long, long>> points(num_points);
        for (int i = 0; i < num_points; ++i) {
            points[i] = {lpns[i], ppns[i]};
        }

        auto sort_start = std::chrono::high_resolution_clock::now();
        std::sort(points.begin(), points.end());
        auto sort_end = std::chrono::high_resolution_clock::now();

        auto train_start = std::chrono::high_resolution_clock::now();
        PLR_Optimizer optimizer(gamma);
        std::vector<SegmentResult> learned_segments = optimizer.learn(points);
        auto train_end = std::chrono::high_resolution_clock::now();

        auto total_end = std::chrono::high_resolution_clock::now();

        PlrResult* result = new PlrResult();
        result->segment_count = learned_segments.size();
        if (result->segment_count > 0) {
            result->segments = new SegmentResult[result->segment_count];
            std::copy(learned_segments.begin(), learned_segments.end(), result->segments);
        } else {
            result->segments = nullptr;
        }

        result->timings.sorting_duration_sec = std::chrono::duration<double>(sort_end - sort_start).count();
        result->timings.training_duration_sec = std::chrono::duration<double>(train_end - train_start).count();
        result->timings.total_duration_sec = std::chrono::duration<double>(total_end - total_start).count();

        return result;
    }

    void free_plr_result(PlrResult* result) {
        if (result) {
            delete[] result->segments;
            delete result;
        }
    }
}

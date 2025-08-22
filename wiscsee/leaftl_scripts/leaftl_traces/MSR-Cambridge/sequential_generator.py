import csv
import random
import time

# --- 설정 ---
NUM_RECORDS = 1_500_000  # 생성할 레코드 수
OUTPUT_FILE = 'sequential_write_trace.csv'  # 출력 파일 이름
WRITE_RATIO = 0.7  # 전체 작업 중 쓰기 작업의 비율 (70%)
HOSTNAME = 'usr'
DISK_NUM = 0
# 원본 데이터에서 관찰된 일반적인 I/O 크기 (바이트 단위)
POSSIBLE_SIZES = [512, 1024, 2048, 4096, 8192, 16384, 32768, 40960]

# --- 현실적인 트레이스 생성을 위한 설정 ---
# 한 번의 순차 쓰기 묶음(burst)에 포함될 쓰기 작업의 최소/최대 횟수
MIN_SEQ_LENGTH = 50
MAX_SEQ_LENGTH = 200
# 시뮬레이션할 디스크의 최대 오프셋 (예: 1TB)
MAX_OFFSET = 1 * 1024 * 1024 * 1024 * 1024 # 1TB
# 오프셋 정렬 단위 (일반적으로 페이지 크기인 4KB)
ALIGNMENT = 4096

def generate_realistic_write_response_time(size):
    """쓰기 크기에 따라 현실적인 쓰기 응답 시간을 생성합니다. (범위 확장)"""
    base_time = 0
    jitter = 0
    if size <= 4096: # 작은 쓰기
        base_time = random.randint(20000, 60000)
        jitter = random.randint(0, 30000)
    elif size <= 16384: # 중간 크기 쓰기
        base_time = random.randint(40000, 90000)
        jitter = random.randint(0, 50000)
    else: # 큰 쓰기
        base_time = random.randint(70000, 150000)
        jitter = random.randint(0, 100000)
    return base_time + jitter

def generate_realistic_read_response_time(size):
    """
    읽기 크기에 따라 현실적인 읽기 응답 시간을 생성합니다.
    쓰기 작업보다 확연히 작은 응답 시간을 갖도록 설정합니다.
    """
    base_time = 0
    jitter = 0
    if size <= 4096:
        base_time = random.randint(1000, 3000)
        jitter = random.randint(0, 1500)
    else:
        base_time = random.randint(2500, 5000)
        jitter = random.randint(0, 2000)
    return base_time + jitter


# --- 초기값 설정 ---
current_timestamp = int(time.time() * 1_000_000_000)
written_bursts = []  # 완료된 쓰기 묶음의 (시작, 끝) 오프셋을 저장하는 리스트

# 순차 쓰기 묶음(burst) 관련 변수 초기화
current_seq_count = 0
next_seq_length = random.randint(MIN_SEQ_LENGTH, MAX_SEQ_LENGTH)
# 시작 오프셋을 디스크 내 임의의 정렬된 주소로 설정
current_offset = random.randint(0, MAX_OFFSET // ALIGNMENT) * ALIGNMENT
current_burst_start_offset = current_offset

print(f"'{OUTPUT_FILE}' 파일에 {NUM_RECORDS:,}개의 레코드 생성을 시작합니다...")

with open(OUTPUT_FILE, 'w', newline='') as f:
    writer = csv.writer(f)

    for i in range(NUM_RECORDS):
        # 타임스탬프는 모든 작업에 공통적으로 증가
        timestamp_increment = random.randint(100, 1500)
        current_timestamp += timestamp_increment

        op_type = 'Write'
        # 첫 100개는 쓰기 작업을 보장하고, 이전에 쓰인 데이터가 있을 때만 읽기 시도
        if i > 100 and random.random() > WRITE_RATIO and written_bursts:
            op_type = 'Read'

        if op_type == 'Write':
            # --- 순차 쓰기 묶음 관리 로직 ---
            if current_seq_count >= next_seq_length:
                # 현재까지의 쓰기 묶음 범위를 저장
                written_bursts.append((current_burst_start_offset, current_offset))
                # 1000개가 넘으면 오래된 기록은 일부 삭제 (메모리 관리)
                if len(written_bursts) > 1000:
                    written_bursts.pop(0)

                current_seq_count = 0
                next_seq_length = random.randint(MIN_SEQ_LENGTH, MAX_SEQ_LENGTH)
                current_offset = random.randint(0, MAX_OFFSET // ALIGNMENT) * ALIGNMENT
                current_burst_start_offset = current_offset # 새 묶음의 시작 위치 기록

            size = random.choice(POSSIBLE_SIZES)
            response_time = generate_realistic_write_response_time(size)
            offset = current_offset

            record = [current_timestamp, HOSTNAME, DISK_NUM, op_type, offset, size, response_time]

            # 다음 쓰기를 위해 오프셋과 카운트 업데이트
            current_offset += size
            current_seq_count += 1
        
        else: # op_type == 'Read'
            # 기록된 쓰기 묶음 중 하나를 무작위로 선택
            start_addr, end_addr = random.choice(written_bursts)
            
            size = random.choice(POSSIBLE_SIZES)
            
            # 읽기 작업이 선택된 주소 범위를 벗어나지 않도록 오프셋 계산
            # end_addr가 size보다 작을 수 있는 극단적인 경우 방지
            if start_addr >= end_addr - size:
                offset = start_addr
            else:
                offset = random.randint(start_addr, end_addr - size)
            
            # 읽기 오프셋도 정렬
            offset = (offset // ALIGNMENT) * ALIGNMENT

            response_time = generate_realistic_read_response_time(size)
            record = [current_timestamp, HOSTNAME, DISK_NUM, op_type, offset, size, response_time]

        # 생성된 레코드(읽기 또는 쓰기)를 파일에 씀
        writer.writerow(record)

        if (i + 1) % 100000 == 0:
            print(f"  ... {i + 1:,}개 레코드 생성 완료 (현재 {len(written_bursts)}개 쓰기 묶음 기록 중)")

print(f"성공적으로 '{OUTPUT_FILE}' 파일을 생성했습니다.")

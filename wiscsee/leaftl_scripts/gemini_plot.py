#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt

# 상수 정의
SECTOR_SIZE = 512
GB = 1024.0**3
MSR_TIMESTAMP_UNIT = 100e-9  # 100 nanoseconds
FIU_TIMESTAMP_UNIT = 1e-6    # 1 microsecond

def parse_msr_trace_first_second(filepath):
    """MSR-Cambridge 트레이스 파일(.csv)의 첫 1초 데이터를 파싱합니다."""
    print("Parsing first 1s of MSR trace: {}...".format(os.path.basename(filepath)))
    offsets = []
    start_timestamp = None
    try:
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    parts = line.strip().split(',')
                    timestamp = int(parts[0])
                    
                    if start_timestamp is None:
                        start_timestamp = timestamp
                    
                    # 경과 시간(초) 계산
                    elapsed_seconds = (timestamp - start_timestamp) * MSR_TIMESTAMP_UNIT
                    if elapsed_seconds > 1.0:
                        break # 1초가 지나면 중단

                    offset_bytes = int(parts[4])
                    offsets.append(offset_bytes / GB) # GB 단위로 변환
                except (ValueError, IndexError):
                    continue
    except IOError as e:
        print("Error reading file {}: {}".format(filepath, e))
    return offsets

def parse_fiu_trace_first_second(filepath):
    """FIU 트레이스 파일(.blkparse)의 첫 1초 데이터를 파싱합니다."""
    print("Parsing first 1s of FIU trace: {}...".format(os.path.basename(filepath)))
    lbns = []
    start_timestamp = None
    try:
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    parts = line.strip().split()
                    timestamp = int(parts[0])

                    if start_timestamp is None:
                        start_timestamp = timestamp
                    
                    elapsed_seconds = (timestamp - start_timestamp) * FIU_TIMESTAMP_UNIT
                    if elapsed_seconds > 1.0:
                        break # 1초가 지나면 중단

                    lbn_sectors = int(parts[3])
                    offset_bytes = lbn_sectors * SECTOR_SIZE
                    lbns.append(offset_bytes / GB)
                except (ValueError, IndexError):
                    continue
    except IOError as e:
        print("Error reading file {}: {}".format(filepath, e))
    return lbns

def plot_access_pattern(trace_file, output_file):
    """트레이스 파일을 읽어 첫 1초 접근 패턴 그래프를 생성하고 저장합니다."""
    
    if trace_file.endswith('.csv'):
        offsets_gb = parse_msr_trace_first_second(trace_file)
        y_label = "Offset (GB)"
    elif trace_file.endswith('.blkparse'):
        offsets_gb = parse_fiu_trace_first_second(trace_file)
        y_label = "LBA Address (GB)"
    else:
        return

    if not offsets_gb:
        print("  -> No data points found in the first second. Skipping.")
        return

    print("  -> Plotting {} data points...".format(len(offsets_gb)))
    
    x_axis = range(len(offsets_gb))

    plt.figure(figsize=(12, 6))
    plt.scatter(x_axis, offsets_gb, s=5, alpha=0.6, edgecolors='none')
    
    plt.title('LBA Access Pattern (First 1 Second): {}'.format(os.path.basename(trace_file)))
    plt.xlabel('Request Sequence Number')
    plt.ylabel(y_label)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    plt.savefig(output_file, dpi=200)
    print("  -> Graph saved to: {}".format(output_file))
    plt.close()

if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))

    parser = argparse.ArgumentParser(description="Visualize the first 1 second of LBA access patterns for all MSR and FIU traces.")
    parser.add_argument('--trace_dir', type=str, default=os.path.join(BASE_DIR, 'leaftl_traces'), 
                        help="Directory containing the trace files (default: ./leaftl_traces)")
    parser.add_argument('--output_dir', type=str, default=os.path.join(BASE_DIR, 'plots_first_second'),
                        help="Directory to save the output graphs (default: ./plots_first_second)")
    
    args = parser.parse_args()

    if not os.path.isdir(args.trace_dir):
        print("Error: Trace directory not found at '{}'".format(args.trace_dir))
        sys.exit(1)

    print("Starting trace visualization for the first 1 second...")
    print("Trace Source: {}".format(args.trace_dir))
    print("Output Destination: {}".format(args.output_dir))
    print("-" * 30)

    for root, dirs, files in os.walk(args.trace_dir):
        for filename in files:
            if filename.endswith('.csv') or filename.endswith('.blkparse'):
                trace_filepath = os.path.join(root, filename)
                
                relative_path = os.path.relpath(root, args.trace_dir)
                output_folder = os.path.join(args.output_dir, relative_path)
                
                output_filename = os.path.splitext(filename)[0] + '_first_sec.png'
                output_filepath = os.path.join(output_folder, output_filename)
                
                plot_access_pattern(trace_filepath, output_filepath)
                print("-" * 30)

    print("All tasks completed.")

#!/usr/bin/env python3
"""
False Sharing Analysis - Results Extractor
Extracts key metrics from gem5 stats.txt files.
"""

import os
import sys
import csv
import json
from pathlib import Path
from collections import defaultdict


def parse_stats_file(stats_file):
    """Parse gem5 stats.txt file and extract metrics."""
    metrics = {}
    
    if not os.path.exists(stats_file):
        print(f"ERROR: stats file not found: {stats_file}", file=sys.stderr)
        return metrics
    
    # Check if file is empty
    if os.path.getsize(stats_file) == 0:
        print(f"ERROR: stats file is empty (0 bytes): {stats_file}", file=sys.stderr)
        return metrics
    
    with open(stats_file, 'r') as f:
        line_count = 0
        for line in f:
            line = line.strip()
            if not line or line.startswith('---'):
                continue
            
            # Parse stat lines: "stat_name value"
            if ' ' in line and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2:
                    stat_name = parts[0]
                    try:
                        # Try to parse as float
                        value = float(parts[1])
                        metrics[stat_name] = value
                        line_count += 1
                    except ValueError:
                        # Store as string if not a number
                        metrics[stat_name] = parts[1]
                        line_count += 1
    
    if line_count == 0:
        print(f"WARNING: stats file has no parseable metrics: {stats_file}", file=sys.stderr)
    
    return metrics


def extract_key_metrics(metrics):
    """Extract key metrics for false sharing analysis.
    
    Supports both Ruby (MESI) and classic cache hierarchies.
    Classic cache hierarchy uses board.processor.coresX.core.* stats.
    Ruby uses system.cpuX.* and system.ruby_system.* stats.
    """
    extracted = {}
    
    # Helper function to safely get metric
    def get_metric(key, default=None):
        return metrics.get(key, default)
    
    # Try to determine which cache hierarchy is used by checking for metrics
    is_ruby = 'system.ruby_system.L1Cache_Controller.Inv::total' in metrics
    is_classic = 'board.processor.cores0.core.cpi' in metrics
    
    if is_classic:
        # Classic cache hierarchy - extract from board.processor.coresX.core.*
        extracted['num_cpus'] = 0
        cpu_insts = []
        cpu_cycles = []
        cpu_cpis = []
        
        # Find all cores (cores0, cores1, etc.)
        for i in range(16):
            cpi_key = f'board.processor.cores{i}.core.cpi'
            cycles_key = f'board.processor.cores{i}.core.numCycles'
            
            cpi = get_metric(cpi_key)
            cycles = get_metric(cycles_key)
            
            if cpi is not None and cycles is not None and not (isinstance(cpi, str)):
                extracted['num_cpus'] += 1
                cpu_cpis.append(cpi)
                cpu_cycles.append(cycles)
                # Calculate instructions from CPI: instructions = cycles / CPI
                if cpi > 0:
                    insts = cycles / cpi
                    cpu_insts.append(insts)
        
        if cpu_cpis:
            extracted['total_insts'] = sum(cpu_insts)
            extracted['total_cycles_per_cpu'] = cpu_cycles
            extracted['insts_per_cpu'] = cpu_insts
            extracted['cpu_cpis'] = cpu_cpis  # Store pre-calculated CPIs
    
    else:
        # Ruby cache hierarchy or unknown - try Ruby metrics first
        extracted['total_cycles'] = get_metric('system.clk_domain.clock')
        extracted['total_instructions'] = get_metric('system.cpu.commit.commits')
        
        # CPI calculation - need per-core metrics
        cpu_insts = []
        cpu_cycles = []
        for i in range(16):  # Support up to 16 cores
            insts_key = f'system.cpu{i}.commit.commits'
            cycles_key = f'system.cpu{i}.numCycles'
            
            insts = get_metric(insts_key)
            cycles = get_metric(cycles_key)
            
            if insts is not None and cycles is not None:
                cpu_insts.append(insts)
                cpu_cycles.append(cycles)
            else:
                # Try alternative keys
                insts_key = f'system.cpu.commit.commits'
                cycles_key = f'system.cpu.numCycles'
                insts = get_metric(insts_key)
                cycles = get_metric(cycles_key)
                if insts is not None and cycles is not None:
                    cpu_insts.append(insts)
                    cpu_cycles.append(cycles)
        
        extracted['num_cpus'] = len(cpu_insts)
        if cpu_insts:
            extracted['total_insts'] = sum(cpu_insts)
            extracted['total_cycles_per_cpu'] = cpu_cycles
            extracted['insts_per_cpu'] = cpu_insts
    
    # Invalidations (Ruby only - will be 0 for classic cache)
    inv_key = 'system.ruby_system.L1Cache_Controller.Inv::total'
    extracted['invalidations'] = get_metric(inv_key, 0)
    for state in ['I', 'S', 'E', 'M']:
        load_key = f'system.ruby_system.L1Cache_Controller.{state}.Load::total'
        extracted[f'loads_{state}'] = get_metric(load_key, 0)
    
    # L2 requests
    extracted['l2_gets'] = get_metric(
        'system.ruby_system.L2Cache_Controller.L1_GETS::total', 0
    )
    extracted['l2_getx'] = get_metric(
        'system.ruby_system.L2Cache_Controller.L1_GETX::total', 0
    )
    
    # Network traffic
    extracted['net_request_control'] = get_metric(
        'system.ruby_system.network.msg_count.Request_Control::total', 0
    )
    extracted['net_response_data'] = get_metric(
        'system.ruby_system.network.msg_count.Response_Data::total', 0
    )
    extracted['net_writeback_data'] = get_metric(
        'system.ruby_system.network.msg_count.Writeback_Data::total', 0
    )
    
    return extracted


def calculate_cpi_stats(extracted_metrics):
    """Calculate CPI mean and standard deviation per CPU."""
    import statistics
    
    # If we already have pre-calculated CPIs from classic cache, use those
    if 'cpu_cpis' in extracted_metrics and extracted_metrics['cpu_cpis']:
        cpi_values = extracted_metrics['cpu_cpis']
        if cpi_values:
            mean_cpi = statistics.mean(cpi_values)
            std_cpi = statistics.stdev(cpi_values) if len(cpi_values) > 1 else 0
            return mean_cpi, std_cpi
        else:
            return None, None
    
    # Otherwise calculate from instructions and cycles
    if extracted_metrics.get('num_cpus', 0) == 0:
        return None, None
    
    cpi_values = []
    if 'insts_per_cpu' in extracted_metrics and 'total_cycles_per_cpu' in extracted_metrics:
        for i in range(extracted_metrics['num_cpus']):
            insts = extracted_metrics['insts_per_cpu'][i]
            cycles = extracted_metrics['total_cycles_per_cpu'][i]
            
            if insts > 0:
                cpi = cycles / insts
                cpi_values.append(cpi)
    
    if not cpi_values:
        return None, None
    
    mean_cpi = statistics.mean(cpi_values)
    std_cpi = statistics.stdev(cpi_values) if len(cpi_values) > 1 else 0
    
    return mean_cpi, std_cpi


def process_results_directory(results_dir):
    """Process all simulation results in a directory."""
    summary = []
    
    if not os.path.exists(results_dir):
        print(f"ERROR: Results directory not found: {results_dir}", file=sys.stderr)
        return summary
    
    print(f"DEBUG: Scanning results directory: {results_dir}", file=sys.stderr)
    
    for variant_dir in sorted(os.listdir(results_dir)):
        sim_path = os.path.join(results_dir, variant_dir)
        if not os.path.isdir(sim_path):
            continue
        
        stats_file = os.path.join(sim_path, 'stats.txt')
        
        # Parse variant from directory name (e.g., "task2_falsesharing_2cores")
        # Remove 'task2_' prefix if present
        dir_name = variant_dir
        if dir_name.startswith('task2_'):
            dir_name = dir_name[6:]  # Remove 'task2_'
        
        # Remove 'cores' suffix and split on last '_'
        if dir_name.endswith('cores'):
            dir_name = dir_name[:-5]  # Remove 'cores' suffix
            parts = dir_name.rsplit('_', 1)  # Split on last '_'
            if len(parts) != 2:
                print(f"DEBUG: Skipping directory (name mismatch): {variant_dir}", file=sys.stderr)
                continue
            
            variant = parts[0]
            try:
                num_cores = int(parts[1])
            except ValueError:
                print(f"DEBUG: Skipping directory (invalid core count): {variant_dir}", file=sys.stderr)
                continue
        else:
            print(f"DEBUG: Skipping directory (invalid suffix): {variant_dir}", file=sys.stderr)
            continue
        
        print(f"DEBUG: Parsed directory '{variant_dir}' -> variant='{variant}', cores={num_cores}", file=sys.stderr)
        print(f"DEBUG: Looking for stats file: {stats_file}", file=sys.stderr)
        
        # Extract metrics
        raw_metrics = parse_stats_file(stats_file)
        if not raw_metrics:
            print(f"WARNING: No metrics extracted from {stats_file}", file=sys.stderr)
        
        extracted = extract_key_metrics(raw_metrics)
        
        # Calculate CPI stats
        mean_cpi, std_cpi = calculate_cpi_stats(extracted)
        
        record = {
            'variant': variant,
            'cores': num_cores,
            'num_cpus': extracted.get('num_cpus', 0),
            'mean_cpi': mean_cpi,
            'std_cpi': std_cpi,
            'invalidations': extracted.get('invalidations', 0),
            'loads_i': extracted.get('loads_I', 0),
            'loads_s': extracted.get('loads_S', 0),
            'loads_e': extracted.get('loads_E', 0),
            'loads_m': extracted.get('loads_M', 0),
            'l2_gets': extracted.get('l2_gets', 0),
            'l2_getx': extracted.get('l2_getx', 0),
            'net_request_control': extracted.get('net_request_control', 0),
            'net_response_data': extracted.get('net_response_data', 0),
            'net_writeback_data': extracted.get('net_writeback_data', 0),
        }
        summary.append(record)
    
    if not summary:
        print(f"ERROR: No simulation results found in {results_dir}", file=sys.stderr)
    
    return summary


def generate_csv_report(summary, output_file):
    """Generate CSV report from summary."""
    if not summary:
        print("Warning: No results to report", file=sys.stderr)
        return
    
    fieldnames = [
        'variant', 'cores', 'num_cpus', 'mean_cpi', 'std_cpi',
        'invalidations', 'loads_i', 'loads_s', 'loads_e', 'loads_m',
        'l2_gets', 'l2_getx', 'net_request_control', 'net_response_data',
        'net_writeback_data'
    ]
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)
    
    print(f"CSV report saved: {output_file}")


def generate_json_report(summary, output_file):
    """Generate JSON report from summary."""
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"JSON report saved: {output_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_results.py <results_directory> [output_base]")
        print("  results_directory: Path to directory containing simulation outputs")
        print("  output_base: Base path for report files (default: results_dir)")
        return 1
    
    results_dir = sys.argv[1]
    output_base = sys.argv[2] if len(sys.argv) > 2 else results_dir
    
    if not os.path.isdir(results_dir):
        print(f"Error: Directory not found: {results_dir}", file=sys.stderr)
        return 1
    
    print(f"Processing results from: {results_dir}")
    summary = process_results_directory(results_dir)
    
    if not summary:
        print("Error: No valid simulation results found", file=sys.stderr)
        return 1
    
    print(f"Found {len(summary)} simulation results")
    
    # Generate reports
    csv_file = os.path.join(output_base, "false_sharing_analysis.csv")
    json_file = os.path.join(output_base, "false_sharing_analysis.json")
    
    os.makedirs(output_base, exist_ok=True)
    
    generate_csv_report(summary, csv_file)
    generate_json_report(summary, json_file)
    
    # Print summary
    print("\n" + "="*70)
    print("ANALYSIS SUMMARY")
    print("="*70)
    for record in sorted(summary, key=lambda x: (x['variant'], x['cores'])):
        print(f"\n{record['variant'].upper()} - {record['cores']} cores:")
        
        # Handle None values for CPI
        if record['mean_cpi'] is not None and record['std_cpi'] is not None:
            print(f"  Mean CPI:           {record['mean_cpi']:.4f} ± {record['std_cpi']:.4f}")
        else:
            print(f"  Mean CPI:           N/A (no stats data)")
        
        # Handle None values for other metrics
        inv = record['invalidations'] if record['invalidations'] is not None else 0
        loads_i = record['loads_i'] if record['loads_i'] is not None else 0
        loads_s = record['loads_s'] if record['loads_s'] is not None else 0
        loads_e = record['loads_e'] if record['loads_e'] is not None else 0
        loads_m = record['loads_m'] if record['loads_m'] is not None else 0
        l2_gets = record['l2_gets'] if record['l2_gets'] is not None else 0
        l2_getx = record['l2_getx'] if record['l2_getx'] is not None else 0
        net_rc = record['net_request_control'] if record['net_request_control'] is not None else 0
        net_rd = record['net_response_data'] if record['net_response_data'] is not None else 0
        net_wd = record['net_writeback_data'] if record['net_writeback_data'] is not None else 0
        
        print(f"  Invalidations:      {int(inv)}")
        print(f"  Loads (I/S/E/M):    {int(loads_i)}/{int(loads_s)}/{int(loads_e)}/{int(loads_m)}")
        print(f"  L2 Requests (GET/X):{int(l2_gets)}/{int(l2_getx)}")
        print(f"  Network Traffic:")
        print(f"    Request_Control:  {int(net_rc)}")
        print(f"    Response_Data:    {int(net_rd)}")
        print(f"    Writeback_Data:   {int(net_wd)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

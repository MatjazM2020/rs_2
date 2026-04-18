#!/usr/bin/env python3
"""
Network Topology Analysis - Results Extractor
Extracts key metrics from gem5 stats.txt files for task3.
Analyzes network topologies (crossbar, point_to_point, ring) across different core counts.
"""

import os
import sys
import csv
import json
from pathlib import Path
from collections import defaultdict
import statistics


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
            if not line or line.startswith('---') or line.startswith('#'):
                continue
            
            # Parse stat lines: "stat_name value"
            if ' ' in line:
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
    """Extract key metrics for network topology analysis.
    Uses board.processor.coresX.core.* stats for performance metrics.
    """
    extracted = {}
    
    # Helper function to safely get metric
    def get_metric(key, default=None):
        return metrics.get(key, default)
    
    # Extract from board.processor.coresX.core.* (classic cache hierarchy)
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
        
        if cpi is not None and cycles is not None and not isinstance(cpi, str):
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
        extracted['cpu_cpis'] = cpu_cpis
    
    # Total cycles for execution time
    total_cycles = sum(cpu_cycles) if cpu_cycles else 0
    extracted['total_cycles'] = total_cycles
    extracted['execution_time_seconds'] = total_cycles / 1e9
    
    # Bus and traffic metrics
    extracted['membus_pkt_count'] = get_metric('board.cache_hierarchy.membus.pktCount::total', 0)
    extracted['membus_pkt_size'] = get_metric('board.cache_hierarchy.membus.pktSize::total', 0)
    extracted['membus_snoop_traffic'] = get_metric('board.cache_hierarchy.membus.snoopTraffic', 0)
    
    # L3 bus metrics
    extracted['l3_bus_snoop_traffic'] = get_metric('board.cache_hierarchy.l3_bus.snoopTraffic', 0)
    
    # Cache miss data - L1 and L2
    extracted['l1d_misses'] = get_metric('board.cache_hierarchy.clusters0.l1d_cache.overall_misses::total', 0)
    extracted['l2_misses'] = get_metric('board.cache_hierarchy.clusters0.l2_cache.overall_misses::total', 0)
    
    return extracted


def calculate_cpi_stats(extracted_metrics):
    """Calculate CPI mean and standard deviation per CPU."""
    if 'cpu_cpis' in extracted_metrics and extracted_metrics['cpu_cpis']:
        cpi_values = extracted_metrics['cpu_cpis']
        if cpi_values:
            mean_cpi = statistics.mean(cpi_values)
            std_cpi = statistics.stdev(cpi_values) if len(cpi_values) > 1 else 0
            return mean_cpi, std_cpi
    
    return None, None


def process_task3_results(results_dir):
    """Process all simulation results in task3 directory structure."""
    summary = []
    results_dir = Path(results_dir)
    
    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}", file=sys.stderr)
        return summary
    
    print(f"DEBUG: Scanning results directory: {results_dir}", file=sys.stderr)
    
    networks = ['point_to_point', 'ring', 'crossbar']
    cores_list = [2, 4, 8, 16]
    
    for network in networks:
        network_dir = results_dir / network
        if not network_dir.exists():
            print(f"WARNING: Network directory not found: {network_dir}", file=sys.stderr)
            continue
        
        for cores in cores_list:
            cores_dir = network_dir / f"cores_{cores}"
            stats_file = cores_dir / "stats.txt"
            
            print(f"DEBUG: Checking {network} with {cores} cores: {stats_file}", file=sys.stderr)
            
            if not stats_file.exists():
                print(f"WARNING: Stats file not found: {stats_file}", file=sys.stderr)
                continue
            
            file_size = os.path.getsize(str(stats_file))
            if file_size == 0:
                print(f"WARNING: Stats file is empty (0 bytes): {stats_file}", file=sys.stderr)
                continue
            
            print(f"DEBUG: Found stats.txt ({file_size} bytes) for {network} / {cores} cores", file=sys.stderr)
            
            # Parse and extract metrics
            raw_metrics = parse_stats_file(str(stats_file))
            if not raw_metrics:
                print(f"WARNING: No metrics extracted from {stats_file}", file=sys.stderr)
                continue
            
            extracted = extract_key_metrics(raw_metrics)
            mean_cpi, std_cpi = calculate_cpi_stats(extracted)
            
            record = {
                'network': network,
                'cores': cores,
                'num_cpus': extracted.get('num_cpus', 0),
                'mean_cpi': mean_cpi,
                'std_cpi': std_cpi,
                'execution_time_seconds': extracted.get('execution_time_seconds', 0),
                'membus_pkt_count': extracted.get('membus_pkt_count', 0),
                'membus_pkt_size': extracted.get('membus_pkt_size', 0),
                'membus_snoop_traffic': extracted.get('membus_snoop_traffic', 0),
                'l3_bus_snoop_traffic': extracted.get('l3_bus_snoop_traffic', 0),
                'l1d_misses': extracted.get('l1d_misses', 0),
                'l2_misses': extracted.get('l2_misses', 0),
            }
            summary.append(record)
            print(f"✓ Processed {network:15s} {cores:2d} cores", file=sys.stderr)
    
    if not summary:
        print(f"ERROR: No simulation results found in {results_dir}", file=sys.stderr)
    
    return summary


def generate_csv_report(summary, output_file):
    """Generate CSV report from summary."""
    if not summary:
        print("Warning: No results to report", file=sys.stderr)
        return
    
    fieldnames = [
        'network', 'cores', 'num_cpus', 'mean_cpi', 'std_cpi',
        'execution_time_seconds', 'membus_pkt_count', 'membus_pkt_size',
        'membus_snoop_traffic', 'l3_bus_snoop_traffic', 'l1d_misses', 'l2_misses'
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
        print("Usage: python3 task3_analysis.py <results_directory> [output_base]")
        print("  results_directory: Path to task3 results directory")
        print("  output_base: Base path for report files (default: results_dir)")
        return 1
    
    results_dir = sys.argv[1]
    output_base = sys.argv[2] if len(sys.argv) > 2 else results_dir
    
    if not os.path.isdir(results_dir):
        print(f"Error: Directory not found: {results_dir}", file=sys.stderr)
        return 1
    
    print(f"Processing results from: {results_dir}")
    summary = process_task3_results(results_dir)
    
    if not summary:
        print("Error: No valid simulation results found", file=sys.stderr)
        return 1
    
    print(f"Found {len(summary)} simulation results")
    
    # Generate reports
    csv_file = os.path.join(output_base, "analysis.csv")
    json_file = os.path.join(output_base, "analysis.json")
    
    os.makedirs(output_base, exist_ok=True)
    
    generate_csv_report(summary, csv_file)
    generate_json_report(summary, json_file)
    
    # Print summary
    print("\n" + "="*80)
    print("ANALYSIS SUMMARY - TASK3 NETWORK TOPOLOGIES")
    print("="*80)
    
    # Group by network
    by_network = defaultdict(list)
    for record in summary:
        by_network[record['network']].append(record)
    
    for network in sorted(by_network.keys()):
        print(f"\n{network.upper()}")
        print("-" * 80)
        print(f"{'Cores':>8} {'CPUs':>8} {'Mean CPI':>12} {'Std CPI':>12} {'Exec Time':>15} {'Membus Pkts':>15}")
        print("-" * 80)
        
        for record in sorted(by_network[network], key=lambda x: x['cores']):
            mean_cpi = record['mean_cpi'] if record['mean_cpi'] is not None else 0
            std_cpi = record['std_cpi'] if record['std_cpi'] is not None else 0
            exec_time = record['execution_time_seconds']
            membus_pkts = int(record['membus_pkt_count'])
            
            print(f"{record['cores']:>8d} {record['num_cpus']:>8d} "
                  f"{mean_cpi:>12.4f} {std_cpi:>12.4f} {exec_time:>15.6f} {membus_pkts:>15d}")
    
    print("\n" + "="*80)
    print("COMPARATIVE ANALYSIS ACROSS TOPOLOGIES")
    print("="*80)
    
    by_cores = defaultdict(list)
    for record in summary:
        by_cores[record['cores']].append(record)
    
    for cores in sorted(by_cores.keys()):
        print(f"\n{cores} CORES - Topology Comparison")
        print("-" * 80)
        print(f"{'Network':>20} {'Mean CPI':>12} {'Exec Time':>15} {'Membus Pkts':>15} {'L3 Snoop Traffic':>20}")
        print("-" * 80)
        
        for record in sorted(by_cores[cores], key=lambda x: x['network']):
            mean_cpi = record['mean_cpi'] if record['mean_cpi'] is not None else 0
            exec_time = record['execution_time_seconds']
            membus_pkts = int(record['membus_pkt_count'])
            l3_snoop = int(record['l3_bus_snoop_traffic'])
            
            print(f"{record['network']:>20s} {mean_cpi:>12.4f} {exec_time:>15.6f} "
                  f"{membus_pkts:>15d} {l3_snoop:>20d}")
    
    print("\n" + "="*80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

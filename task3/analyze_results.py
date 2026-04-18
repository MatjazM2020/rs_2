#!/usr/bin/env python3
"""
Network Topology Results Analysis
Extracts and analyzes metrics from simulation results.
Generates comparative analysis across topologies and core counts.
"""

import os
import sys
import argparse
import json
from pathlib import Path
from collections import defaultdict


def extract_stats(stats_file):
    """Extract all relevant statistics from stats.txt."""
    stats = {}
    
    try:
        if not os.path.exists(stats_file):
            print(f"ERROR: stats file not found: {stats_file}", file=sys.stderr)
            return None
        
        file_size = os.path.getsize(stats_file)
        if file_size == 0:
            print(f"ERROR: stats file is empty (0 bytes): {stats_file}", file=sys.stderr)
            return None
        
        print(f"DEBUG: Parsing stats file: {stats_file} (size: {file_size} bytes)", file=sys.stderr)
        
        with open(stats_file, 'r') as f:
            line_count = 0
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0]
                    try:
                        metric_value = float(parts[1])
                        stats[metric_name] = metric_value
                        line_count += 1
                    except ValueError:
                        pass
            
            if line_count == 0:
                print(f"WARNING: stats file has no parseable metrics: {stats_file}", file=sys.stderr)
    
    except FileNotFoundError:
        return None
    
    return stats


def extract_network_metrics(stats):
    """Extract network-specific metrics from gem5 stats.
    
    Supports both Ruby (MESI) and classic cache hierarchies.
    Ruby uses board.cache_hierarchy.ruby_system.network.msg_count.* naming.
    """
    if not stats:
        return None
    
    metrics = {}
    
    # Ruby network metric names (with board.cache_hierarchy prefix)
    ruby_network_keys = {
        'Request_Control': 'board.cache_hierarchy.ruby_system.network.msg_count.Request_Control',
        'Response_Data': 'board.cache_hierarchy.ruby_system.network.msg_count.Response_Data',
        'Writeback_Data': 'board.cache_hierarchy.ruby_system.network.msg_count.Writeback_Data',
    }
    
    # Classic network metric names (fallback)
    classic_network_keys = {
        'Request_Control': 'network.msg_count.Request_Control',
        'Response_Data': 'network.msg_count.Response_Data',
        'Writeback_Data': 'network.msg_count.Writeback_Data',
    }
    
    # Try Ruby keys first
    found_ruby = False
    for key_name, stat_name in ruby_network_keys.items():
        if stat_name in stats:
            metrics[key_name] = stats[stat_name]
            found_ruby = True
    
    # If no Ruby keys found, try classic keys
    if not found_ruby:
        for key_name, stat_name in classic_network_keys.items():
            if stat_name in stats:
                metrics[key_name] = stats[stat_name]
    
    # Calculate total network traffic
    if metrics:
        metrics['Total_Traffic'] = sum(metrics.values())
    
    return metrics if metrics else None


def analyze_results(results_dir):
    """Analyze results from a complete experiment run."""
    results_dir = Path(results_dir)
    
    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}")
        return False
    
    print("="*80)
    print("NETWORK TOPOLOGY ANALYSIS RESULTS")
    print("="*80)
    print(f"Results Directory: {results_dir}\n")
    
    # Collect results by network type and core count
    all_results = defaultdict(lambda: defaultdict(dict))
    
    networks = ['point_to_point', 'ring', 'crossbar']
    cores_list = [2, 4, 8, 16]
    
    for network in networks:
        for cores in cores_list:
            stats_file = results_dir / network / f"cores_{cores}" / "stats.txt"
            
            print(f"DEBUG: Checking {network} with {cores} cores: {stats_file}", file=sys.stderr)
            
            if stats_file.exists():
                file_size = os.path.getsize(str(stats_file))
                print(f"DEBUG: Found stats.txt (size: {file_size} bytes)", file=sys.stderr)
                
                if file_size == 0:
                    print(f"✗ {network:15s} {cores:2d} cores: stats.txt is empty (0 bytes)", file=sys.stdout)
                    continue
                
                all_stats = extract_stats(str(stats_file))
                network_metrics = extract_network_metrics(all_stats)
                
                if network_metrics:
                    all_results[network][cores] = network_metrics
                    print(f"✓ {network:15s} {cores:2d} cores: Found {len(network_metrics)} metrics")
                else:
                    print(f"✗ {network:15s} {cores:2d} cores: No network metrics found")
            else:
                print(f"✗ {network:15s} {cores:2d} cores: stats.txt not found")
    
    print("\n" + "="*80)
    print("DETAILED METRICS BY TOPOLOGY")
    print("="*80)
    
    # Print detailed results
    for network in networks:
        print(f"\n{network.upper()}")
        print("-" * 80)
        print(f"{'Cores':>8} {'Request_Ctrl':>15} {'Response_Data':>15} {'Writeback_Data':>15} {'Total_Traffic':>15}")
        print("-" * 80)
        
        for cores in cores_list:
            if cores in all_results[network]:
                metrics = all_results[network][cores]
                print(f"{cores:>8} "
                      f"{metrics.get('Request_Control', 0):>15.0f} "
                      f"{metrics.get('Response_Data', 0):>15.0f} "
                      f"{metrics.get('Writeback_Data', 0):>15.0f} "
                      f"{metrics.get('Total_Traffic', 0):>15.0f}")
            else:
                print(f"{cores:>8} {'[No Data]':>15} {'':>15} {'':>15} {'':>15}")
    
    print("\n" + "="*80)
    print("COMPARATIVE ANALYSIS")
    print("="*80)
    
    # Compare networks for each core count
    for cores in cores_list:
        print(f"\n{cores} CORES - Network Comparison")
        print("-" * 80)
        print(f"{'Network':>15} {'Request_Ctrl':>15} {'Response_Data':>15} {'Writeback_Data':>15} {'Total':>15}")
        print("-" * 80)
        
        for network in networks:
            if cores in all_results[network]:
                metrics = all_results[network][cores]
                print(f"{network:>15} "
                      f"{metrics.get('Request_Control', 0):>15.0f} "
                      f"{metrics.get('Response_Data', 0):>15.0f} "
                      f"{metrics.get('Writeback_Data', 0):>15.0f} "
                      f"{metrics.get('Total_Traffic', 0):>15.0f}")
    
    print("\n" + "="*80)
    print("SCALABILITY ANALYSIS (Traffic per Core)")
    print("="*80)
    
    # Analyze scalability trends
    for network in networks:
        print(f"\n{network.upper()}")
        print("-" * 80)
        print(f"{'Cores':>8} {'Total Traffic':>20} {'Per Core':>20} {'Efficiency %':>15}")
        print("-" * 80)
        
        traffic_data = []
        for cores in cores_list:
            if cores in all_results[network]:
                metrics = all_results[network][cores]
                total_traffic = metrics.get('Total_Traffic', 0)
                per_core = total_traffic / cores if cores > 0 else 0
                
                # Perfect scaling would be linear
                efficiency = (cores_list[0] * per_core / (total_traffic / cores_list[0] if cores_list[0] > 0 else 1)) * 100 if cores > cores_list[0] else 100
                
                print(f"{cores:>8} {total_traffic:>20.0f} {per_core:>20.0f} {efficiency:>14.1f}%")
                traffic_data.append((cores, total_traffic))
    
    # Save analysis results
    output_file = results_dir / "analysis_results.json"
    
    results_json = {
        'networks': networks,
        'core_counts': cores_list,
        'results': {},
    }
    
    for network in networks:
        results_json['results'][network] = {}
        for cores in cores_list:
            if cores in all_results[network]:
                results_json['results'][network][str(cores)] = all_results[network][cores]
    
    with open(output_file, 'w') as f:
        json.dump(results_json, f, indent=2)
    
    print(f"\n\nAnalysis results saved to: {output_file}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Analyze network topology simulation results"
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Path to results directory (default: latest in results/task3_*)"
    )
    
    args = parser.parse_args()
    
    if args.results_dir:
        results_dir = args.results_dir
    else:
        # Find latest results directory
        workspace_root = Path.cwd()
        results_base = workspace_root / "results"
        
        if not results_base.exists():
            print(f"Error: results directory not found")
            return 1
        
        task3_dirs = sorted([d for d in results_base.glob("task3_*")])
        if not task3_dirs:
            print(f"Error: No task3 results found in {results_base}")
            return 1
        
        results_dir = task3_dirs[-1]  # Latest directory
    
    if analyze_results(results_dir):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())

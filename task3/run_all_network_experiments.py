#!/usr/bin/env python3
"""
Network Topology Experiment Driver
Runs all combinations of network topologies and core counts.
Collects and analyzes results.
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime


def run_simulation(gem5_path, sim_script, cores, network, binary_path, output_dir, script_dir, gem5_container=None):
    """Run a single network topology simulation using gem5.opt with Ruby MESI.
    
    Uses srun for proper HPC resource allocation and Ruby MESI_TWO_LEVEL with network
    topologies to analyze interconnection network traffic and latency characteristics.
    """
    
    if not os.path.exists(binary_path):
        print(f"  ERROR: Binary not found: {binary_path}")
        return False
    
    cmd = [
        gem5_path,
        f"--outdir={output_dir}",
        sim_script,
        "--cores", str(cores),
        "--network", network,
        "--binary-path", binary_path,
    ]
    
    print(f"  Running: {network:15s} with {cores:2d} cores...")
    
    try:
        # If container is available, run inside it with srun for proper resource allocation
        if gem5_container and os.path.exists(gem5_container):
            # Bind mount the workspace directory so container can access all files
            workspace_root = os.path.dirname(os.path.dirname(script_dir))
            container_cmd = [
                'srun', 'apptainer', 'exec',
                '--bind', f"{workspace_root}:{workspace_root}",
                gem5_container
            ] + cmd
            result = subprocess.run(
                container_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=7200,  # 2 hours timeout
            )
        else:
            # Otherwise run directly with srun (should use srun if in HPC environment)
            container_cmd = ['srun'] + cmd
            result = subprocess.run(
                container_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=7200,  # 2 hours timeout
                cwd=script_dir
            )
        
        if result.returncode != 0 and result.returncode != -6:
            print(f"    ERROR: Simulation failed with code {result.returncode}")
            if result.stderr:
                print(f"    STDERR: {result.stderr[:500]}")
            return False
        elif result.returncode == -6:
            # Exit code -6 is SIGABRT, but stats may have been collected before crash
            print(f"    PARTIAL SUCCESS (SIGABRT after stats collection)")
            # Verify stats were actually written
            stats_file = os.path.join(output_dir, 'stats.txt')
            if os.path.exists(stats_file) and os.path.getsize(stats_file) > 0:
                return True
            else:
                print(f"    WARNING: Stats file empty or missing after SIGABRT")
                return False
        else:
            # Verify stats.txt exists and is non-empty before reporting success
            stats_file = os.path.join(output_dir, 'stats.txt')
            if os.path.exists(stats_file):
                file_size = os.path.getsize(stats_file)
                if file_size > 0:
                    print(f"    SUCCESS (stats: {file_size} bytes)")
                    return True
                else:
                    print(f"    ERROR: Stats file is empty (0 bytes) - simulation did not run properly")
                    if result.stderr:
                        print(f"    STDERR: {result.stderr[:500]}")
                    return False
            else:
                print(f"    ERROR: Stats file not created")
                if result.stderr:
                    print(f"    STDERR: {result.stderr[:500]}")
                return False
    
    except subprocess.TimeoutExpired:
        print(f"    ERROR: Simulation timed out (2 hours)")
        return False
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def extract_network_stats(stats_file):
    """Extract network traffic metrics from stats.txt."""
    metrics = {}
    
    try:
        if not os.path.exists(stats_file):
            print(f"    ERROR: Stats file not found: {stats_file}", file=sys.stderr)
            return metrics
        
        if os.path.getsize(stats_file) == 0:
            print(f"    ERROR: Stats file is empty (0 bytes): {stats_file}", file=sys.stderr)
            return metrics
        
        line_count = 0
        with open(stats_file, 'r') as f:
            for line in f:
                if "network.msg_count.Request_Control" in line:
                    try:
                        metrics['Request_Control'] = float(line.split()[1])
                        line_count += 1
                    except (IndexError, ValueError):
                        pass
                elif "network.msg_count.Response_Data" in line:
                    try:
                        metrics['Response_Data'] = float(line.split()[1])
                        line_count += 1
                    except (IndexError, ValueError):
                        pass
                elif "network.msg_count.Writeback_Data" in line:
                    try:
                        metrics['Writeback_Data'] = float(line.split()[1])
                        line_count += 1
                    except (IndexError, ValueError):
                        pass
        
        if line_count == 0:
            print(f"    WARNING: No network metrics found in {stats_file}", file=sys.stderr)
    
    except FileNotFoundError:
        print(f"    ERROR: Stats file not found: {stats_file}", file=sys.stderr)
    
    return metrics


def main():
    # Configuration - use standardized GEM5_PATH with Ruby-enabled build
    # RISCV_ALL_RUBY includes Ruby memory system for network topology analysis
    GEM5_PATH = "/d/hpc/projects/FRI/GEM5/gem5_workspace/gem5/build/RISCV_ALL_RUBY/gem5.opt"
    GEM5_CONTAINER = "/d/hpc/projects/FRI/GEM5/gem5_workspace/gem5_rv.sif"
    
    # Determine workspace paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try to get workspace from environment variable first (set by submit script)
    workspace_root = os.environ.get('WORKSPACE_DIR')
    if not workspace_root:
        workspace_root = os.path.dirname(script_dir)
    
    # Allow output directory to be passed as command-line argument
    if len(sys.argv) > 1:
        output_base = sys.argv[1]
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_base = os.path.join(workspace_root, 'results', f'task3_{timestamp}')
    
    binary_dir = os.path.join(workspace_root, 'workload', 'stream')
    binary_path = os.path.join(binary_dir, "stream.bin")
    sim_script = os.path.join(script_dir, 'run_network_sim.py')
    
    # Simulation parameters
    CORE_COUNTS = [2, 4, 8, 16]
    NETWORKS = ['point_to_point', 'ring', 'crossbar']
    
    # Verify required files
    if not os.path.exists(sim_script):
        print(f"Error: Simulation script not found: {sim_script}", file=sys.stderr)
        return 1
    
    if not os.path.exists(binary_dir):
        print(f"Error: Workload directory not found: {binary_dir}", file=sys.stderr)
        return 1
    
    print("="*80)
    print("NETWORK TOPOLOGY ANALYSIS - EXPERIMENT RUNNER")
    print("="*80)
    print(f"GEM5 Path:         {GEM5_PATH}")
    print(f"Workspace:         {workspace_root}")
    print(f"Binary Directory:  {binary_dir}")
    print(f"Output Directory:  {output_base}")
    print(f"Core Counts:       {CORE_COUNTS}")
    print(f"Network Types:     {NETWORKS}")
    print(f"Total Simulations: {len(CORE_COUNTS) * len(NETWORKS)}")
    print("="*80)
    
    # Create output directory
    os.makedirs(output_base, exist_ok=True)
    
    # Run simulations
    results_summary = {
        'point_to_point': {},
        'ring': {},
        'crossbar': {},
    }
    
    total_tests = len(CORE_COUNTS) * len(NETWORKS)
    passed = 0
    failed = 0
    
    start_time = time.time()
    
    for network in NETWORKS:
        print(f"\n{network.upper()}")
        print("-" * 80)
        
        for cores in CORE_COUNTS:
            output_dir = os.path.join(output_base, network, f"cores_{cores}")
            os.makedirs(output_dir, exist_ok=True)
            
            success = run_simulation(
                GEM5_PATH,
                sim_script,
                cores,
                network,
                binary_path,
                output_dir,
                script_dir,
                GEM5_CONTAINER
            )
            
            if success:
                passed += 1
                # Extract metrics
                stats_file = os.path.join(output_dir, "stats.txt")
                metrics = extract_network_stats(stats_file)
                results_summary[network][cores] = metrics
                
                if metrics:
                    print(f"      Metrics collected: {len(metrics)} metrics")
            else:
                failed += 1
                results_summary[network][cores] = None
    
    elapsed = time.time() - start_time
    
    # Print summary
    print("\n" + "="*80)
    print("EXPERIMENT SUMMARY")
    print("="*80)
    print(f"Total Tests:      {total_tests}")
    print(f"Passed:           {passed}")
    print(f"Failed:           {failed}")
    print(f"Elapsed Time:     {elapsed:.1f} seconds ({elapsed/3600:.1f} hours)")
    print(f"Output Directory: {output_base}")
    print("="*80)
    
    # Save summary to file
    summary_file = os.path.join(output_base, "summary.txt")
    with open(summary_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("NETWORK TOPOLOGY ANALYSIS - RESULTS SUMMARY\n")
        f.write("="*80 + "\n\n")
        
        for network in NETWORKS:
            f.write(f"\n{network.upper()}\n")
            f.write("-" * 80 + "\n")
            
            for cores in CORE_COUNTS:
                f.write(f"\nCores: {cores}\n")
                metrics = results_summary[network].get(cores)
                
                if metrics:
                    for metric, value in metrics.items():
                        f.write(f"  {metric:20s}: {value:15.0f}\n")
                else:
                    f.write("  [Simulation failed]\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write(f"Total Tests:      {total_tests}\n")
        f.write(f"Passed:           {passed}\n")
        f.write(f"Failed:           {failed}\n")
        f.write(f"Elapsed Time:     {elapsed:.1f} seconds ({elapsed/3600:.1f} hours)\n")
        f.write("="*80 + "\n")
    
    print(f"\nResults summary saved to: {summary_file}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

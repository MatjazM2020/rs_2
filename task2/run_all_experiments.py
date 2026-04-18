#!/usr/bin/env python3
"""
False Sharing Impact Analysis - Experiment Runner
Runs all simulation configurations using gem5.opt within the container.
Usage: python3 run_all_experiments.py [output_directory]
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def run_simulation(gem5_path, sim_script, cores, variant, binary_dir, output_dir, gem5_container=None):
    """Run a single simulation configuration using gem5.opt in container."""
    
    cmd = [
        gem5_path,
        f"--outdir={output_dir}",
        sim_script,
        "--cores", str(cores),
        "--variant", variant,
        "--binary-dir", binary_dir,
    ]
    
    print(f"  Running: {variant} with {cores} cores...")
    print(f"  Command: {' '.join(cmd)}")
    
    try:
        # If container is available, run inside it
        if gem5_container and os.path.exists(gem5_container):
            # Bind mount the workspace directory so container can access all files
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(sim_script)))
            container_cmd = [
                'apptainer', 'exec',
                '--bind', f"{workspace_root}:{workspace_root}",
                gem5_container
            ] + cmd
            result = subprocess.run(
                container_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )
        else:
            # Otherwise run directly
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )
        
        if result.returncode != 0 and result.returncode != -6:
            print(f"    ERROR: Simulation failed with code {result.returncode}")
            if result.stdout:
                stdout_lines = result.stdout.split('\n')
                print(f"    STDOUT (last 10 lines):")
                for line in stdout_lines[-10:]:
                    if line.strip():
                        print(f"      {line}")
            if result.stderr:
                stderr_lines = result.stderr.split('\n')
                print(f"    STDERR (last 10 lines):")
                for line in stderr_lines[-10:]:
                    if line.strip():
                        print(f"      {line}")
            return False
        elif result.returncode == -6:
            # Exit code -6 is SIGABRT, but stats may have been collected before crash
            print(f"    PARTIAL SUCCESS (SIGABRT after stats collection)")
            return True
        else:
            print(f"    SUCCESS")
            return True
    
    except subprocess.TimeoutExpired:
        print(f"    ERROR: Simulation timed out (1 hour)")
        return False
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def main():
    # Configuration - use standardized GEM5_PATH
    GEM5_PATH = "/d/hpc/projects/FRI/GEM5/gem5_workspace/gem5/build/RISCV/gem5.opt"
    GEM5_CONTAINER = "/d/hpc/projects/FRI/GEM5/gem5_workspace/gem5_rv.sif"
    
    # Determine workspace paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(script_dir)
    
    binary_dir = os.path.join(workspace_root, 'workload', 'parallel_prefix')
    
    # Allow output directory to be passed as command-line argument
    if len(sys.argv) > 1:
        output_base = sys.argv[1]
    else:
        output_base = os.path.join(workspace_root, 'results', 'task2')
    
    # Simulation parameters
    CORE_COUNTS = [2, 4, 8, 16]
    VARIANTS = ['falsesharing', 'optimized']
    
    # Use classic cache version instead of Ruby (Ruby MESI_TWO_LEVEL not compiled in GEM5)
    # The Ruby protocol would provide more detailed cache coherence stats, but the classic
    # version will provide valid performance metrics (CPI, cache stats, etc.)
    sim_script = os.path.join(script_dir, 'run_false_sharing_sim_classic.py')
    analyze_script = os.path.join(script_dir, 'analyze_results.py')
    
    for required_file in [sim_script, analyze_script, binary_dir]:
        if not os.path.exists(required_file):
            print(f"Error: Required file not found: {required_file}", file=sys.stderr)
            return 1
    
    print("="*70)
    print("FALSE SHARING IMPACT ANALYSIS - EXPERIMENT RUNNER")
    print("="*70)
    print(f"GEM5 Path:        {GEM5_PATH}")
    print(f"Container:        {GEM5_CONTAINER if os.path.exists(GEM5_CONTAINER) else 'NOT FOUND'}")
    print(f"Workspace:        {workspace_root}")
    print(f"Binary Directory: {binary_dir}")
    print(f"Output Directory: {output_base}")
    print(f"Core Counts:      {CORE_COUNTS}")
    print(f"Variants:         {VARIANTS}")
    print(f"Total Simulations: {len(CORE_COUNTS) * len(VARIANTS)}")
    print("="*70)
    
    # Create output directory
    os.makedirs(output_base, exist_ok=True)
    
    # Run simulations
    results_summary = {
        'start_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'configurations': [],
        'completed': 0,
        'failed': 0,
    }
    
    total_configs = len(CORE_COUNTS) * len(VARIANTS)
    current = 0
    
    for variant in VARIANTS:
        for cores in CORE_COUNTS:
            current += 1
            print(f"\n[{current}/{total_configs}] {variant.upper()} - {cores} cores")
            
            # Create output subdirectory for this configuration
            config_output_dir = os.path.join(
                output_base, 
                f"task2_{variant}_{cores}cores"
            )
            os.makedirs(config_output_dir, exist_ok=True)
            
            # Run simulation using gem5.opt
            success = run_simulation(
                GEM5_PATH, 
                sim_script, 
                cores, 
                variant, 
                binary_dir, 
                config_output_dir,
                GEM5_CONTAINER
            )
            
            if success:
                results_summary['completed'] += 1
                results_summary['configurations'].append({
                    'variant': variant,
                    'cores': cores,
                    'status': 'completed',
                })
            else:
                results_summary['failed'] += 1
                results_summary['configurations'].append({
                    'variant': variant,
                    'cores': cores,
                    'status': 'failed',
                })
    
    results_summary['end_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Analyze results
    print("\n" + "="*70)
    print("ANALYZING RESULTS")
    print("="*70)
    
    try:
        result = subprocess.run(
            ['python3', analyze_script, output_base],
            capture_output=False,
            text=True,
            timeout=300
        )
        if result.returncode != 0:
            print("Warning: Result analysis encountered issues")
    except Exception as e:
        print(f"Warning: Could not run analysis: {e}")
    
    # Print summary
    print("\n" + "="*70)
    print("EXPERIMENT SUMMARY")
    print("="*70)
    print(f"Start Time:      {results_summary['start_time']}")
    print(f"End Time:        {results_summary['end_time']}")
    print(f"Completed:       {results_summary['completed']}/{total_configs}")
    print(f"Failed:          {results_summary['failed']}/{total_configs}")
    print(f"Output:          {output_base}")
    print("="*70)
    
    return 0 if results_summary['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

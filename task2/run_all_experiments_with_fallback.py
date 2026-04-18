#!/usr/bin/env python3
"""
False Sharing Impact Analysis - Experiment Runner (Fallback to Classic Cache)
Runs all simulation configurations using gem5.opt.
Automatically tries classic cache version if Ruby/MESI version fails.

Usage: python3 run_all_experiments_with_fallback.py [output_directory]
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def run_simulation(gem5_path, sim_script, cores, variant, binary_dir, output_dir, is_fallback=False):
    """Run a single simulation configuration using gem5.opt."""
    
    cmd = [
        gem5_path,
        f"--outdir={output_dir}",
        sim_script,
        "--cores", str(cores),
        "--variant", variant,
        "--binary-dir", binary_dir,
    ]
    
    mode_label = "(Classic Cache)" if is_fallback else "(Ruby MESI)"
    print(f"  Running: {variant} with {cores} cores {mode_label}...")
    
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )
        
        if result.returncode != 0:
            print(f"    ERROR: Simulation failed with code {result.returncode}")
            if result.stdout:
                stdout_lines = result.stdout.split('\n')
                print(f"    STDOUT (last 5 lines):")
                for line in stdout_lines[-5:]:
                    if line.strip():
                        print(f"      {line}")
            if result.stderr:
                stderr_lines = result.stderr.split('\n')
                print(f"    STDERR (last 5 lines):")
                for line in stderr_lines[-5:]:
                    if line.strip():
                        print(f"      {line}")
            return False
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
    # Configuration
    GEM5_PATH = "/d/hpc/projects/FRI/GEM5/gem5_workspace/gem5/build/RISCV/gem5.opt"
    
    # Determine workspace paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(script_dir)
    
    binary_dir = os.path.join(workspace_root, 'workload', 'parallel_prefix')
    
    # Allow output directory to be passed as command-line argument
    if len(sys.argv) > 1:
        output_base = sys.argv[1]
    else:
        output_base = os.path.join(workspace_root, 'results', 'task2')
    
    # Create timestamped output directory
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(output_base, f"task2_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*80)
    print("FALSE SHARING IMPACT ANALYSIS - EXPERIMENT RUNNER")
    print("="*80)
    print(f"GEM5 Path:        {GEM5_PATH}")
    print(f"Workspace:        {workspace_root}")
    print(f"Binary Directory: {binary_dir}")
    print(f"Output Directory: {output_dir}")
    print("="*80 + "\n")
    
    # Configuration parameters
    cores_list = [2, 4, 8, 16]
    variants = ['falsesharing', 'optimized']
    
    # Try Ruby/MESI version first, fall back to classic if it fails
    ruby_script = os.path.join(script_dir, 'run_false_sharing_sim.py')
    classic_script = os.path.join(script_dir, 'run_false_sharing_sim_classic.py')
    
    total_sims = len(cores_list) * len(variants)
    completed = 0
    passed = 0
    failed = 0
    
    use_classic = False
    
    # Run all simulations
    for i, cores in enumerate(cores_list):
        for j, variant in enumerate(variants):
            test_num = i * len(variants) + j + 1
            print(f"[{test_num}/{total_sims}] {variant.upper()} - {cores} cores")
            
            # Determine which script to use
            if use_classic:
                sim_script = classic_script
            else:
                sim_script = ruby_script
            
            # Try to run simulation
            success = run_simulation(
                GEM5_PATH, sim_script, cores, variant, binary_dir, output_dir, 
                is_fallback=use_classic
            )
            completed += 1
            
            # If Ruby version fails and we haven't tried fallback yet, try fallback
            if not success and not use_classic and os.path.exists(classic_script):
                print(f"    Ruby version failed, trying classic cache fallback...")
                use_classic = True
                success = run_simulation(
                    GEM5_PATH, classic_script, cores, variant, binary_dir, output_dir,
                    is_fallback=True
                )
            
            if success:
                passed += 1
            else:
                failed += 1
    
    # Print summary
    print("\n" + "="*80)
    print("EXPERIMENT SUMMARY")
    print("="*80)
    print(f"Total Simulations:  {total_sims}")
    print(f"Passed:             {passed}/{total_sims}")
    print(f"Failed:             {failed}/{total_sims}")
    print(f"Output:             {output_dir}")
    if use_classic:
        print("\nNote: Classic cache hierarchy was used (Ruby MESI not available)")
        print("To use Ruby MESI protocol, rebuild GEM5 with:")
        print("  cd /d/hpc/projects/FRI/GEM5/gem5_workspace/gem5")
        print("  scons build/RISCV/gem5.opt --with-protocol=MESI_TWO_LEVEL -j$(nproc)")
    print("="*80 + "\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

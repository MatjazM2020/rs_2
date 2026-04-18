#!/usr/bin/env python3
"""
Test script to run a single simulation and capture detailed output.
"""

import subprocess
import sys
import os

GEM5_PATH = "/d/hpc/projects/FRI/GEM5/gem5_workspace/gem5/build/RISCV/gem5.opt"
WORKSPACE = "/d/hpc/home/mm11484/rs_2"
SIM_SCRIPT = os.path.join(WORKSPACE, "task2", "run_false_sharing_sim.py")
BINARY_DIR = os.path.join(WORKSPACE, "workload", "parallel_prefix")
OUTPUT_DIR = "/tmp/test_sim_output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Testing single simulation...")
print(f"GEM5 Path: {GEM5_PATH}")
print(f"Script: {SIM_SCRIPT}")
print(f"Binary Dir: {BINARY_DIR}")
print(f"Output Dir: {OUTPUT_DIR}")
print()

cmd = [
    GEM5_PATH,
    f"--outdir={OUTPUT_DIR}",
    SIM_SCRIPT,
    "--cores", "2",
    "--variant", "falsesharing",
    "--binary-dir", BINARY_DIR,
]

print(f"Running: {' '.join(cmd)}")
print("="*80)

result = subprocess.run(
    cmd,
    capture_output=False,
    text=True,
    timeout=300,
)

print("="*80)
print(f"\nExit code: {result.returncode}")
print(f"\nOutput directory contents:")
for item in os.listdir(OUTPUT_DIR):
    path = os.path.join(OUTPUT_DIR, item)
    size = os.path.getsize(path) if os.path.isfile(path) else "DIR"
    print(f"  {item}: {size}")

# Check stats file
stats_file = os.path.join(OUTPUT_DIR, "stats.txt")
if os.path.exists(stats_file):
    print(f"\nStats file size: {os.path.getsize(stats_file)} bytes")
    if os.path.getsize(stats_file) > 0:
        print("First 20 lines of stats.txt:")
        with open(stats_file, 'r') as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                print(f"  {line.rstrip()}")
    else:
        print("Stats file is empty")

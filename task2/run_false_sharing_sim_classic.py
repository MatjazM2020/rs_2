#!/usr/bin/env python3
"""
False Sharing Impact Analysis - gem5 Simulation Runner (Classic Cache Version)
Uses classic cache hierarchy instead of Ruby MESI protocol.
Runs simulations with configurable core count and binary variant.

This script must be run through gem5.opt to access the m5 module:
  gem5.opt run_false_sharing_sim_classic.py --cores 2 --variant falsesharing --binary-dir /path/to/binaries
"""

import sys
import os
import argparse

import m5
from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.components.memory.single_channel import SingleChannelDDR3_1600
from gem5.isas import ISA
from gem5.resources.resource import CustomResource
from gem5.simulate.simulator import Simulator

# Import classic cache hierarchy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'smp_classic'))
from three_level import PrivateL1PrivateL2SharedL3CacheHierarchy


def main():
    parser = argparse.ArgumentParser(
        description="Run gem5 simulation for false sharing analysis (Classic Cache Mode)"
    )
    parser.add_argument(
        "--cores", type=int, required=True,
        help="Number of CPU cores (2, 4, 8, or 16)"
    )
    parser.add_argument(
        "--variant", type=str, required=True,
        choices=["falsesharing", "optimized"],
        help="Binary variant: falsesharing or optimized"
    )
    parser.add_argument(
        "--binary-dir", type=str, required=True,
        help="Directory containing binary files"
    )
    
    args = parser.parse_args()
    
    # Validate core count
    if args.cores not in [2, 4, 8, 16]:
        print("Error: cores must be 2, 4, 8, or 16", file=sys.stderr)
        return 1
    
    # Construct binary path
    binary_filename = f"pprefix_{args.variant}.bin"
    binary_path = os.path.join(args.binary_dir, binary_filename)
    if not os.path.exists(binary_path):
        print(f"Error: Binary not found: {binary_path}", file=sys.stderr)
        return 1
    
    # Use m5.options.outdir set by gem5.opt --outdir parameter
    # Create subdirectory for this specific configuration
    sim_output_dir = os.path.join(
        m5.options.outdir,
        f"{args.variant}_cores{args.cores}"
    )
    os.makedirs(sim_output_dir, exist_ok=True)
    m5.options.outdir = sim_output_dir
    
    # Create cache hierarchy using classic (non-Ruby) implementation
    # L1: 32KB instruction + data (per core)
    # L2: 256KB (per core)  
    # L3: 8MB (shared)
    cache_hierarchy = PrivateL1PrivateL2SharedL3CacheHierarchy(
        l1d_size="32KiB",
        l1i_size="32KiB",
        l1d_assoc=8,
        l1i_assoc=8,
        l2_size="256KiB",
        l2_assoc=8,
        l3_size="8MiB",
        l3_assoc=16,
    )
    
    # Create processor with specified number of cores
    processor = SimpleProcessor(
        cpu_type=CPUTypes.TIMING,
        num_cores=args.cores,
        isa=ISA.RISCV,
    )
    
    # Create memory system
    memory = SingleChannelDDR3_1600(size="4GiB")
    
    # Create board
    board = SimpleBoard(
        clk_freq="3GHz",
        processor=processor,
        memory=memory,
        cache_hierarchy=cache_hierarchy,
    )
    
    # Create and run simulator
    simulator = Simulator(board=board, full_system=False)
    
    # Load binary and set as workload
    binary = CustomResource(binary_path)
    board.set_se_binary_workload(binary)
    
    print(f"\n{'='*80}")
    print(f"Starting simulation: {args.variant} with {args.cores} cores")
    print(f"Binary: {binary_path}")
    print(f"Output directory: {sim_output_dir}")
    print(f"Cache hierarchy: Classic 3-level (L1i/L1d 32KB, L2 256KB, L3 8MB)")
    print(f"{'='*80}\n")
    
    # Reset stats before running simulation
    m5.stats.reset()
    print(f"Stats reset before simulation", file=sys.stderr)
    
    # Run simulation
    simulator.run()
    
    print(f"\nSimulation completed")
    
    # Dump stats to ensure they're written to stats.txt
    print(f"Dumping stats to {m5.options.outdir}...", file=sys.stderr)
    m5.stats.dump()
    print(f"Stats dumped successfully", file=sys.stderr)
    
    # Verify stats.txt was written
    stats_file = os.path.join(m5.options.outdir, 'stats.txt')
    if os.path.exists(stats_file):
        file_size = os.path.getsize(stats_file)
        print(f"Stats file created: {stats_file} (size: {file_size} bytes)", file=sys.stderr)
    else:
        print(f"WARNING: Stats file not found at {stats_file}", file=sys.stderr)
    
    print(f"Output saved to: {sim_output_dir}")
    
    return 0


if __name__ == "__m5_main__":
    sys.exit(main())

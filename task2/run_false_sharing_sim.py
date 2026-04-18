#!/usr/bin/env python3
"""
False Sharing Impact Analysis - gem5 Simulation Runner
Runs simulations with configurable core count and binary variant.

This script must be run through gem5.opt to access the m5 module:
  gem5.opt run_false_sharing_sim.py --cores 2 --variant falsesharing --binary-dir /path/to/binaries
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
from gem5.utils.requires import requires
from gem5.coherence_protocol import CoherenceProtocol

# Import cache hierarchy - use absolute import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'smp_ruby'))
from mesi_two_level import MESITwoLevelCacheHierarchy


def main():
    parser = argparse.ArgumentParser(
        description="Run gem5 simulation for false sharing analysis"
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
    # Do NOT create subdirectories - gem5 handles output directory management
    print(f"DEBUG: Using outdir set by gem5.opt: {m5.options.outdir}", file=sys.stderr)
    os.makedirs(m5.options.outdir, exist_ok=True)
    
    # Require MESI_TWO_LEVEL protocol - try, but don't fail if not available
    try:
        requires(coherence_protocol_required=CoherenceProtocol.MESI_TWO_LEVEL)
        print(f"DEBUG: MESI_TWO_LEVEL protocol available", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: MESI_TWO_LEVEL protocol not available: {e}", file=sys.stderr)
        pass
    
    # Create cache hierarchy with specified parameters
    cache_hierarchy = MESITwoLevelCacheHierarchy(
        l1i_size="32KiB",
        l1i_assoc=8,
        l1d_size="32KiB",
        l1d_assoc=8,
        l2_size="256KiB",
        l2_assoc=8,
        num_l2_banks=1,
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
    
    # Load binary and set as workload
    binary = CustomResource(binary_path)
    board.set_se_binary_workload(binary)
    
    # Run simulation
    simulator = Simulator(board=board)
    print(f"DEBUG: Starting simulation for {args.variant} with {args.cores} cores", file=sys.stderr)
    print(f"DEBUG: Output directory: {m5.options.outdir}", file=sys.stderr)
    
    # Reset stats before running simulation
    m5.stats.reset()
    print(f"DEBUG: Stats reset before simulation", file=sys.stderr)
    
    simulator.run()
    print(f"DEBUG: Simulation run completed", file=sys.stderr)
    
    # Dump stats to ensure they're written to stats.txt
    print(f"DEBUG: About to dump stats", file=sys.stderr)
    m5.stats.dump()
    print(f"DEBUG: Stats dumped to {m5.options.outdir}", file=sys.stderr)
    
    # Verify stats.txt was written
    stats_file = os.path.join(m5.options.outdir, 'stats.txt')
    if os.path.exists(stats_file):
        file_size = os.path.getsize(stats_file)
        print(f"DEBUG: Stats file created: {stats_file} (size: {file_size} bytes)", file=sys.stderr)
    else:
        print(f"WARNING: Stats file not found at {stats_file}", file=sys.stderr)
    
    print(f"Simulation completed. Results saved to: {m5.options.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

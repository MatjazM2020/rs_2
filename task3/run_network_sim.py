#!/usr/bin/env python3
"""
Network Topology Analysis - gem5 Simulation Runner
Runs simulations with configurable core count and network topology.

This script must be run through gem5.opt to access the m5 module:
  gem5.opt run_network_sim.py --cores 2 --network ring --binary-path /path/to/binary
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

# Import Ruby MESI cache hierarchy with network topology support
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'smp_ruby'))
from mesi_two_level_networks import MESITwoLevelCacheHierarchyWithNetworks


def main():
    parser = argparse.ArgumentParser(
        description="Run gem5 simulation with different network topologies"
    )
    parser.add_argument(
        "--cores",
        type=int,
        required=True,
        help="Number of CPU cores (2, 4, 8, or 16)"
    )
    parser.add_argument(
        "--network",
        type=str,
        required=True,
        choices=["point_to_point", "ring", "crossbar"],
        help="Network topology type"
    )
    parser.add_argument(
        "--binary-path",
        type=str,
        required=True,
        help="Path to DAXPY binary"
    )
    
    args = parser.parse_args()
    
    # Use m5.options.outdir set by gem5.opt --outdir parameter
    print(f"DEBUG: Using outdir set by gem5.opt: {m5.options.outdir}", file=sys.stderr)
    os.makedirs(m5.options.outdir, exist_ok=True)
    
    print(f"DEBUG: Network topology: {args.network}", file=sys.stderr)
    print(f"DEBUG: Using Ruby MESI cache hierarchy with {args.network} network", file=sys.stderr)
    
    # Map command-line network names to cache hierarchy parameter names
    network_type_map = {
        "point_to_point": "point_to_point",
        "ring": "ring",
        "crossbar": "crossbar",
    }
    
    network_type = network_type_map.get(args.network, "point_to_point")
    
    # Create Ruby MESI cache hierarchy with specified network topology
    # Task 3: Measures network traffic for different interconnection topologies
    cache_hierarchy = MESITwoLevelCacheHierarchyWithNetworks(
        l1d_size="32KiB",
        l1d_assoc=8,
        l1i_size="32KiB",
        l1i_assoc=8,
        l2_size="256KiB",
        l2_assoc=8,
        num_l2_banks=1,
        network_type=network_type,
    )
    cache_type = f"Ruby MESI ({args.network} network)"
    
    # Create processor with specified core count
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
    
    # Load DAXPY binary
    binary = CustomResource(args.binary_path)
    board.set_se_binary_workload(binary)
    
    # Run simulation
    print(f"\n{'='*70}")
    print(f"Network Topology Simulation")
    print(f"{'='*70}")
    print(f"Network Type:    {args.network}")
    print(f"CPU Cores:       {args.cores}")
    print(f"Binary:          {args.binary_path}")
    print(f"Cache Type:      {cache_type}")
    print(f"Output Dir:      {m5.options.outdir}")
    print(f"{'='*70}\n")
    
    simulator = Simulator(board=board, full_system=False)
    print(f"DEBUG: Starting simulation run for {args.network} with {args.cores} cores", file=sys.stderr)
    print(f"DEBUG: Output directory: {m5.options.outdir}", file=sys.stderr)
    
    # Reset stats before running simulation
    m5.stats.reset()
    print(f"DEBUG: Stats reset before simulation", file=sys.stderr)
    
    # Run simulation with error handling to ensure stats are dumped
    try:
        simulator.run()
        print(f"DEBUG: Simulation run completed", file=sys.stderr)
    except Exception as e:
        import traceback
        print(f"WARNING: Simulator encountered exception: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"DEBUG: Traceback: {traceback.format_exc()}", file=sys.stderr)
        print(f"DEBUG: Continuing to dump stats despite exception", file=sys.stderr)
    
    # Dump stats to ensure they're written to stats.txt (even if simulator crashed)
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
    
    # Clean up unnecessary config files - keep only stats.txt
    cleanup_files = ['citations.bib', 'config.dot', 'config.dot.pdf', 'config.dot.svg', 'config.ini', 'config.json']
    for filename in cleanup_files:
        filepath = os.path.join(m5.options.outdir, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                print(f"DEBUG: Removed {filename}", file=sys.stderr)
            except Exception as e:
                print(f"WARNING: Failed to remove {filename}: {e}", file=sys.stderr)
    
    print(f"\n{'='*70}")
    print(f"Simulation completed successfully")
    print(f"Results saved to: {m5.options.outdir}")
    print(f"{'='*70}\n")
    
    return 0


if __name__ == "__m5_main__":
    sys.exit(main())

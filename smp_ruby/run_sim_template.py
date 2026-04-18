#!/usr/bin/env python3
"""
gem5 Simulation Runner - Template
Configurable simulation runner for false sharing experiments.
Accepts command line arguments for core count and variant.
"""

import sys
import os
import argparse

# Add gem5 build directory to Python path before importing m5
# Try standard container installation paths
gem5_possible_paths = [
    "/gem5/build/RISCV",
    "/opt/gem5/build/RISCV",
    "/usr/local/gem5/build/RISCV",
]
for gem5_path in gem5_possible_paths:
    if os.path.exists(gem5_path) and gem5_path not in sys.path:
        sys.path.insert(0, gem5_path)

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
from mesi_two_level import MESITwoLevelCacheHierarchy


def main():
    parser = argparse.ArgumentParser(description="Run gem5 simulation for false sharing analysis")
    parser.add_argument("--cores", type=int, required=True, help="Number of CPU cores")
    parser.add_argument("--variant", type=str, required=True, 
                       choices=["falsesharing", "optimized"],
                       help="Binary variant to simulate")
    parser.add_argument("--binary-path", type=str, required=True, 
                       help="Path to binary in container")
    args = parser.parse_args()
    
    # Use m5.options.outdir set by gem5.opt --outdir parameter
    # Create subdirectory for this specific configuration
    results_dir = os.path.join(m5.options.outdir, 
                               f"sim_{args.variant}_cores{args.cores}")
    os.makedirs(results_dir, exist_ok=True)
    m5.options.outdir = results_dir
    
    requires(coherence_protocol_required=CoherenceProtocol.MESI_TWO_LEVEL)
    
    cache_hierarchy = MESITwoLevelCacheHierarchy(
        l1d_size="32KiB",
        l1d_assoc=8,
        l1i_size="32KiB",
        l1i_assoc=8,
        l2_size="256KiB",
        l2_assoc=8,
        num_l2_banks=1,
    )
    
    processor = SimpleProcessor(
        cpu_type=CPUTypes.TIMING,
        num_cores=args.cores,
        isa=ISA.RISCV,
    )
    
    memory = SingleChannelDDR3_1600(size="4GiB")
    
    board = SimpleBoard(
        clk_freq="3GHz",
        processor=processor,
        memory=memory,
        cache_hierarchy=cache_hierarchy,
    )
    
    binary = CustomResource(args.binary_path)
    board.set_se_binary_workload(binary)
    
    simulator = Simulator(board=board)
    simulator.run()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

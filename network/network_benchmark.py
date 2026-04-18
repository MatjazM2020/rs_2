
from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory.multi_channel import DualChannelDDR4_2400
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_switchable_processor import (
    SimpleSwitchableProcessor
)
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import obtain_resource
from gem5.simulate.exit_event import ExitEvent
from gem5.simulate.simulator import Simulator
from gem5.resources.resource import CustomResource
from gem5.components.memory.single_channel import SingleChannelDDR3_1600

from mesi_two_level import MESITwoLevelCacheHierarchy

import m5
import os
import argparse


parser = argparse.ArgumentParser(description="Configure simulation parameters.")
parser.add_argument("--num_cores", type=int, default=4, help="Number of CPU cores.")
parser.add_argument("--l1_size", type=str, default="1KiB", help="L1 cache size.")
parser.add_argument("--l2_size", type=str, default="4KiB", help="L2 cache size.")

args = parser.parse_args()

# Set up output directory using m5.options.outdir
# If called by gem5.opt, --outdir will have already set this
# If run standalone, use default results directory
if m5.options.outdir == ".":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(os.path.dirname(script_dir))  # rs_2 folder
    results_dir = os.path.join(workspace_root, "results", "network")
else:
    results_dir = m5.options.outdir

os.makedirs(results_dir, exist_ok=True)
m5.options.outdir = results_dir

cache_hiearchy = MESITwoLevelCacheHierarchy(
    l1d_size=args.l1_size,
    l1d_assoc=8,
    l1i_size=args.l1_size,
    l1i_assoc=8,
    l2_size=args.l2_size,
    l2_assoc=8,
    num_l2_banks=1,
)

processor = SimpleProcessor(
    cpu_type=CPUTypes.MINOR,
    num_cores=args.num_cores,
    isa=ISA.RISCV,
)

memory = SingleChannelDDR3_1600(size="2GiB")

#add board 
board = SimpleBoard(
    clk_freq="3GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hiearchy,
)

binary = CustomResource("../workload/stream/stream.bin")
board.set_se_binary_workload(binary)

simulator = Simulator(board=board)
simulator.run()

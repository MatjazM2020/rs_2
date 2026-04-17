
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
from gem5.simulate.exit_event import ExitEvent



from three_level import PrivateL1PrivateL2SharedL3CacheHierarchy

import m5
import argparse

parser = argparse.ArgumentParser(description="Configure simulation parameters.")
parser.add_argument("--num_cores", type=int, default=4, help="Number of CPU cores.")
parser.add_argument("--l1_size", type=str, default="32KiB", help="L1 cache size.")
parser.add_argument("--l2_size", type=str, default="512KiB", help="L2 cache size.")
parser.add_argument("--l3_size", type=str, default="2MiB", help="L3 cache size.")

args = parser.parse_args()


cache_hiearchy = PrivateL1PrivateL2SharedL3CacheHierarchy(
    l1d_size=args.l1_size,
    l1d_assoc=8,
    l1i_size=args.l1_size,
    l1i_assoc=8,
    l2_size=args.l2_size,
    l2_assoc=8,
    l3_size=args.l3_size,
    l3_assoc=16,
)

processor = SimpleProcessor(
        cpu_type=CPUTypes.MINOR,
        num_cores=args.num_cores,
        isa=ISA.RISCV,
    )


memory = SingleChannelDDR3_1600(size="4GiB")




#add board 
board = SimpleBoard(
    clk_freq="3GHz",
    processor=processor,
    memory=memory,
    cache_hierarchy=cache_hiearchy
      
)

binary = CustomResource("../workload/cholesky/cholesky.bin")

board.set_se_binary_workload(binary)

simulator = Simulator(
            board=board,
            )
simulator.run()

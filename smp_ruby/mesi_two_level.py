#Copyright (c) 2020 The Regents of the University of California.
#All Rights Reserved

""" This file creates a set of Ruby caches for the MESI TWO Level protocol
This protocol models two level cache hierarchy. The L1 cache is split into
instruction and data cache.
This system support the memory size of up to 3GB.
"""
from __future__ import print_function
from __future__ import absolute_import
import math
from m5.defines import buildEnv
from m5.util import fatal, panic
from m5.objects import *

from gem5.coherence_protocol import CoherenceProtocol
from gem5.utils.override import overrides
from gem5.utils.requires import requires

from gem5.components.processors.abstract_core import AbstractCore


from m5.objects import (
    DMASequencer, # DMASequencer is a sequencer object that feeds requests to the DMA controller and receives responses from the DMA controller
    ClockDomain,
    MessageBuffer, # MessageBuffer is a simple message buffer object that stores the messages, all the requests and responses are transmitted through this buffer
    # Ruby objects
    RubyCache, # RubyCache is a simple cache memory object that stores the cache data and tags
    RubyPrefetcher, # RubyPrefetcher is a prefetcher object that is used to prefetch data into the cache
    RubyDirectoryMemory, # RubyDirectoryMemory is a directory memory object that stores the directory data and tags
    RubyPortProxy, # RubyPortProxy is a proxy port object that is used to load binaries and other functional-only things. Communication between the Ruby system and the rest of the system is done through this port.
    RubySequencer, # RubySequencer feeds requests to the cache memory object and receives responses from the cache memory object
    RubySystem, # RubySystem is the top-level Ruby object that contains all the Ruby objects
    # MESI Two Level
    MESI_Two_Level_L1Cache_Controller, # MESI_Two_Level_L1Cache_Controller is a controller object that manages the L1 cache
    MESI_Two_Level_L2Cache_Controller, # MESI_Two_Level_L2Cache_Controller is a controller object that manages the L2 cache
    MESI_Two_Level_DMA_Controller, # MESI_Two_Level_DMA_Controller is a controller object that manages the DMA controller
    MESI_Two_Level_Directory_Controller,  # MESI_Two_Level_Directory_Controller is a controller object that manages the directory controller   
    # NETWORK
    SimpleExtLink,
    SimpleIntLink,
    SimpleNetwork,
    Switch,
)



requires(coherence_protocol_required=CoherenceProtocol.MESI_TWO_LEVEL)

from gem5.isas import ISA
from gem5.components.boards.abstract_board import AbstractBoard
from gem5.components.cachehierarchies.abstract_cache_hierarchy import AbstractCacheHierarchy
from gem5.components.cachehierarchies.abstract_two_level_cache_hierarchy import AbstractTwoLevelCacheHierarchy
from gem5.components.cachehierarchies.ruby.abstract_ruby_cache_hierarchy import AbstractRubyCacheHierarchy



class MESITwoLevelCacheHierarchy(
    AbstractRubyCacheHierarchy, AbstractTwoLevelCacheHierarchy
):
    """A two level private L1 shared L2 MESI hierarchy.

    In addition to the normal two level parameters, you can also change the
    number of L2 banks in this protocol.

    The on-chip network is a point-to-point all-to-all simple network.
    """

    def __init__(
        self,
        l1i_size: str,
        l1i_assoc: str,
        l1d_size: str,
        l1d_assoc: str,
        l2_size: str,
        l2_assoc: str,
        num_l2_banks: int,
    ):
        AbstractRubyCacheHierarchy.__init__(self=self)
        AbstractTwoLevelCacheHierarchy.__init__(
            self,
            l1i_size=l1i_size,
            l1i_assoc=l1i_assoc,
            l1d_size=l1d_size,
            l1d_assoc=l1d_assoc,
            l2_size=l2_size,
            l2_assoc=l2_assoc,
        )

        self._num_l2_banks = num_l2_banks

    @overrides(AbstractCacheHierarchy)
    def get_coherence_protocol(self):
        return CoherenceProtocol.MESI_TWO_LEVEL

    def incorporate_cache(self, board: AbstractBoard) -> None:
        super().incorporate_cache(board)
        cache_line_size = board.get_cache_line_size()

        # Create the Ruby System, which is the root of all Ruby objects
        self.ruby_system = RubySystem()

        # MESI_Two_Level needs 3 virtual networks
        self.ruby_system.number_of_virtual_networks = 3

        # Create the network 
        self.ruby_system.network = SimplePt2Pt(self.ruby_system)
        self.ruby_system.network.number_of_virtual_networks = 3

        # For each core, create an L1 cache and connect it to the core. Also create sequencer for each L1 cache.
        self._l1_controllers = []
        for i, core in enumerate(board.get_processor().get_cores()):
            cache = L1Cache(
                self._l1i_size,
                self._l1i_assoc,
                self._l1d_size,
                self._l1d_assoc,
                self.ruby_system.network,
                core,
                self._num_l2_banks,
                cache_line_size,
                board.processor.get_isa(),
                board.get_clock_domain(),
            )

            cache.sequencer = RubySequencer(
                version=i,
                dcache=cache.L1Dcache,
                clk_domain=cache.clk_domain,
                ruby_system=self.ruby_system,
            )
            
            cache.ruby_system = self.ruby_system

            core.connect_icache(cache.sequencer.in_ports)
            core.connect_dcache(cache.sequencer.in_ports)

            if board.has_io_bus():
                cache.sequencer.connectIOPorts(board.get_io_bus())


            core.connect_walker_ports(
                cache.sequencer.in_ports, cache.sequencer.in_ports
            )

            # Connect the interrupt ports
            if board.get_processor().get_isa() == ISA.X86:
                int_req_port = cache.sequencer.interrupt_out_port
                int_resp_port = cache.sequencer.in_ports
                core.connect_interrupt(int_req_port, int_resp_port)
            else:
                core.connect_interrupt()

            self._l1_controllers.append(cache)

        # Create the L2 cache controllers
        self._l2_controllers = [
            L2Cache(
                self._l2_size,
                self._l2_assoc,
                self.ruby_system.network,
                self._num_l2_banks,
                cache_line_size,
            )
            for _ in range(self._num_l2_banks)
        ]
        
        for cache in self._l2_controllers:
            cache.ruby_system = self.ruby_system

        # For each memory port on the board, create a directory controller
        self._directory_controllers = [
            Directory(self.ruby_system.network, cache_line_size, range, port)
            for range, port in board.get_mem_ports()
        ]
        
        for dir in self._directory_controllers:
            dir.ruby_system = self.ruby_system

        # Create the DMA controllers
        self._dma_controllers = []
        if board.has_dma_ports():
            dma_ports = board.get_dma_ports()
            for i, port in enumerate(dma_ports):
                ctrl = DMAController(self.ruby_system.network, cache_line_size)
                ctrl.dma_sequencer = DMASequencer(
                    version=i,
                    in_ports=port,
                    ruby_system=self.ruby_system,
                )
                self._dma_controllers.append(ctrl)
                ctrl.ruby_system = self.ruby_system


        # Set up the system 
        self.ruby_system.num_of_sequencers = len(self._l1_controllers) + len(
            self._dma_controllers
        )


        self.ruby_system.l1_controllers = self._l1_controllers
        self.ruby_system.l2_controllers = self._l2_controllers
        self.ruby_system.directory_controllers = self._directory_controllers

        if len(self._dma_controllers) != 0:
            self.ruby_system.dma_controllers = self._dma_controllers

        # Create the network and connect the controllers.
        self.ruby_system.network.connectControllers(
            self._l1_controllers
            + self._l2_controllers
            + self._directory_controllers
            + self._dma_controllers
        )
        self.ruby_system.network.setup_buffers()

        # Set up a proxy port for the system_port. Used for load binaries and
        # other functional-only things.
        self.ruby_system.sys_port_proxy = RubyPortProxy(
            ruby_system=self.ruby_system
        )
        board.connect_system_port(self.ruby_system.sys_port_proxy.in_ports)

    @overrides(AbstractRubyCacheHierarchy)
    def _reset_version_numbers(self):
        Directory._version = 0
        L1Cache._version = 0
        L2Cache._version = 0
        DMAController._version = 0


class L1Cache(MESI_Two_Level_L1Cache_Controller):

    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1  # Use count for this particular type
        return cls._version - 1

    def __init__(
        self,
        l1i_size,
        l1i_assoc,
        l1d_size,
        l1d_assoc,
        network,
        core: AbstractCore,
        num_l2Caches,
        cache_line_size,
        target_isa: ISA,
        clk_domain: ClockDomain,
    ):
        """Creating L1 cache controller. Consist of both instruction
        and data cache.
        """
        super().__init__()

        self.version = self.versionCount()
        self._cache_line_size = cache_line_size
        self.connectQueues(network)

        # This is the cache memory object that stores the cache data and tags
        self.L1Icache = RubyCache(
            size=l1i_size,
            assoc=l1i_assoc,
            start_index_bit=int(math.log(self._cache_line_size, 2)),
            is_icache=True,
        )
        self.L1Dcache = RubyCache(
            size=l1d_size,
            assoc=l1d_assoc,
            start_index_bit=int(math.log(self._cache_line_size, 2)),
            is_icache=False,
        )
        self.l2_select_num_bits = int(math.log(num_l2Caches, 2))
        self.clk_domain = clk_domain
        self.prefetcher = RubyPrefetcher(block_size=self._cache_line_size)
        self.send_evictions = core.requires_send_evicts()
        self.transitions_per_cycle = 4
        self.enable_prefetch = False

    def connectQueues(self, network):
        self.mandatoryQueue = MessageBuffer()
        self.requestFromL1Cache = MessageBuffer()
        self.requestFromL1Cache.out_port = network.in_port
        self.responseFromL1Cache = MessageBuffer()
        self.responseFromL1Cache.out_port = network.in_port
        self.unblockFromL1Cache = MessageBuffer()
        self.unblockFromL1Cache.out_port = network.in_port

        self.optionalQueue = MessageBuffer()

        self.requestToL1Cache = MessageBuffer()
        self.requestToL1Cache.in_port = network.out_port
        self.responseToL1Cache = MessageBuffer()
        self.responseToL1Cache.in_port = network.out_port
    



class L2Cache(MESI_Two_Level_L2Cache_Controller):

    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1  # Use count for this particular type
        return cls._version - 1

    def __init__(
        self, l2_size, l2_assoc, network, num_l2Caches, cache_line_size
    ):
        super().__init__()

        self.version = self.versionCount()
        self._cache_line_size = cache_line_size
        self.connectQueues(network)

        # This is the cache memory object that stores the cache data and tags
        self.L2cache = RubyCache(
            size=l2_size,
            assoc=l2_assoc,
            start_index_bit=self.getIndexBit(num_l2Caches), 
        )

        self.transitions_per_cycle = 4

    def getIndexBit(self, num_l2caches):
        l2_bits = int(math.log(num_l2caches, 2))
        bits = int(math.log(self._cache_line_size, 2)) + l2_bits
        return bits

    def connectQueues(self, network):
        self.DirRequestFromL2Cache = MessageBuffer()
        self.DirRequestFromL2Cache.out_port = network.in_port
        self.L1RequestFromL2Cache = MessageBuffer()
        self.L1RequestFromL2Cache.out_port = network.in_port
        self.responseFromL2Cache = MessageBuffer()
        self.responseFromL2Cache.out_port = network.in_port
        self.unblockToL2Cache = MessageBuffer()
        self.unblockToL2Cache.in_port = network.out_port
        self.L1RequestToL2Cache = MessageBuffer()
        self.L1RequestToL2Cache.in_port = network.out_port
        self.responseToL2Cache = MessageBuffer()
        self.responseToL2Cache.in_port = network.out_port

class DMAController(MESI_Two_Level_DMA_Controller):

    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1  # Use count for this particular type
        return cls._version - 1

    def __init__(self, network, cache_line_size):
        super().__init__()
        self.version = self.versionCount()
        self._cache_line_size = cache_line_size
        self.connectQueues(network)

    def connectQueues(self, network):
        self.mandatoryQueue = MessageBuffer()
        self.responseFromDir = MessageBuffer(ordered=True)
        self.responseFromDir.in_port = network.out_port
        self.requestToDir = MessageBuffer()
        self.requestToDir.out_port = network.in_port


class Directory(MESI_Two_Level_Directory_Controller):

    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1  # Use count for this particular type
        return cls._version - 1

    def __init__(self, network, cache_line_size, mem_range, port):
        super().__init__()
        self.version = self.versionCount()
        self._cache_line_size = cache_line_size
        self.connectQueues(network)

        self.addr_ranges = [mem_range]
        self.directory = RubyDirectoryMemory(block_size=cache_line_size)
        # Connect this directory to the memory side.
        self.memory_out_port = port

    def connectQueues(self, network):
        self.requestToDir = MessageBuffer()
        self.requestToDir.in_port = network.out_port
        self.responseToDir = MessageBuffer()
        self.responseToDir.in_port = network.out_port
        self.responseFromDir = MessageBuffer()
        self.responseFromDir.out_port = network.in_port
        self.requestToMemory = MessageBuffer()
        self.responseFromMemory = MessageBuffer()






class SimplePt2Pt(SimpleNetwork):
    """A simple point-to-point network. This doesn't not use garnet."""

    def __init__(self, ruby_system):
        super().__init__()
        self.netifs = []

        # TODO: These should be in a base class
        # https://gem5.atlassian.net/browse/GEM5-1039
        self.ruby_system = ruby_system

    def connectControllers(self, controllers):
        """Connect all of the controllers to routers and connec the routers
        together in a point-to-point network.
        """
        # Create one router/switch per controller in the system
        self.routers = [Switch(router_id=i) for i in range(len(controllers))]

        # Make a link from each controller to the router. The link goes
        # externally to the network.
        self.ext_links = [
            SimpleExtLink(link_id=i, ext_node=c, int_node=self.routers[i])
            for i, c in enumerate(controllers)
        ]

        # Make an "internal" link (internal to the network) between every pair
        # of routers.
        link_count = 0
        int_links = []
        for ri in self.routers:
            for rj in self.routers:
                if ri == rj:
                    continue  # Don't connect a router to itself!
                link_count += 1
                int_links.append(
                    SimpleIntLink(link_id=link_count, src_node=ri, dst_node=rj)
                )
        self.int_links = int_links
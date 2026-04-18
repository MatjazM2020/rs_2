#!/usr/bin/env python3
"""
Network-aware cache hierarchy for interconnection network analysis.
Extends MESI_Two_Level with configurable network topologies.
"""

import sys
import os
import math

# Add gem5 build directory to Python path
gem5_possible_paths = [
    "/gem5/build/RISCV",
    "/opt/gem5/build/RISCV",
    "/usr/local/gem5/build/RISCV",
]
for gem5_path in gem5_possible_paths:
    if os.path.exists(gem5_path) and gem5_path not in sys.path:
        sys.path.insert(0, gem5_path)

# Try to import MESI classes with fallback error handling
_using_ruby = False
try:
    from m5.objects import (
        DMASequencer,
        ClockDomain,
        MessageBuffer,
        RubyCache,
        RubyPrefetcher,
        RubyDirectoryMemory,
        RubyPortProxy,
        RubySequencer,
        RubySystem,
        MESI_Two_Level_L1Cache_Controller,
        MESI_Two_Level_L2Cache_Controller,
        MESI_Two_Level_DMA_Controller,
        MESI_Two_Level_Directory_Controller,
        SimpleExtLink,
        SimpleIntLink,
        SimpleNetwork,
        Switch,
    )
    _using_ruby = True
    print(f"DEBUG: Ruby MESI classes imported successfully", file=sys.stderr)
except ImportError as e:
    # Try partial import and provide helpful error
    import m5.objects as m5_objs
    print(f"WARNING: Ruby MESI not available. Error: {e}", file=sys.stderr)
    print(f"DEBUG: Available MESI classes: {[n for n in dir(m5_objs) if 'MESI' in n]}", file=sys.stderr)
    print(f"WARNING: Using fallback classic cache hierarchy", file=sys.stderr)
    
    # Import what we can
    try:
        from m5.objects import (
            DMASequencer,
            ClockDomain,
            MessageBuffer,
            SimpleExtLink,
            SimpleIntLink,
            SimpleNetwork,
            Switch,
        )
    except:
        pass
    
    # Fall back to classic cache hierarchy
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'smp_classic'))
    try:
        from three_level import PrivateL1PrivateL2SharedL3CacheHierarchy
        print(f"DEBUG: Loaded classic cache hierarchy as fallback", file=sys.stderr)
    except ImportError as e2:
        print(f"ERROR: Could not load fallback classic cache hierarchy: {e2}", file=sys.stderr)
        raise ImportError("Ruby MESI protocol not available and fallback failed. Cannot create cache hierarchy.")

from gem5.coherence_protocol import CoherenceProtocol
from gem5.utils.override import overrides
from gem5.utils.requires import requires
from gem5.isas import ISA
from gem5.components.processors.abstract_core import AbstractCore
from gem5.components.boards.abstract_board import AbstractBoard
from gem5.components.cachehierarchies.abstract_cache_hierarchy import AbstractCacheHierarchy
from gem5.components.cachehierarchies.abstract_two_level_cache_hierarchy import AbstractTwoLevelCacheHierarchy
from gem5.components.cachehierarchies.ruby.abstract_ruby_cache_hierarchy import AbstractRubyCacheHierarchy


# Network topology classes (simplified from networks.py)
class SimplePt2Pt(SimpleNetwork):
    """Point-to-point network connecting every router to every other router."""

    def __init__(self, ruby_system):
        super().__init__()
        self.netifs = []
        self.ruby_system = ruby_system

    def connectControllers(self, controllers):
        self.routers = [Switch(router_id=i) for i in range(len(controllers))]
        
        self.ext_links = [
            SimpleExtLink(link_id=i, ext_node=c, int_node=self.routers[i])
            for i, c in enumerate(controllers)
        ]

        link_count = 0
        int_links = []
        for ri in self.routers:
            for rj in self.routers:
                if ri == rj:
                    continue
                link_count += 1
                int_links.append(
                    SimpleIntLink(link_id=link_count, src_node=ri, dst_node=rj)
                )
        self.int_links = int_links


class Ring(SimpleNetwork):
    """Ring network connecting routers in a circular topology."""

    def __init__(self, ruby_system):
        super().__init__()
        self.netifs = []
        self.ruby_system = ruby_system

    def connectControllers(self, controllers):
        self.routers = [Switch(router_id=i) for i in range(len(controllers))]
        
        self.ext_links = [
            SimpleExtLink(link_id=i, ext_node=c, int_node=self.routers[i])
            for i, c in enumerate(controllers)
        ]

        link_count = 0
        int_links = []
        for i in range(len(self.routers)):
            src_router = self.routers[i]
            dst_router = self.routers[(i + 1) % len(self.routers)]
            link_count += 1
            int_links.append(
                SimpleIntLink(link_id=link_count, src_node=src_router, dst_node=dst_router)
            )
        self.int_links = int_links


class Crossbar(SimpleNetwork):
    """Crossbar network with centralized switch."""

    def __init__(self, ruby_system):
        super().__init__()
        self.netifs = []
        self.ruby_system = ruby_system

    def connectControllers(self, controllers):
        # Create individual routers plus centralized crossbar
        self.routers = [Switch(router_id=i) for i in range(len(controllers) + 1)]
        xbar = self.routers[-1]

        self.ext_links = [
            SimpleExtLink(link_id=i, ext_node=c, int_node=self.routers[i])
            for i, c in enumerate(controllers)
        ]

        link_count = len(controllers)
        int_links = []

        for i in range(len(controllers)):
            # Link from router to crossbar
            int_links.append(
                SimpleIntLink(link_id=link_count, src_node=self.routers[i], dst_node=xbar)
            )
            link_count += 1

            # Link from crossbar to router
            int_links.append(
                SimpleIntLink(link_id=link_count, src_node=xbar, dst_node=self.routers[i])
            )
            link_count += 1

        self.int_links = int_links


# L1 Cache Controller
class L1Cache(MESI_Two_Level_L1Cache_Controller):
    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1
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
        super().__init__()

        self.version = self.versionCount()
        self._cache_line_size = cache_line_size
        self.connectQueues(network)

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


# L2 Cache Controller
class L2Cache(MESI_Two_Level_L2Cache_Controller):
    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1
        return cls._version - 1

    def __init__(
        self, l2_size, l2_assoc, network, num_l2Caches, cache_line_size
    ):
        super().__init__()

        self.version = self.versionCount()
        self._cache_line_size = cache_line_size
        self.connectQueues(network)

        self.L2cache = RubyCache(
            size=l2_size,
            assoc=l2_assoc,
            start_index_bit=self.getIndexBit(num_l2Caches),
        )

        self.transitions_per_cycle = 4

    def getIndexBit(self, num_l2caches):
        l2_bits = int(math.log(num_l2caches, 2)) if num_l2caches > 1 else 0
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


# DMA Controller
class DMAController(MESI_Two_Level_DMA_Controller):
    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1
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


# Directory Controller
class Directory(MESI_Two_Level_Directory_Controller):
    _version = 0

    @classmethod
    def versionCount(cls):
        cls._version += 1
        return cls._version - 1

    def __init__(self, network, cache_line_size, mem_range, port):
        super().__init__()
        self.version = self.versionCount()
        self._cache_line_size = cache_line_size
        self.connectQueues(network)

        self.addr_ranges = [mem_range]
        self.directory = RubyDirectoryMemory(block_size=cache_line_size)
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


# Network-aware cache hierarchy
class NetworkAwareCacheHierarchy(
    AbstractRubyCacheHierarchy, AbstractTwoLevelCacheHierarchy
):
    """Two-level cache hierarchy with configurable network topology."""

    def __init__(
        self,
        l1i_size: str,
        l1i_assoc: str,
        l1d_size: str,
        l1d_assoc: str,
        l2_size: str,
        l2_assoc: str,
        num_l2_banks: int,
        network_type: str = "point_to_point",
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
        self._network_type = network_type.lower()

    @overrides(AbstractCacheHierarchy)
    def get_coherence_protocol(self):
        return CoherenceProtocol.MESI_TWO_LEVEL

    def _create_network(self, ruby_system):
        """Create network based on type."""
        if self._network_type == "point_to_point":
            return SimplePt2Pt(ruby_system)
        elif self._network_type == "ring":
            return Ring(ruby_system)
        elif self._network_type == "crossbar":
            return Crossbar(ruby_system)
        else:
            raise ValueError(f"Unknown network type: {self._network_type}")

    def incorporate_cache(self, board: AbstractBoard) -> None:
        super().incorporate_cache(board)
        cache_line_size = board.get_cache_line_size()

        self.ruby_system = RubySystem()
        self.ruby_system.number_of_virtual_networks = 3

        # Create network based on type
        self.ruby_system.network = self._create_network(self.ruby_system)
        self.ruby_system.network.number_of_virtual_networks = 3

        # Create L1 controllers
        self._l1_controllers = []
        for i, core in enumerate(board.get_processor().get_cores()):
            L1_cache = L1Cache(
                self._l1i_size,
                self._l1i_assoc,
                self._l1d_size,
                self._l1d_assoc,
                self.ruby_system.network,
                core,
                self._num_l2_banks,
                cache_line_size,
                board.processor.get_isa(),
                board.clk_domain,
            )
            self._l1_controllers.append(L1_cache)
            core.connect_dcache(L1_cache.connectCachePorts)

        # Create L2 controllers
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
            cache.connectCachePort(self.ruby_system.network)

        # Create directory controllers
        self._directory_controllers = [
            Directory(self.ruby_system.network, cache_line_size, range, port)
            for range, port in board.get_mem_ports()
        ]

        for dir in self._directory_controllers:
            dir.connectCachePort(self.ruby_system.network)

        # Create DMA controllers if needed
        self._dma_controllers = []
        if board.has_dma_ports():
            for port in board.get_dma_ports():
                dma = DMAController(self.ruby_system.network, cache_line_size)
                self._dma_controllers.append(dma)
                dma.connectCachePort(self.ruby_system.network)

        # Configure system
        self.ruby_system.num_of_sequencers = len(self._l1_controllers) + len(
            self._dma_controllers
        )

        self.ruby_system.l1_controllers = self._l1_controllers
        self.ruby_system.l2_controllers = self._l2_controllers
        self.ruby_system.directory_controllers = self._directory_controllers

        if len(self._dma_controllers) != 0:
            self.ruby_system.dma_controllers = self._dma_controllers

        # Connect network
        self.ruby_system.network.connectControllers(
            self._l1_controllers
            + self._l2_controllers
            + self._directory_controllers
            + self._dma_controllers
        )
        self.ruby_system.network.setup_buffers()

        # Proxy port for system
        self.ruby_system.sys_port_proxy = RubyPortProxy(
            ruby_system=self.ruby_system
        )
        board.connect_system_port(self.ruby_system.sys_port_proxy.in_ports)

    @overrides(AbstractRubyCacheHierarchy)
    def _reset_version_numbers(self):
        L1Cache._version = 0
        L2Cache._version = 0
        DMAController._version = 0
        Directory._version = 0

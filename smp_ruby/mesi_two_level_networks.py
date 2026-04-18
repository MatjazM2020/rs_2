#Copyright (c) 2020 The Regents of the University of California.
#All Rights Reserved

"""
Extended MESI TWO Level Ruby cache hierarchy with support for different network topologies.
Supports point-to-point, ring, and crossbar network configurations.
Used for Task 3: Network topology performance analysis.
"""
from __future__ import print_function
from __future__ import absolute_import

import sys
import os
import math

# Import base MESI hierarchy
sys.path.insert(0, os.path.dirname(__file__))
from mesi_two_level import (
    MESITwoLevelCacheHierarchy,
    SimplePt2Pt,
    L1Cache,
    L2Cache,
    Directory,
    DMAController,
)

from gem5.components.boards.abstract_board import AbstractBoard
from gem5.utils.override import overrides
from m5.objects import (
    RubySystem,
    RubySequencer,
    RubyPortProxy,
    DMASequencer,
)
from gem5.isas import ISA


class MESITwoLevelCacheHierarchyWithNetworks(MESITwoLevelCacheHierarchy):
    """Extended MESI two-level cache hierarchy with configurable network topologies.
    
    Supports different interconnection networks:
    - SimplePt2Pt: Simple point-to-point all-to-all network
    - Ring: Ring network topology
    - Crossbar: Star/crossbar network topology
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
        network_type: str = "point_to_point",
    ):
        super().__init__(
            l1i_size=l1i_size,
            l1i_assoc=l1i_assoc,
            l1d_size=l1d_size,
            l1d_assoc=l1d_assoc,
            l2_size=l2_size,
            l2_assoc=l2_assoc,
            num_l2_banks=num_l2_banks,
        )
        self._network_type = network_type

    @overrides(MESITwoLevelCacheHierarchy)
    def incorporate_cache(self, board: AbstractBoard) -> None:
        """Incorporate cache with network topology support.
        
        Overrides parent's incorporate_cache to support different network topologies.
        Replicates all cache setup logic but with topology-specific network creation.
        """
        # Skip abstract base class call - we implement everything here
        # AbstractCacheHierarchy.incorporate_cache(self, board) would raise NotImplementedError
        
        cache_line_size = board.get_cache_line_size()

        # Create the Ruby System, which is the root of all Ruby objects
        self.ruby_system = RubySystem()

        # MESI_Two_Level needs 3 virtual networks
        self.ruby_system.number_of_virtual_networks = 3

        # Create the appropriate network based on network_type
        if self._network_type == "point_to_point":
            self.ruby_system.network = SimplePt2Pt(self.ruby_system)
        elif self._network_type == "ring":
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'network'))
            from networks import Circle
            self.ruby_system.network = Circle(self.ruby_system)
        elif self._network_type == "crossbar":
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'network'))
            from networks import Crossbar
            self.ruby_system.network = Crossbar(self.ruby_system)
        else:
            raise ValueError(f"Unknown network type: {self._network_type}")
        
        self.ruby_system.network.number_of_virtual_networks = 3

        # For each core, create an L1 cache and connect it to the core
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

        # Set up a proxy port for the system_port
        self.ruby_system.sys_port_proxy = RubyPortProxy(
            ruby_system=self.ruby_system
        )
        board.connect_system_port(self.ruby_system.sys_port_proxy.in_ports)

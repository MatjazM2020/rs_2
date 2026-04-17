
from m5.objects import (
    SimpleExtLink,
    SimpleIntLink,
    SimpleNetwork,
    Switch,
)

import math

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

class Circle(SimpleNetwork):
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
        for i in range(len(self.routers)):
            src_router = self.routers[i]
            dst_router = self.routers[(i + 1) % len(self.routers)]  # Connect to the next router in the circle
            if src_router != dst_router:  # Ensure the router is not connected to itself
                link_count += 1
                int_links.append(
                    SimpleIntLink(link_id=link_count, src_node=src_router, dst_node=dst_router)
                )
        self.int_links = int_links


class Mesh(SimpleNetwork):
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
        # Determine the dimensions of the mesh (assume a square mesh)
        mesh_size = int(math.sqrt(len(self.routers)))
        if mesh_size ** 2 != len(self.routers):
            raise ValueError("Number of controllers must be a perfect square for a mesh network.")

        for i in range(mesh_size):
            for j in range(mesh_size):
                router_id = i * mesh_size + j
                src_router = self.routers[router_id]

                # Connect to the router on the right (if it exists)
                if j < mesh_size - 1:
                    dst_router = self.routers[router_id + 1]
                    link_count += 1
                    int_links.append(
                    SimpleIntLink(link_id=link_count, src_node=src_router, dst_node=dst_router)
                    )

                # Connect to the router below (if it exists)
                if i < mesh_size - 1:
                    dst_router = self.routers[router_id + mesh_size]
                    link_count += 1
                    int_links.append(
                    SimpleIntLink(link_id=link_count, src_node=src_router, dst_node=dst_router)
                    )

        self.int_links = int_links


class Mesh_XY(SimpleNetwork):
    """A simple mesh network using XY routing."""

    def __init__(self, ruby_system):
        super().__init__()
        self.netifs = []
        self.ruby_system = ruby_system

    def connectControllers(self, controllers):
        """Connect all of the controllers to routers and connect the routers
        together in a mesh network using XY routing.
        """
        # Create one router/switch per controller in the system

        self.routers = [Switch(router_id=i) for i in range(len(controllers))]

        # Make a link from each controller to the router. The link goes
        # externally to the network.
        self.ext_links = [
            SimpleExtLink(link_id=i, ext_node=c, int_node=self.routers[i % len(self.routers)])
            for i, c in enumerate(controllers)
        ]

        # Create the mesh links
        link_count = 0
        int_links = []

        num_routers = len(self.routers)
        num_rows = int(math.sqrt(num_routers))
        num_columns = int(num_routers / num_rows)

        if num_columns * num_rows != num_routers:
            raise ValueError("Number of CPUs must be divisible by the number of rows.")

        # East output to West input links
        for row in range(num_rows):
            for col in range(num_columns):
                if col + 1 < num_columns:
                    src_router = self.routers[col + (row * num_columns)]
                    dst_router = self.routers[(col + 1) + (row * num_columns)]
                    link_count += 1
                    int_links.append(
                        SimpleIntLink(link_id=link_count, src_node=src_router, dst_node=dst_router)
                    )

        # West output to East input links
        for row in range(num_rows):
            for col in range(num_columns):
                if col + 1 < num_columns:
                    src_router = self.routers[(col + 1) + (row * num_columns)]
                    dst_router = self.routers[col + (row * num_columns)]
                    link_count += 1
                    int_links.append(
                        SimpleIntLink(link_id=link_count, src_node=src_router, dst_node=dst_router)
                    )

        # North output to South input links
        for col in range(num_columns):
            for row in range(num_rows):
                if row + 1 < num_rows:
                    src_router = self.routers[col + (row * num_columns)]
                    dst_router = self.routers[col + ((row + 1) * num_columns)]
                    link_count += 1
                    int_links.append(
                        SimpleIntLink(link_id=link_count, src_node=src_router, dst_node=dst_router)
                    )

        # South output to North input links
        for col in range(num_columns):
            for row in range(num_rows):
                if row + 1 < num_rows:
                    src_router = self.routers[col + ((row + 1) * num_columns)]
                    dst_router = self.routers[col + (row * num_columns)]
                    link_count += 1
                    int_links.append(
                        SimpleIntLink(link_id=link_count, src_node=src_router, dst_node=dst_router)
                    )

        self.int_links = int_links


class Crossbar(SimpleNetwork):
    """A simple crossbar network."""

    def __init__(self, ruby_system):
        super().__init__()
        self.netifs = []
        self.ruby_system = ruby_system

    def connectControllers(self, controllers):
        """Connect all of the controllers to a centralized crossbar router."""
        # Create an individual router for each controller plus one more for
        # the centralized crossbar.
        self.routers = [Switch(router_id=i) for i in range(len(controllers) + 1)]
        xbar = self.routers[-1]  # the crossbar router is the last router created

        # Make a link from each controller to its corresponding router.
        self.ext_links = [
            SimpleExtLink(link_id=i, ext_node=c, int_node=self.routers[i])
            for i, c in enumerate(controllers)
        ]

        # Create internal links between each router and the crossbar.
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

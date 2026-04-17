# Second homework assignment


## Assessing performance of a snooping based cache coherence protocol (3 points)

In this assignment, you will analyze the performance of a snooping-based cache coherence protocol in a multiprocessor system. The snooping protocol is a widely used mechanism for maintaining cache coherence, allowing multiple processors to have a consistent view of memory by monitoring (or "snooping") the bus for memory transactions. You will specifically assess the performance of Cholesky decomposition in a multiprocessor system utilizing this snooping-based cache coherence protocol. Cholesky decomposition is a numerical method used to factor a symmetric positive-definite matrix into the product of a lower triangular matrix and its conjugate transpose.

To evaluate the performance of the snooping-based cache coherence protocol, you will use the Cholesky decomposition implementation provided in the `workload/cholesky/` directory. For the GEM5 model, you will utilize the Python scripts located in the `smp_classic/` directory to model the multiprocessor system with a snooping-based cache coherence protocol. The script `smp_benchmark/smp_benchmark.py` contains the implementation of this protocol and is based on the M5 memory system in GEM5.

### Experiment Setup:

1. Assess performance for a number of processors: 2, 4, 8, and 16.
2. Run the Cholesky decomposition program for each configuration.
3. Measure the following metrics connected to performance:
   - CPI (Cycles Per Instruction) for each CPU: Provide mean and standard deviation for each CPU
   - L1 cache miss ratio per core (`l1d_cache.overallMisses::total`, `l1d_cache.overallHits::total`): Provide mean and standard deviation for each L1 cache
   - Number of upgrade requests at L3 cache (`l3_bus.transDist::UpgradeReq`)
   - Snoop traffic (`l3_bus.snoopTraffic`)


- Parameters of cache hierarchy:
   - L1 cache: 32KB, 8-way set associative, 64B cache line size
   - L2 cache: 256KB, 8-way set associative, 64B cache line size 
   - L1 and L2 cache are private to each core
   - L3 cache: 2MB, 16-way set associative, 64B cache line size

 

## Assessing the impact of false sharing on performance in directory based cache coherence protocols (4 points)

False sharing can arise when multiple processors access different data items stored in the same cache line. This situation can lead to unnecessary invalidations and increased memory traffic, ultimately degrading performance. Your task is to analyze the impact of false sharing on the performance of a directory-based cache coherence protocol. For this analysis, you will use the multithreaded version of a program that computes the parallel prefix sum of an array. Both program versions—one with false sharing and one without—are available in the `workload/prefix_sum/` directory.

To evaluate the impact of false sharing, you must run both program versions on a simulated system that utilizes a directory-based cache coherence protocol, specifically using the gem5 simulator. The Python scripts that model the SMP system with gem5 can be found in the `smp_ruby/` directory. You will assess the system's performance by varying the number of processors and observing the effects on execution time and memory traffic. Additionally, you should analyze the cache coherence protocol's behavior in relation to invalidations and memory accesses.

### Experiment Setup:

1. Set the number of processors to 2, 4, 8, and 16.
2. Run the program with and without false sharing for each configuration.
3. To observe the impact of false sharing, observe following metrics:
   - CPI (Cycles Per Instruction): Provide mean and standard deviation for each CPU
   - Execution time
   - Number of invalidations (`ruby_system.L1Cache_Controller.Inv::total`)
   - Number of loads under different states (`L1Cache_Controller.I.Load::total`, `L1Cache_Controller.S.Load::total`, `L1Cache_Controller.E.Load::total`, `L1Cache_Controller.M.Load::total`)
   - Number of read and write requests towards the L2 cache (`L2Cache_Controller.L1_GETS`, `L2Cache_Controller.L1_GETX`)
   - Network traffic ( `network.msg_count.Request_Control`, `network.msg_count.Response_Data`, `network.msg_count.Writeback_Data`)


- Parameters of cache hierarchy:
  - L1 cache: 32KB, 8-way set associative, 64B cache line size
  - L2 cache: 256KB, 8-way set associative, 64B cache line size
  - Number of L2 cache banks: 1



## Assessing the performance of interconnection network (3 points)

In NUMA (Non-Uniform Memory Access) systems, the interconnection network plays a crucial role in the overall performance of the system. In this assignment, you will analyze the performance of a multiprocessor system with three different types of interconnection networks: crossbar-based (or star-based), ring, and simple point-to-point networks.

For this assignment, we implemented one kernel that executes the DAXPY operation on two arrays. The DAXPY operation, a common vector operation in scientific computing, is defined as follows:

```
y[i] = a * x[i] + y[i]
```

Here, `a` is a scalar value, while `x` and `y` are arrays of floating-point numbers, and `i` represents the index of the arrays. The DAXPY operation is frequently used to benchmark and evaluate the performance of memory systems.

You can find the implementation of the DAXPY kernel in the folder `workload/stream/`. This implementation is written in C and employs OpenMP to parallelize computations across multiple threads, designed to run on a multiprocessor system with shared memory architecture.

Regarding the GEM5 model, you will use the Python scripts located in the `network/` directory to model the multiprocessor system with different interconnection networks. Specifically, the Python script `network/networks.py` contains the implementations of these various interconnection networks and is based on the Simple Network class, which provides a basic framework for a network interface and network switch. The script includes the following classes:

- **SimplePt2Pt Network**: This class implements a simple point-to-point network, connecting two nodes through a single switch, and provides a straightforward interface for sending and receiving messages.
- **Circle Network**: This class establishes a ring network that connects multiple nodes in a circular topology, utilizing a series of switches to link the nodes and offering a simple interface for communication.
- **Crossbar Network**: This class creates a crossbar network, connecting multiple nodes in a star topology. It uses a series of switches to interconnect the nodes and provides an easy-to-use interface for message transmission.

### Experiment Setup:
1. Set the number of processors to 2, 4, 8, and 16.
2. Run the DAXPY kernel on each interconnection network (crossbar, ring, and point-to-point) for each configuration.
3. Measure the following metrics connected to network performance:
   - Network traffic ( `network.msg_count.Request_Control`, `network.msg_count.Response_Data`, `network.msg_count.Writeback_Data`)

- Parameters of cache hierarchy:
  - L1 cache: 32KB, 8-way set associative, 64B cache line size
  - L2 cache: 256KB, 8-way set associative, 64B cache line size
  - Number of L2 cache banks: 1


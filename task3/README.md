# Task 3: Network Topology Performance Analysis

## Overview
This task analyzes the performance of different interconnection network topologies in a multiprocessor system using the gem5 simulator. We test three network types (point-to-point, ring, and crossbar) with varying processor counts (2, 4, 8, 16) while running the DAXPY kernel workload.

## Network Topologies

### Point-to-Point Network
- **Description**: All-to-all connected network where every router can communicate directly with every other router.
- **Characteristics**: Low latency for point-to-point communication but high complexity as core count grows.
- **Use case**: Small systems with known communication patterns.

### Ring Network
- **Description**: Routers connected in a circular topology, where each router connects to its neighbors.
- **Characteristics**: Simple structure with scalable links, but higher latency for distant communicating nodes.
- **Use case**: Systems prioritizing scalability over minimum latency.

### Crossbar Network
- **Description**: Centralized crossbar switch connecting all routers to a central arbitration point.
- **Characteristics**: Low latency but potential bottleneck at the central switch.
- **Use case**: Systems with high-bandwidth centralized access patterns.

## Files

- **network_cache_hierarchy.py**: Defines the network-aware cache hierarchy with support for three network topologies. Implements MESI_Two_Level protocol with configurable network types.

- **run_network_sim.py**: Single simulation runner that accepts command-line arguments for:
  - `--cores`: Number of CPU cores (2, 4, 8, or 16)
  - `--network`: Network type (point_to_point, ring, or crossbar)
  - `--binary-path`: Path to DAXPY binary
  - `--output-dir`: Output directory for simulation results

- **run_all_network_experiments.py**: Experiment driver that runs all combinations of network types and core counts, collects metrics, and generates a summary report.

- **analyze_results.py**: Post-processing script to extract metrics and generate analysis.

## Usage

### Single Simulation
```bash
# Running from container or with gem5 installed
python3 run_network_sim.py \
    --cores 4 \
    --network crossbar \
    --binary-path /path/to/stream.bin \
    --output-dir ./results/test_crossbar_4cores
```

### Run All Experiments
```bash
python3 run_all_network_experiments.py
```
This will run all 12 simulations (3 networks × 4 core counts) and generate a summary.

### SLURM Job Submission
```bash
sbatch submit_job_task3.sh
```
This submits the complete experiment suite to the HPC cluster.

## Metrics Collected

The simulation collects the following network traffic metrics:
- **network.msg_count.Request_Control**: Number of control request messages
- **network.msg_count.Response_Data**: Number of data response messages
- **network.msg_count.Writeback_Data**: Number of writeback data messages

## Cache Configuration

All simulations use the same cache hierarchy:
- **L1 Cache**: 32KB, 8-way set associative, 64B cache line
- **L2 Cache**: 256KB, 8-way set associative, 64B cache line
- **Number of L2 banks**: 1

## Output

Results are organized as:
```
results/task3_YYYYMMDD_HHMMSS/
├── point_to_point/
│   ├── cores_2/stats.txt
│   ├── cores_4/stats.txt
│   ├── cores_8/stats.txt
│   └── cores_16/stats.txt
├── ring/
│   ├── cores_2/stats.txt
│   ├── cores_4/stats.txt
│   ├── cores_8/stats.txt
│   └── cores_16/stats.txt
├── crossbar/
│   ├── cores_2/stats.txt
│   ├── cores_4/stats.txt
│   ├── cores_8/stats.txt
│   └── cores_16/stats.txt
└── summary.txt
```

## Expected Behavior

### Point-to-Point Network
- Lowest latency due to direct connections
- Higher network traffic proportional to core count squared (O(n²))
- Best for small systems with uniform communication

### Ring Network
- Linear increase in network links with core count (O(n))
- Higher latency for distant nodes (O(n) hops in worst case)
- Better scalability to larger systems

### Crossbar Network
- Low uniform latency to central switch
- Potential bottleneck at crossbar as traffic increases
- Good for systems with bursty communication patterns

## Notes

- The DAXPY workload is a data-parallel operation with regular communication patterns
- All simulations use TIMING CPU model for accurate memory system simulation
- Results should be analyzed for network utilization, latency trends, and scalability characteristics

# Task 2: False Sharing Impact Analysis

## Overview
This task analyzes the impact of false sharing on performance of a directory-based cache coherence protocol (MESI_TWO_LEVEL) using gem5 simulator.

## Scripts

### 1. `run_false_sharing_sim.py`
Main simulation runner that executes a single configuration.

**Usage:**
```bash
python3 run_false_sharing_sim.py \
    --cores <2|4|8|16> \
    --variant <falsesharing|optimized> \
    --binary-dir <path_to_binaries> \
    --output-dir <path_to_output>
```

**Parameters:**
- `--cores`: Number of CPU cores (must be 2, 4, 8, or 16)
- `--variant`: Binary variant (falsesharing with false sharing or optimized without)
- `--binary-dir`: Directory containing pprefix_*.bin binaries
- `--output-dir`: Directory where gem5 output will be stored

**Output:**
- Creates subdirectory: `{variant}_cores{N}/`
- Contains gem5 output files including `stats.txt`

### 2. `run_all_experiments.py`
Orchestrates all simulation configurations (2×4 = 8 experiments).

**Usage:**
```bash
python3 run_all_experiments.py
```

**Configurations:**
- Core counts: 2, 4, 8, 16
- Variants: falsesharing, optimized
- Total simulations: 8

**Output:**
- All simulation results in `results/task2/`
- Automatically runs analysis and generates reports

### 3. `analyze_results.py`
Extracts key metrics from gem5 stats files and generates analysis reports.

**Usage:**
```bash
python3 analyze_results.py <results_directory> [output_base]
```

**Parameters:**
- `results_directory`: Path to directory with simulation outputs
- `output_base`: (Optional) Base path for reports (default: results_directory)

**Extracted Metrics:**
- **CPI**: Mean and standard deviation per CPU
- **Execution time**: Total execution time in seconds (calculated from total cycles)
- **Invalidations**: Total cache invalidations (`ruby_system.L1Cache_Controller.Inv::total`)
- **Loads by state**: I, S, E, M states (`L1Cache_Controller.{state}.Load::total`)
- **L2 requests**: L1_GETS and L1_GETX requests
- **Network traffic**: Request_Control, Response_Data, Writeback_Data messages

**Output:**
- `false_sharing_analysis.csv`: Tabular report
- `false_sharing_analysis.json`: Structured data
- Console summary with key findings

## Workflow

### Local Testing
```bash
# Run single configuration
python3 run_false_sharing_sim.py \
    --cores 2 \
    --variant falsesharing \
    --binary-dir ../workload/parallel_prefix \
    --output-dir ../results/task2

# Analyze results
python3 analyze_results.py ../results/task2
```

### HPC Submission
```bash
# Submit to SLURM
sbatch ../submit_job_task2.sh

# Monitor
tail -f task2_log_*.txt
```

## Expected Results

### Key Findings
- **False sharing variant** should show:
  - Higher invalidation rates
  - More cache-to-cache transfers
  - Higher CPI due to cache misses
  
- **Optimized variant** should show:
  - Significantly lower invalidations
  - Better cache locality
  - Lower CPI

### Scaling Behavior
- Performance degradation with more cores due to increased coherence traffic
- False sharing effect amplified as core count increases
- Network traffic growth reflects cache coherence communication

## Cache Hierarchy Configuration

```
L1 Cache:
  - Size: 32KB per core (split I/D)
  - Associativity: 8-way
  - Cache line: 64B

L2 Cache:
  - Size: 256KB (shared, 1 bank)
  - Associativity: 8-way
  - Cache line: 64B

Protocol: MESI_TWO_LEVEL (directory-based)
Processors: TIMING CPUs
ISA: RISCV
Memory: 4GB DDR3-1600
Frequency: 3GHz
```

## Output Files Structure

```
results/task2/
├── falsesharing_cores2/
│   └── stats.txt
├── falsesharing_cores4/
│   └── stats.txt
├── ... (other configurations)
├── false_sharing_analysis.csv
└── false_sharing_analysis.json
```

## Troubleshooting

### Simulation Fails
- Check binary paths: `ls ../workload/parallel_prefix/pprefix_*.bin`
- Verify gem5 installation: Check GEM5_WORKSPACE path
- Check container availability: `apptainer --version`

### Stats Parsing Issues
- Ensure stats.txt exists in output directory
- Check gem5 version compatibility
- Verify metric names in stats.txt

### Memory/Timeout Issues
- Increase SLURM time: Modify `--time` in submit_job_task2.sh
- Reduce simulations: Edit CORE_COUNTS in run_all_experiments.py
- Check HPC queue status: `squeue -u $(whoami)`

## References

- Cache Hierarchy: `../smp_ruby/mesi_two_level.py`
- Binary Sources: `../workload/parallel_prefix/`
- SLURM Submission: `../submit_job_task2.sh`

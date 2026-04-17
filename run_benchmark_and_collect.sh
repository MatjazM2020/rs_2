#!/usr/bin/env bash
#SBATCH --job-name=rs_hw2
#SBATCH --output=log.txt     
#SBATCH --reservation=fri
#SBATCH --cpus-per-task=16
#SBATCH --ntasks=1
#SBATCH --time=00:15:00

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./run_benchmark_and_collect.sh <folder_name> <benchmark_folder> <param1> <param2> ...

What it does:
  - Creates results/<folder_name> relative to the directory where you run the script
  - Copies all .py files from <benchmark_folder> into that results folder
  - Finds the single file ending with benchmark.py in the copied files
  - Runs that benchmark file from results/<folder_name>
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

GEM5_WORKSPACE=/d/hpc/projects/FRI/GEM5/gem5_workspace
GEM5_ROOT=$GEM5_WORKSPACE/gem5
GEM_PATH=$GEM5_ROOT/build/RISCV
RESULT_NAME="$1"
SOURCE_FOLDER="$2"
shift 2
BENCHMARK_ARGS=("$@")
BASE_DIR="$PWD"
SOURCE_DIR="${BASE_DIR}/${SOURCE_FOLDER}"
RESULT_DIR="${BASE_DIR}/results/${RESULT_NAME}"

check_create_folders() {
  if [[ ! -d "${SOURCE_DIR}" ]]; then
    echo "Error: folder not found: ${SOURCE_DIR}" >&2
    exit 1
  fi

  mapfile -t PY_FILES < <(find "${SOURCE_DIR}" -maxdepth 1 -type f -name '*.py' | sort)

  if [[ ${#PY_FILES[@]} -eq 0 ]]; then
    echo "Error: no .py files found in ${SOURCE_DIR}" >&2
    exit 1
  fi

  mapfile -t BENCHMARK_FILES < <(find "${SOURCE_DIR}" -maxdepth 1 -type f -name '*benchmark.py' | sort)

  if [[ ${#BENCHMARK_FILES[@]} -ne 1 ]]; then
    echo "Error: expected exactly one *benchmark.py file in ${SOURCE_DIR}" >&2
    printf 'Found: %s\n' "${BENCHMARK_FILES[@]:-none}" >&2
    exit 1
  fi

  BENCHMARK_BASENAME="$(basename "${BENCHMARK_FILES[0]}")"

  rm -rf "${RESULT_DIR}"
  mkdir -p "${RESULT_DIR}"

  for py_file in "${PY_FILES[@]}"; do
    cp "${py_file}" "${RESULT_DIR}/"
  done
}

run_benchmark() {
  echo "Running ${BENCHMARK_BASENAME} from ${SOURCE_DIR}"
  set +e
  ( cd "${SOURCE_DIR}" && srun apptainer exec "$GEM5_WORKSPACE/gem5_rv.sif" "$GEM_PATH/gem5.opt" "${BENCHMARK_BASENAME}" "${BENCHMARK_ARGS[@]}" )
  local run_status=$?
  set -e

  if [[ ${run_status} -ne 0 ]]; then
    echo "Error: benchmark execution failed (exit code ${run_status})." >&2
    echo "Reason: stats copy runs only after a successful benchmark run." >&2
    echo "Check Slurm output in log.txt for the underlying error." >&2
  fi

  sleep 1

  local stats_file="${SOURCE_DIR}/m5out/stats.txt"
  if [[ ! -f "${stats_file}" ]]; then
    echo "Error: expected generated stats file not found: ${stats_file}" >&2
    exit 1
  fi

  cp "${stats_file}" "${RESULT_DIR}/"
}

check_create_folders
run_benchmark

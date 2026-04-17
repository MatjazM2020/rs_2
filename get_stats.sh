#!/usr/bin/env bash

# Script to find and return rows from a stats.txt file
# Usage: ./get_stats.sh <directory> <stat_name> [<stat_name>...]
# Example: ./get_stats.sh results/1-2cores l1d_cache.prefetcher.pfIssued

# Check if we have the minimum required arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <directory> <stat_name> [<stat_name>...]"
    echo "Example: $0 results/1-2cores l1d_cache.prefetcher.pfIssued"
    exit 1
fi

dir=$1
shift
stats=("$@")

# Find the stats.txt file in the directory
stats_file=$(find "$dir" -name "stats.txt" 2>/dev/null | head -1)

if [ -z "$stats_file" ]; then
    echo "Error: stats.txt not found in $dir" >&2
    exit 1
fi

# Search for each stat and return matching lines
for stat in "${stats[@]}"; do
    grep "$stat" "$stats_file"
done


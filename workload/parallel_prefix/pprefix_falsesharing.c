// false_sharing_prefix_sum_omp.c
// Parallel Prefix Sum (Scan) — version with false sharing with OpenMP


#include <stdio.h>
#include <stdlib.h>
#include <omp.h>
#define ARRAY_SIZE   (1 << 16)   
// Include the gem5 m5ops header file
#include <gem5/m5ops.h>

int  *input;
long *output;

// Plain array — all slots likely share the same cache line(s)
// sizeof(long) = 8 bytes, cache line = 64 bytes → 8 longs = 1 cache line

//get number of threads


int main(void) {
    input  = malloc(ARRAY_SIZE * sizeof(int));
    output = malloc(ARRAY_SIZE * sizeof(long));
    for (long i = 0; i < ARRAY_SIZE; i++) input[i] = 1;

    // Initialize OpenMP
    // get number of threads
    int num_threads = omp_get_max_threads();
    omp_set_num_threads(num_threads);
    long chunk = ARRAY_SIZE / num_threads;

    long *partial = malloc(num_threads * sizeof(long));   // shared array for per-thread sums — likely false sharing

    double t0 = omp_get_wtime();

    #ifdef GEM5
        m5_reset_stats(0,0);
    #endif
    // --- Phase 1: parallel reduce ---
    // Each thread reduces its chunk and writes to partial[id]
    #pragma omp parallel
    {
        int id    = omp_get_thread_num();
        long start = id * chunk;
        long end   = (id == num_threads - 1) ? ARRAY_SIZE : start + chunk;

        long sum = 0;
        for (long i = start; i < end; i++)
            partial[id]  += input[i];  // ← false sharing: all threads hammer same cache line
    }

    #ifdef GEM5
        m5_dump_stats(0,0);
    #endif
    // --- Serial step: convert per-thread sums into base offsets ---
    long running = 0;
    for (int i = 0; i < num_threads; i++) {
        long chunk_sum = partial[i];
        partial[i]     = running;
        running       += chunk_sum;
    }


    // --- Phase 2: parallel scan write ---
    // Each thread reads its base offset from partial[] and scans its chunk
    #pragma omp parallel
    {
        int id     = omp_get_thread_num();
        long start = id * chunk;
        long end   = (id == num_threads - 1) ? ARRAY_SIZE : start + chunk;
        long base  = partial[id];   // ← reading partial[] — stresses the same cache line

        output[start] = base + input[start];
        for (long i = start + 1; i < end; i++)
            output[i] = output[i-1] + input[i];
    }


    double ms = (omp_get_wtime() - t0) * 1e3;

    // Verify correctness (output[i] should equal i+1 for all-ones input)
    int ok = 1;
    for (long i = 0; i < ARRAY_SIZE; i++) {
        if (output[i] != i + 1) { ok = 0; break; }
    }


    free(input);
    free(output);
    return 0;
}

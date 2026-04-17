// fixed_prefix_sum_omp.c
// Parallel Prefix Sum (Scan) — version with no false sharing with OpenMP


#include <stdio.h>
#include <stdlib.h>
#include <omp.h>
// Include the gem5 m5ops header file
#include <gem5/m5ops.h>


#define ARRAY_SIZE   (1 << 16)   // 64 M elements
#define CACHE_LINE   64

int  *input;
long *output;

// Each slot padded to its own cache line — zero inter-thread interference
typedef struct {
    long value;
    char _pad[CACHE_LINE - sizeof(long)];   // 56 bytes padding
} __attribute__((aligned(CACHE_LINE))) PaddedLong;


int main(void) {
    input  = malloc(ARRAY_SIZE * sizeof(int));
    output = malloc(ARRAY_SIZE * sizeof(long));
    for (long i = 0; i < ARRAY_SIZE; i++) input[i] = 1;

    // get number of threads
    int num_threads = omp_get_max_threads();
    omp_set_num_threads(num_threads);

    PaddedLong *partial = malloc(num_threads * sizeof(PaddedLong));   // shared array for per-thread sums — no false sharing

    printf("Running with %d threads...\n", num_threads);

    long chunk = ARRAY_SIZE / num_threads;

    double t0 = omp_get_wtime();
     #ifdef GEM5
        m5_reset_stats(0,0);
    #endif
    // --- Phase 1: parallel reduce ---
    // Each thread reduces its chunk into its own private cache line
    #pragma omp parallel
    {
        int  id    = omp_get_thread_num();
        long start = id * chunk;
        long end   = (id == num_threads - 1) ? ARRAY_SIZE : start + chunk;

        long sum = 0;
        for (long i = start; i < end; i++)
            partial[id].value += input[i];

    }

    #ifdef GEM5
        m5_dump_stats(0,0);
    #endif

    // --- Serial step: convert per-thread sums into base offsets ---
    long running = 0;
    for (int i = 0; i < num_threads; i++) {
        long chunk_sum    = partial[i].value;
        partial[i].value  = running;   // base offset for this thread's output chunk
        running          += chunk_sum;
    }

   
    // --- Phase 2: parallel scan write ---
    // Each thread reads only its own cache line for the base offset
    #pragma omp parallel
    {
        int  id    = omp_get_thread_num();
        long start = id * chunk;
        long end   = (id == num_threads - 1) ? ARRAY_SIZE : start + chunk;
        long base  = partial[id].value;   // reads only its own cache line

        output[start] = base + input[start];
        for (long i = start + 1; i < end; i++)
            output[i] = output[i-1] + input[i];
    }


    double ms = (omp_get_wtime() - t0) * 1e3;

    printf("Time: %.3f ms\n", ms);
    // Verify correctness (output[i] should equal i+1 for all-ones input)
    int ok = 1;
    for (long i = 0; i < ARRAY_SIZE; i++) {
        if (output[i] != i + 1) { ok = 0; break; }
    }


    free(input);
    free(output);
    return 0;
}

#include <stdio.h>
#include <stdlib.h>
#include <gem5/m5ops.h>

void set_array(double *array, size_t size, double value) {
    for (size_t i = 0; i < size; i++) {
        array[i] = value;
    }
}

void stream_triad(double *a, double *b, double *c, size_t size, double scalar) {
    for (size_t i = 0; i < size; i++) {
        a[i] = b[i] + scalar * c[i];
    }
}

int main() {
    size_t array_size = 1000000;
    double *a = (double *)malloc(array_size * sizeof(double));
    double *b = (double *)malloc(array_size * sizeof(double));
    double *c = (double *)malloc(array_size * sizeof(double));
    if (a == NULL || b == NULL || c == NULL) {
        fprintf(stderr, "Memory allocation failed\n");
        free(a);
        free(b);
        free(c);
        return 1;
    }

    double scalar = 3.14;

    // Initialize arrays
    set_array(a, array_size, 0.0);
    set_array(b, array_size, 1.0);
    set_array(c, array_size, 2.0);

    // Reset gem5 stats before main workload
    #ifdef GEM5
        m5_reset_stats(0,0);
    #endif

    // Perform STREAM triad operation
    stream_triad(a, b, c, array_size, scalar);

    // Dump stats after workload completes
    #ifdef GEM5
        m5_dump_stats(0,0);
    #endif

    // Verify the first few elements
    for (size_t i = 0; i < 10; i++) {
        printf("a[%zu] = %f\n", i, a[i]);
    }

    // Free memory
    free(a);
    free(b);
    free(c);

    return 0;
}

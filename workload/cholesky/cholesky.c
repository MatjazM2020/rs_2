#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <omp.h>
#include <time.h>
// Include the gem5 m5ops header file
#include <gem5/m5ops.h>



#define N 100  // Matrix size (adjustable)

// Function to print matrix
void print_matrix(double** M) {
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++)
            printf("%7.4f ", M[i][j]);
        printf("\n");
    }
}




// Function to generate a symmetric positive definite (SPD) matrix
void generate_spd_matrix(double** A) {
    double temp[N][N] = {0};  // Temporary matrix to hold random values

    // Fill temp with random values
    srand(time(NULL));
    for (int i = 0; i < N; i++) {
        for (int j = i; j < N; j++) {  // Only fill the upper triangle
            temp[j][i] = 4 ;  // Random values between 1 and 10
        }
    }


    // Create SPD matrix A = temp * temp^T
    #pragma omp parallel for collapse(2)
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            A[i][j] = 0.0;
            for (int k = 0; k < N; k++) {
                A[i][j] += temp[i][k] * temp[j][k];  // Ensures symmetry and positive definiteness
            }
        }
    }
}

// Function to perform Cholesky decomposition using OpenMP
void cholesky_decomposition(double** A, double** L) {
    int i, j, k;

    // Initialize L matrix to zeros
    #pragma omp parallel for collapse(2) schedule(static)
    for (i = 0; i < N; i++)
        for (j = 0; j < N; j++)
            L[i][j] = 0.0;

    // Cholesky decomposition
    for (i = 0; i < N; i++) {
        double sum = 0.0;

        // Compute diagonal element
        #pragma omp parallel for reduction(+:sum) schedule(static)
        for (k = 0; k < i; k++)
            sum += L[i][k] * L[i][k];
        L[i][i] = sqrt(A[i][i] - sum);

        // Compute off-diagonal elements
        #pragma omp parallel for schedule(static)
        for (j = i + 1; j < N; j++) {
            double local_sum = 0.0;
            for (k = 0; k < i; k++)
                local_sum += L[j][k] * L[i][k];
            L[j][i] = (A[j][i] - local_sum) / L[i][i];
        }
    }
}


int main() {

    // Allocate matrices dynamically
    double** A = (double**)malloc(N * sizeof(double*));
    double** L = (double**)malloc(N * sizeof(double*));
    for (int i = 0; i < N; i++) {
        A[i] = (double*)malloc(N * sizeof(double));
        L[i] = (double*)malloc(N * sizeof(double));
    }

    // get number of threads
    int num_threads = omp_get_max_threads();

    omp_set_num_threads(num_threads);

    printf("Number of threads: %d\n", num_threads);
    // Generate SPD matrix
    generate_spd_matrix(A);

    printf("Generated Symmetric Positive Definite Matrix A:\n");
    
  


    #ifdef GEM5
	// m5_work_begin(work_id, thread_id) -- begin a item sample
    m5_work_begin(0, 0);
	#endif
    // Perform Cholesky Decomposition
    cholesky_decomposition(A, L);
    
    #ifdef GEM5
	    m5_work_end(0, 0);
	#endif

    printf("\nCholesky Decomposed Matrix L:\n");
    print_matrix(L);

    // Free allocated memory
    for (int i = 0; i < N; i++) {
        free(A[i]);
        free(L[i]);
    }
    free(A);
    free(L);

    return 0;
}

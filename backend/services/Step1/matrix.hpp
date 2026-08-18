#pragma once
#include <vector>
#include <stdexcept>
#include <random>
#include <cmath>
#include <algorithm>

struct Matrix {
    int rows;
    int columns;
    std::vector<double> row_values; //flat storage for cache optimisation

    // Empty 0x0 matrix. Lets Matrix be a member that gets assigned a real
    // matrix later (e.g. a Layer's cache, sized on the first forward pass).
    Matrix() : rows(0), columns(0) {}

    // Build from existing values.
    explicit Matrix(int r, int c, std::vector<double> rv)
        : rows(r), columns(c), row_values(std::move(rv)) {
        if (row_values.size() != static_cast<std::size_t>(rows) * columns) {
            throw std::invalid_argument("Rows and columns does not match dimension size of input");
        }
    }

    // Zero matrix of a given shape.
    Matrix(int r, int c)
        : rows(r), columns(c), row_values(static_cast<std::size_t>(r) * c, 0.0) {}

    // "Born random": weights ~ N(0, 1/sqrt(fan_in)), fan_in = rows (input dim).
    // Delegates to the zero ctor, then fills. Mirrors the Rung-0 Node ctor.
    Matrix(int r, int c, std::mt19937& rng) : Matrix(r, c) {
        randomise(rng);
    }

    // In-place re-initialisation. Caller owns the rng (and therefore the seed),
    // so runs stay reproducible.
    void randomise(std::mt19937& rng) {
        const double scale = 1.0 / std::sqrt(static_cast<double>(rows));
        std::normal_distribution<double> dist(0.0, scale);
        for (double& v : row_values){ 
            v = dist(rng);
        }
    }
};

inline Matrix matmul(const Matrix& A, const Matrix& B){
    //matrix A cross Matrix B

    if (A.columns != B.rows){
        throw std::invalid_argument("Columns of A must be equal to the rows of B");
    }
    const int m = A.rows;        // C is m x p
    const int n = A.columns;     // shared dimension (== B.rows)
    const int p = B.columns;

    std::vector<double> newValues(m * p, 0.0);   // zeroed: we ACCUMULATE into it

    for (int i = 0; i < m; ++i){
        for (int j = 0; j < n; ++j){
            const double a = A.row_values[i * n + j];
            for (int k = 0; k < p; ++k){
                newValues[i * p + k] += a * B.row_values[j * p + k];
            }
        }
    }
    return Matrix(m, p, newValues);
}
inline void matmul(const Matrix& A, const Matrix& B, Matrix& out) {
    // validate dimensions
    if (A.columns != B.rows){
        throw std::invalid_argument("Columns of A must be equal to the rows of B");
    }
    if (out.rows != A.rows || out.columns != B.columns){
        throw std::invalid_argument("Output buffer is wrong shape");
    }
    const int m = A.rows;        // C is m x p
    const int n = A.columns;     // shared dimension (== B.rows)
    const int p = B.columns;
    std::fill(out.row_values.begin(), out.row_values.end(), 0.0);  // zero it

    for (int i = 0; i < m; ++i){
        for (int j = 0; j < n; ++j) {
            const double a = A.row_values[i * n + j];
            for (int k = 0; k < p; ++k)
                out.row_values[i * p + k] += a * B.row_values[j * p + k];
        }
    }
}

inline Matrix transpose(const Matrix &A){
    const int rows = A.rows;
    const int columns = A.columns;

    std::vector<double> newValues(rows * columns);

    for (int i = 0; i < rows; ++i){
        for (int j = 0; j < columns; ++j){
            newValues[j*rows + i] = A.row_values[i*columns + j];
        }
    }
    return Matrix(columns, rows, newValues);
}

// ----------------------------------------------------------------------------
// Elementwise ops come in two forms (PyTorch's convention):
//   foo_(...)  IN-PLACE: mutates and returns its first argument, no allocation.
//   foo (...)  PURE:     allocates a fresh result, leaves its inputs untouched.
// The math lives ONCE, in the in-place core; the pure form is just "copy, then
// mutate the copy". Use the pure form when you must not disturb an input (a
// cached or parameter matrix); use in-place on transient buffers you own.
// ----------------------------------------------------------------------------

// A += Bias, where Bias is (1 x columns) broadcast across every row of A.
inline Matrix& element_wise_add_(Matrix &A, const Matrix &Bias){
    if (A.columns != Bias.columns){
        throw std::invalid_argument("Columns of A must be equal to the columns of the Bias Vector");
    }
    if (Bias.rows != 1){
        throw std::invalid_argument("Bias vector must only have 1 row");
    }
    const int rows = A.rows;
    const int columns = A.columns;
    for (int i = 0; i < rows; ++i){
        for (int j = 0; j < columns; ++j){
            A.row_values[i*columns + j] += Bias.row_values[j];
        }
    }
    return A;
}
inline Matrix element_wise_add(const Matrix &A, const Matrix &Bias){
    Matrix out = A;                       // copy
    element_wise_add_(out, Bias);         // mutate the copy
    return out;
}

// A -= B (same shape, no broadcasting).
inline Matrix& element_wise_subtract_(Matrix &A, const Matrix &B){
    if (A.rows != B.rows || A.columns != B.columns){
        throw std::invalid_argument("Matrix dimensions must be equal");
    }
    for (std::size_t i = 0; i < A.row_values.size(); ++i){
        A.row_values[i] -= B.row_values[i];
    }
    return A;
}
inline Matrix element_wise_subtract(const Matrix &A, const Matrix &B){
    Matrix out = A;
    element_wise_subtract_(out, B);
    return out;
}

// A = A ⊙ B (elementwise multiply, same shape).
inline Matrix& hadamard_(Matrix &A, const Matrix &B){
    if (A.rows != B.rows || A.columns != B.columns){
        throw std::invalid_argument("Matrix dimensions must be equal");
    }
    for (std::size_t i = 0; i < A.row_values.size(); ++i){
        A.row_values[i] *= B.row_values[i];
    }
    return A;
}
inline Matrix hadamard(const Matrix &A, const Matrix &B){
    Matrix out = A;
    hadamard_(out, B);
    return out;
}

// A *= s (e.g. the 1/N in a gradient).
inline Matrix& scale_(Matrix &A, double s){
    for (double& v : A.row_values) v *= s;
    return A;
}
inline Matrix scale(const Matrix &A, double s){
    Matrix out = A;
    scale_(out, s);
    return out;
}

// Apply a scalar function f elementwise.
template <typename F>
Matrix& apply_(Matrix &A, F f){
    for (double& v : A.row_values) v = f(v);
    return A;
}
template <typename F>
Matrix apply(const Matrix &A, F f){
    Matrix out = A;
    apply_(out, f);
    return out;
}

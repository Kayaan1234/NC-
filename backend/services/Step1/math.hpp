#pragma once
#include <cmath>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include "matrix.hpp"

// --- Activations: scalar f(z) on the pre-activation z ------------------------
inline double sigmoid(double x){
    return (1.0/(1.0+std::exp(-x)));
}

inline double tanh_act(double x){
    return std::tanh(x);   // overflow-safe; avoids clashing with C's ::tanh
}

inline double relu(double x){
    return std::max(0.0,x);
}

// --- Derivatives: NOTE these take the cached OUTPUT a = f(z), not z ----------
// During backprop the forward output is already stored, so expressing the
// derivative in terms of a means zero recomputation (no exp / no tanh).
// Passing z here instead of a is a silent gradient bug.
inline double sigmoid_deriv(double a){
    return a * (1.0 - a);
}

inline double tanh_deriv(double a){
    return 1.0 - a * a;
}

inline double relu_deriv(double a){
    // relu(z) > 0  iff  z > 0, so the output a carries the same sign info.
    // Undefined at 0 mathematically; like most libraries we use 0.
    return (a > 0.0) ? 1.0 : 0.0;
}

// Row-wise softmax: M is (batch_size x num_classes); each ROW (one sample) is
// turned into a probability distribution over the columns (classes).
// Numerically stable via the shift-invariance trick: subtract the row max so
// the largest exponent is exp(0)=1 and nothing can overflow to inf.
inline Matrix& softmax(Matrix &M){
    const int rows = M.rows;
    const int cols = M.columns;
    
    for (int i = 0; i < rows; ++i){
        const int base = i * cols;                 // start of row i in flat storage

        // 1. row max (over the class columns) for stability
        double row_max = M.row_values[base];
        for (int j = 1; j < cols; ++j)
            row_max = std::max(row_max, M.row_values[base + j]);

        // 2. exp(x - row_max) and 3. accumulate the sum, in one sweep
        double sum = 0.0;
        for (int j = 0; j < cols; ++j){
            const double e = std::exp(M.row_values[base + j] - row_max);
            M.row_values[base + j] = e;
            sum += e;
        }

        // 4. normalise. Multiply by the reciprocal once instead of dividing per element.
        const double inv = 1.0 / sum;
        for (int j = 0; j < cols; ++j)
            M.row_values[base + j] *= inv;
    }
    return M;
}

inline double binary_cross_entropy_loss(const Matrix &pred, const Matrix &truth){
    if (pred.rows != truth.rows || pred.columns != truth.columns){
        throw std::invalid_argument("Prediction and truth matrices do not have the same dimensions");
    }
    
    const double eps = 1e-7;
    double loss = 0.0;

    for (std::size_t i = 0; i < pred.row_values.size(); ++i) {
        double p = std::min(std::max(pred.row_values[i], eps), 1.0 - eps);
        loss += truth.row_values[i] * std::log(p) + (1.0 - truth.row_values[i]) * std::log(1.0 - p);
    }
    
    return -loss / (static_cast<double>(pred.rows) * static_cast<double>(pred.columns));
}

inline double cross_entropy_loss(const Matrix &pred, const Matrix &truth){
    if (pred.rows != truth.rows || pred.columns != truth.columns){
        throw std::invalid_argument("Prediction and truth matrices do not have the same dimensions");
    }
    const double eps = 1e-7;
    double loss = 0.0;
    const int n = pred.rows;
    const int m = pred.columns;
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < m; ++j){
            const double p = std::max(pred.row_values[i * m + j], eps);   // guard log(0)
            loss += truth.row_values[i * m + j] * std::log(p);
        }
    }

    return -loss / static_cast<double>(n);
}

// Gradient of the loss w.r.t. the LOGITS (pre-softmax scores) -- the seed of
// backprop. For softmax+cross-entropy (and sigmoid+BCE) the softmax Jacobian
// and the loss derivative cancel into the famous (pred - truth). Scaled by 1/N
// to match the batch-averaged loss above, so grad magnitudes line up.
inline Matrix cross_entropy_loss_grad(const Matrix &pred, const Matrix &truth){
    if (pred.rows != truth.rows || pred.columns != truth.columns){
        throw std::invalid_argument("Prediction and truth matrices do not have the same dimensions");
    }
    Matrix grad = element_wise_subtract(pred, truth);   // PURE: fresh buffer, pred untouched
    scale_(grad, 1.0 / static_cast<double>(pred.rows)); // IN-PLACE: on our own buffer
    return grad;
}

// ----------------------------------------------------------------------------
// Fused softmax + cross-entropy, for an output layer that hands back RAW LOGITS
// (activation LINEAR -- the shape the MLP is built to use). cross_entropy_loss
// and cross_entropy_loss_grad ABOVE both assume their `pred` argument is already
// a probability distribution: the loss takes log(pred), and the grad returns the
// fused (pred - truth)/N. Feeding raw logits to either is a silent bug.
//
// These two wrappers apply the softmax first, so they take logits and are a
// MATCHED pair: softmax_cross_entropy_loss_grad(z, y) really is d/dz of
// softmax_cross_entropy_loss(z, y). That is exactly what a numerical gradient
// check needs (see grad_check.hpp) when the layer under test is LINEAR.
inline double softmax_cross_entropy_loss(const Matrix& logits, const Matrix& truth){
    Matrix probs = logits;   // copy: softmax mutates in place
    softmax(probs);
    return cross_entropy_loss(probs, truth);
}
inline Matrix softmax_cross_entropy_loss_grad(const Matrix& logits, const Matrix& truth){
    Matrix probs = logits;
    softmax(probs);
    return cross_entropy_loss_grad(probs, truth);
}

// Mean squared error, batch-averaged by rows (like the CE losses). Its gradient
// w.r.t. the prediction a is dL/da = 2(a - truth)/N -- a DIRECT dL/da, with no
// fused activation term. That makes (mse_loss, mse_loss_grad) a valid pair for a
// numerical gradient check on a NONLINEAR layer (tanh/relu/sigmoid), which
// exercises the activation-derivative + hadamard path that softmax+CE's LINEAR
// output layer never touches.
inline double mse_loss(const Matrix &pred, const Matrix &truth){
    if (pred.rows != truth.rows || pred.columns != truth.columns){
        throw std::invalid_argument("Prediction and truth matrices do not have the same dimensions");
    }
    double sum = 0.0;
    for (std::size_t i = 0; i < pred.row_values.size(); ++i){
        const double diff = pred.row_values[i] - truth.row_values[i];
        sum += diff * diff;
    }
    return sum / static_cast<double>(pred.rows);
}
inline Matrix mse_loss_grad(const Matrix &pred, const Matrix &truth){
    if (pred.rows != truth.rows || pred.columns != truth.columns){
        throw std::invalid_argument("Prediction and truth matrices do not have the same dimensions");
    }
    Matrix grad = element_wise_subtract(pred, truth);              // (a - truth)
    scale_(grad, 2.0 / static_cast<double>(pred.rows));           // 2(a - truth)/N
    return grad;
}
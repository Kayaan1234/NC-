#pragma once
#include <cmath>
#include <iostream>
#include <iomanip>
#include <string>
#include "matrix.hpp"
#include "layer.hpp"

// Generic numerical gradient check for a single Layer. The loss functions live
// in math.hpp; a LossFn takes (pred, truth) -> scalar, a LossGradFn takes
// (pred, truth) -> Matrix (the seed dL/da fed into Layer::backward).
//
// CRITICAL -- the pair must be consistent: loss_grad_fn(a, truth) has to be the
// true derivative of loss_fn(a, truth) w.r.t. the layer's OUTPUT a. Two traps:
//   * cross_entropy_loss + cross_entropy_loss_grad is NOT such a pair. The grad
//     returns the FUSED dL/dz (softmax already folded in), but backward() then
//     re-applies da/dz -- the activation derivative gets counted twice.
//   * both cross_entropy_* assume `pred` is post-softmax probabilities, yet the
//     layer hands back raw logits, so they'd be evaluated on the wrong input.
// For a softmax+CE output layer use a LINEAR layer with the MATCHED pair from
// math.hpp: softmax_cross_entropy_loss + softmax_cross_entropy_loss_grad (they
// apply the softmax internally, and dL/dz == dL/da when the activation is
// LINEAR). For a nonlinearity, pair a plain loss whose dL/da you can write
// directly (e.g. MSE) with a matching grad fn.
using LossFn = double(*)(const Matrix&, const Matrix&);
using LossGradFn = Matrix(*)(const Matrix&, const Matrix&);

inline double relative_error(double analytical, double numerical, double floor = 1e-8){
    double diff = std::abs(analytical - numerical);
    double denom = std::max({std::abs(analytical), std::abs(numerical), floor});
    return diff / denom;
}

// Perturb a single weight entry (i,j), rerun forward+loss with the layer's
// OWN output (not the cached backward pass) so this is a fully independent
// check on the analytical gradient computed via backward().
inline double numerical_weight_grad(Layer& layer, const Matrix& X, const Matrix& truth,
    LossFn loss_fn, double epsilon, int i, int j){

    const int fan_out = layer.weight.columns;
    const std::size_t idx = static_cast<std::size_t>(i) * fan_out + j;

    double original = layer.weight.row_values[idx];

    layer.weight.row_values[idx] = original + epsilon;
    double loss_plus = loss_fn(layer.forward(X), truth);

    layer.weight.row_values[idx] = original - epsilon;
    double loss_minus = loss_fn(layer.forward(X), truth);

    layer.weight.row_values[idx] = original;   // restore -- don't leave the layer perturbed
    return (loss_plus - loss_minus) / (2 * epsilon);
}

inline double numerical_bias_grad(Layer& layer, const Matrix& X, const Matrix& truth,
    LossFn loss_fn, double epsilon, int j){

    double original = layer.bias.row_values[j];

    layer.bias.row_values[j] = original + epsilon;
    double loss_plus = loss_fn(layer.forward(X), truth);

    layer.bias.row_values[j] = original - epsilon;
    double loss_minus = loss_fn(layer.forward(X), truth);

    layer.bias.row_values[j] = original;
    return (loss_plus - loss_minus) / (2 * epsilon);
}

// Runs forward -> loss_grad -> backward once to get the analytical gradients,
// then re-derives each entry numerically via finite differences and compares.
inline bool run(Layer& layer, const Matrix& X, const Matrix& truth,
    LossFn loss_fn, LossGradFn loss_grad_fn,
    double epsilon = 1e-5, double tol = 1e-4){

    const Matrix& pred = layer.forward(X);
    Matrix upstream = loss_grad_fn(pred, truth);
    layer.backward(upstream);   // fills layer.grad_weight / layer.grad_bias

    std::cout << std::fixed << std::setprecision(8);
    std::cout << "\n--- layer gradient check (epsilon=" << epsilon << ", tol=" << tol << ") ---\n";
    std::cout << std::left << std::setw(12)
                << "param" << std::setw(18) << "analytical"
                << std::setw(18) << "numerical"
                << std::setw(14) << "rel_error"
                << "status\n";
    std::cout << std::string(70, '-') << "\n";

    bool all_pass = true;
    const int fan_in = layer.weight.rows;
    const int fan_out = layer.weight.columns;

    for (int i = 0; i < fan_in; ++i) {
        for (int j = 0; j < fan_out; ++j) {
            double analytical = layer.grad_weight.row_values[static_cast<std::size_t>(i) * fan_out + j];
            double num = numerical_weight_grad(layer, X, truth, loss_fn, epsilon, i, j);
            double rel = relative_error(analytical, num);
            bool ok = rel < tol;
            if (!ok) all_pass = false;

            std::cout << std::left
                      << std::setw(12) << ("W[" + std::to_string(i) + "," + std::to_string(j) + "]")
                      << std::setw(18) << analytical
                      << std::setw(18) << num
                      << std::setw(14) << rel
                      << (ok ? "OK" : "FAIL") << "\n";
        }
    }

    for (int j = 0; j < fan_out; ++j) {
        double analytical = layer.grad_bias.row_values[j];
        double num = numerical_bias_grad(layer, X, truth, loss_fn, epsilon, j);
        double rel = relative_error(analytical, num);
        bool ok = rel < tol;
        if (!ok) all_pass = false;

        std::cout << std::left
                  << std::setw(12) << ("b[" + std::to_string(j) + "]")
                  << std::setw(18) << analytical
                  << std::setw(18) << num
                  << std::setw(14) << rel
                  << (ok ? "OK" : "FAIL") << "\n";
    }

    std::cout << std::string(70, '-') << "\n";
    std::cout << "Result: " << (all_pass ? "PASS" : "FAIL") << "\n\n";
    return all_pass;
}

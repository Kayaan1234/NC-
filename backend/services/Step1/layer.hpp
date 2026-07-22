#pragma once
#include <cmath>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include "matrix.hpp"
#include <random>
#include "math.hpp"
#include <iostream>

enum Activation{
    TANH,
    SIGMOID,
    RELU,
    LINEAR,   // identity: forward = x, f'(a) = 1. Used by the output layer,
              // whose softmax+CE gradient is handled in the loss instead.
};

// Map the activation enum to the scalar function that apply_/apply expects.
inline double identity(double x){ return x; }   // LINEAR (output layer)

using ActFn = double(*)(double);
inline ActFn activation_fn(Activation act){
    switch (act) {
        case TANH:    return tanh_act;
        case SIGMOID: return sigmoid;
        case RELU:    return relu;
        case LINEAR:  return identity;
    }
    throw std::invalid_argument("activation_fn: unknown Activation");  // also silences -Wreturn-type
}

// Map the activation enum to its DERIVATIVE. Mirrors activation_fn so backward
// can fetch f' the same way forward fetches f. Like the *_deriv helpers in
// math.hpp, these take the cached OUTPUT a = f(z), not the pre-activation z.
inline double identity_deriv(double){ return 1.0; }  // LINEAR: f(x)=x => f'=1

inline ActFn activation_deriv_fn(Activation act){
    switch (act) {
        case TANH:    return tanh_deriv;
        case SIGMOID: return sigmoid_deriv;
        case RELU:    return relu_deriv;
        case LINEAR:  return identity_deriv;
    }
    throw std::invalid_argument("activation_deriv_fn: unknown Activation");  // silences -Wreturn-type
}


struct Layer{
    // parameters (these learn)
    Matrix weight;        // (fan_in x fan_out)
    Matrix bias;          // (1 x fan_out)

    // cache: written in forward, read in backward. Shapes depend on batch size,
    // so they start empty (default Matrix) and are assigned on the first forward.
    Matrix cache_input;
    Matrix cache_output;

    // gradients: filled by backward, consumed by update. Shapes known now, zeroed.
    Matrix grad_weight;   // (fan_in x fan_out)
    Matrix grad_bias;     // (1 x fan_out)

    Activation activation_type;

    Layer(int fan_in, int fan_out, Activation activation, std::mt19937& rng)
        : weight(fan_in, fan_out, rng),
          bias(1, fan_out),
          grad_weight(fan_in, fan_out),
          grad_bias(1, fan_out),
          activation_type(activation) {
    }
    const Matrix& forward(const Matrix &input) {
        const int batch   = input.rows;
        const int fan_out = weight.columns;

        // (Re)allocate the output buffer only when the batch shape changes -- i.e.
        // once for a fixed batch size. Also mandatory for correctness: matmul's
        // out-buffer overload writes into existing storage and never resizes.
        if (cache_output.rows != batch || cache_output.columns != fan_out)
            cache_output = Matrix(batch, fan_out);

        matmul(input, weight, cache_output);                  // z -> owned buffer
        element_wise_add_(cache_output, bias);                // + bias, in place
        apply_(cache_output, activation_fn(activation_type)); // -> a, in place

        cache_input = input;        // backward needs the input it saw
        return cache_output;        // by reference: the next layer reads it directly
    }
    Matrix backward(const Matrix &upstream_gradient){ //this is dL/da
        int batch = upstream_gradient.rows;
        int fan_out = upstream_gradient.columns;

        Matrix temp = apply(cache_output,activation_deriv_fn(activation_type)); //da/dz
        hadamard_(temp, upstream_gradient); // dL/dz, as activation was applied across every value
        // dL/db = dz/db x dL/dz - we broadcast the bias to all values in the forward pass, 
        // so the loss is simply summing the loss 
        
        std::vector<double> grad_bias_vec(fan_out, 0.0);   // pre-allocate, zero-init

        for (int i = 0; i < batch; ++i) {
            for (int j = 0; j < fan_out; ++j) {
                grad_bias_vec[j] += temp.row_values[i * fan_out + j];
            }
        }
        
        grad_bias = Matrix(1,fan_out,grad_bias_vec);


        //need dL/dW. Output has shape (batch, fan_out), W has shape (fan_in, fan_out)

        grad_weight = matmul(transpose(cache_input), temp);

        //finally dL/dX - this is just dL_dz x dz_dX. dz_dX is W^T. 

        
        return matmul(temp, transpose(weight));
    
        


    }
    Matrix& update(double lr){
        scale_(grad_weight, lr);
        scale_(grad_bias, lr);

        element_wise_subtract_(weight, grad_weight);
        element_wise_subtract_(bias, grad_bias);

        return weight;
    }
};
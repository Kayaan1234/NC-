#pragma once
#include <iostream>
#include <vector>
#include <stdexcept>
#include <random>
#include "matrix.hpp"
#include "layer.hpp"
#include "math.hpp"


struct MLP{
    std::vector<int> layer_sizes;
    std::vector<Activation> activations;
    std::vector<Layer> layers;

    /*  
        layer_sizes: e.g. {2, 4, 1} = 2 inputs -> 4 hidden -> 1 output.
        activations: one per layer (size == layer_sizes.size() - 1), so
        activations[i] is the activation applied by the layer mapping
        layer_sizes[i] -> layer_sizes[i+1].
    */
    MLP(const std::vector<int>& l_sizes, const std::vector<Activation>& acts, std::mt19937& rng)
        : layer_sizes(l_sizes), activations(acts) {

        if (layer_sizes.size() < 2){
            throw std::invalid_argument("MLP needs at least an input and an output size");
        }
        if (activations.size() != layer_sizes.size() - 1){
            throw std::invalid_argument("activations must have one entry per layer (layer_sizes.size() - 1)");
        }
        // train() applies softmax + cross-entropy itself, so the output layer
        // must hand back raw logits -- LINEAR is the only activation that does.
        if (activations.back() != LINEAR){
            throw std::invalid_argument("output layer activation must be LINEAR (train() applies softmax+CE itself)");
        }

        layers.reserve(activations.size()); //this is optimisation - makes things faster. 
        for (std::size_t i = 0; i < activations.size(); ++i){
            layers.emplace_back(layer_sizes[i], layer_sizes[i + 1], activations[i], rng);
        }
    }

    
    const Matrix& forward(const Matrix& input) {
        const Matrix* current = &input; //current is the pointer to a matrix which is the reference of input

        for (auto& layer : layers) {
            current = &layer.forward(*current);
        }

        return *current;
    }
    Matrix backward(const Matrix& loss_grad){
        Matrix current = loss_grad;
        for (auto it = layers.rbegin(); it != layers.rend(); ++it){ //iterator using a pointer, start at RHS and go Left
            current = it->backward(current);
        }
        return current;
    }



    void train(const Matrix& X, const Matrix& truth, int epochs, double lr){
        for (int epoch = 0; epoch < epochs; ++epoch){
            const Matrix& prediction = forward(X);
            Matrix probs = prediction;   // copy: softmax mutates in place, prediction is const&
            softmax(probs);
            Matrix loss_grad = cross_entropy_loss_grad(probs, truth);
            backward(loss_grad);
            for (auto& layer : layers){
                layer.update(lr);
            }
            if (epoch % 100 == 0){
                double loss = cross_entropy_loss(probs, truth);
                std::cout << "epoch " << epoch << " loss " << loss << "\n";
        }
        }
    }
    
};


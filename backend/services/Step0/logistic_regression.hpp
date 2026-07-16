#pragma once
#include <vector>
#include <cmath>
#include <algorithm>
#include <stdexcept>
#include <random>
#include "math.hpp"


struct Node {
    std::vector<double> vec;  // weights, one per input feature
    double b;                 // bias

    explicit Node(std::size_t n, std::mt19937& rng) : vec(n), b(0.0) {
      // scale ~ 1/sqrt(fan_in): keeps the initial w·x near the sigmoid's
      // steep, high-gradient region instead of its flat, saturated tails.
      const double scale = 1.0 / std::sqrt(static_cast<double>(n));
      std::normal_distribution<double> dist(0.0, scale);
      for (double& w : vec) w = dist(rng);
    }

    double forward(const std::vector<double>& x) const {
        return sigmoid(dot(x, vec) + b);

    }
    struct Grad {
        std::vector<double> w;
        double b = 0.0;
    };

    double binaryLoss(const std::vector<double>& y, const std::vector<std::vector<double>>& x) const {
        if (x.size() != y.size()) {
            throw std::invalid_argument("x and y must have the same number of samples");
        }

        const double eps = 1e-7;
        double loss = 0.0;
        for (std::size_t i = 0; i < x.size(); ++i) {
            double p = std::clamp(forward(x[i]), eps, 1.0 - eps);
            loss += y[i] * std::log(p) + (1.0 - y[i]) * std::log(1.0 - p);
        }
        loss = -loss / static_cast<double>(y.size());
        return loss;
    }
    Grad gradient(const std::vector<std::vector<double>>& x, const std::vector<double>& y) const{
        if (x.size() != y.size()) {
            throw std::invalid_argument("x and y must have the same number of samples");
        }
        const std::size_t N = x.size();
        std::vector<double> weight_gradients(vec.size(), 0.0);
        double bias_gradient = 0.0;
        for (std::size_t i = 0; i < N; ++i){
            const double error = forward(x[i])-y[i];
            for(std::size_t j = 0; j < x[i].size(); ++j){
                
                weight_gradients[j] += error * x[i][j]; 

            }
            bias_gradient += error;
            

        }
        const double invN = 1.0 / static_cast<double>(N);
        for (double& g : weight_gradients){
            g *= invN;
            
        }
        bias_gradient *= invN;

    return Grad{weight_gradients, bias_gradient};
    }
    void update(const Grad& g, double lr){
        if (g.w.size() != vec.size())
            throw std::invalid_argument("gradient and weights size mismatch");
        for (std::size_t j = 0; j < vec.size(); ++j)
            vec[j] -= lr * g.w[j];
        b -= lr * g.b;
    }
};
#pragma once
#include <cmath>
#include <vector>
#include <stdexcept>


inline double sigmoid(double x){
    return (1.0/(1.0+std::exp(-x)));
}
inline double dot(const std::vector<double>& a, const std::vector<double>& b){
    if (a.size() != b.size()){
        
        throw std::invalid_argument("Vectors must have same size");
        
    }
    double total = 0.0;
    for (std::size_t i = 0; i < a.size(); ++i){
        total += a[i] * b[i];
    }
    return total;
}
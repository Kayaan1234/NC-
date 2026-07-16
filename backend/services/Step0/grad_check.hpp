#pragma once
#include <cmath>
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include "logistic_regression.hpp"

inline double relative_error(double analytical, double numerical, double floor = 1e-8){
    double diff = std::abs(analytical - numerical);
    double denom = std::max({std::abs(analytical), std::abs(numerical), floor});
    return diff / denom;
}
inline double numerical_weight_grad(Node& node, const std::vector<std::vector<double>>& X, 
    const std::vector<double>& y, double epsilon, std::size_t j){
    
    double original_weight = node.vec[j];
    node.vec[j] = original_weight + epsilon;
    double loss_plus = node.binaryLoss(y, X);
    node.vec[j] = original_weight - epsilon;
    double loss_minus = node.binaryLoss(y,X);
    node.vec[j] = original_weight;
    return (loss_plus - loss_minus)/ (2*epsilon);
}
inline double numerical_bias_grad(Node& node, const std::vector<std::vector<double>>& X,
    const std::vector<double>& y, double epsilon){
    
    double original_bias = node.b;
    node.b = original_bias + epsilon;
    double loss_plus = node.binaryLoss(y,X);
    node.b = original_bias - epsilon;
    double loss_minus = node.binaryLoss(y,X);
    node.b = original_bias;
    return (loss_plus - loss_minus) / (2 * epsilon);

}
inline bool run(Node& node, const std::vector<std::vector<double>>& X,
    const std::vector<double>& y, double epsilon = 5e-3, double tol = 1e-4){
        Node::Grad analytical = node.gradient(X,y);
        std::cout << std::fixed << std::setprecision(8);
        std::cout << "\n--- gradient check (epsilon=" << epsilon << ", tol=" << tol << ") ---\n";
        std::cout << std::left << std::setw(12) 
                    << "param" << std::setw(18) << "analytical"                                                                                                                                            
                    << std::setw(18) << "numerical"                                                                                                                                             
                    << std::setw(14) << "rel_error"                                                                                                                                             
                    << "status\n";                                                                                                                                                              
        std::cout << std::string(70, '-') << "\n";
        bool all_pass = true;
        for (std::size_t j = 0; j < node.vec.size(); ++j) {                                                                                                                                   
              double num = numerical_weight_grad(node, X, y, epsilon, j);
              double rel = relative_error(analytical.w[j], num);                                                                                                                                
              bool ok = rel < tol;                                                                                                                                                              
              if (!ok) all_pass = false;                                                                                                                                                        
                                                                                                                                                                                                
              std::cout << std::left                                                                                                                                                            
                        << std::setw(12) << ("w[" + std::to_string(j) + "]")                                                                                                                    
                        << std::setw(18) << analytical.w[j]                                                                                                                                     
                        << std::setw(18) << num                                                                                                                                                 
                        << std::setw(14) << rel                                                                                                                                                 
                        << (ok ? "OK" : "FAIL") << "\n";                                                                                                                                        
        }                                                                                                                                                                                     
                                                                                                                                                                                                 
        {                                                                                                                                                                                     
            double num = numerical_bias_grad(node, X, y, epsilon);                                                                                                                                
            double rel = relative_error(analytical.b, num);                                                                                                                                   
            bool ok = rel < tol;                                                                                                                                                              
            if (!ok) all_pass = false;                                                                                                                                                        
                                                                                                                                                                                                 
            std::cout << std::left                                                                                                                                                            
                    << std::setw(12) << "b"                                                                                                                                                 
                    << std::setw(18) << analytical.b                                                                                                                                        
                    << std::setw(18) << num                                                                                                                                                 
                    << std::setw(14) << rel                                                                                                                                                 
                    << (ok ? "OK" : "FAIL") << "\n";                                                                                                                                        
        }                                                                                                                                                                                     
                                                                                                                                                                                               
        std::cout << std::string(70, '-') << "\n";                                                                                                                                            
        std::cout << "Result: " << (all_pass ? "PASS" : "FAIL") << "\n\n";                                                                                                                    
        return all_pass;   
}
# Builds the `nn` training binary that backend/services/runner.py executes.
#
# The binary is deliberately NOT committed (see .gitignore) — it is platform
# specific, so a macOS build will not run in a Linux container. Build it on the
# machine that runs the worker:
#
#     make            # build ./nn
#     make clean
#
# C++17 is required: std::clamp (logistic_regression.hpp) and the
# std::max({...}) initialiser-list overload (grad_check.hpp).

CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra

HEADERS := logistic_regression.hpp math.hpp grad_check.hpp

nn: main.cpp $(HEADERS)
	$(CXX) $(CXXFLAGS) -o $@ main.cpp

clean:
	rm -f nn

.PHONY: clean

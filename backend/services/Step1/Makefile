# Builds the `nn` Rung-1 (MLP) training binary that the webserver's
# backend/services/runner.py executes.
#
# The binary is deliberately NOT committed (see .gitignore) -- it is platform
# specific, so a macOS build will not run in a Linux container. Build it on the
# machine that runs the worker:
#
#     make            # build ./nn
#     make clean
#
# C++17 is required (structured bindings, std::max initializer-list overload in
# grad_check.hpp, etc).

CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra

HEADERS := matrix.hpp math.hpp layer.hpp MLP.hpp grad_check.hpp

nn: main.cpp $(HEADERS)
	$(CXX) $(CXXFLAGS) -o $@ main.cpp

clean:
	rm -f nn

.PHONY: clean

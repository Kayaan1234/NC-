#include <iostream>
#include <iomanip>
#include <vector>
#include <random>
#include <cmath>
#include <algorithm>
#include <string>
#include <stdexcept>
#include "logistic_regression.hpp"
#include "grad_check.hpp"


struct Dataset{
    std::vector<std::vector<double>> X;
    std::vector<double> y;
};

// Training configuration. Populated from CLI flags (see parse_args / print_usage).
// The dataset is one of the built-ins: --dataset is required, everything else defaults.
struct Config {
    std::string  dataset;          // one of "tiny", "blobs", "xor" (required)
    double       lr     = 0.5;
    int          epochs = 500;
    unsigned int seed   = 42;
    bool         demo   = false;   // --demo: run the built-in teaching demo instead
};

// --- forward declarations: main reads as the summary, details below ---
Dataset make_blobs(std::size_t n_samples, std::size_t n_dims, std::mt19937& rng);
Dataset make_xor();
Dataset make_tiny();
void    train(Node& node, const Dataset& d, double lr, int epochs);
double  accuracy(const Node& node, const Dataset& d);
void    show_predictions(const Node& node, const Dataset& d);

void    print_usage();
Config  parse_args(int argc, char** argv, bool& ok, bool& help);
int     run_configured(const Config& cfg);
void    run_demo();

// Two modes:
//   nn --dataset <name> -> one configured training run on a built-in dataset, ending
//                          in a machine-readable RESULT line the training service parses.
//   nn --demo           -> the original three-toy demo (a teaching artifact).
// A missing --dataset (with no --demo) is an error: there is no sensible default.
int main(int argc, char** argv){
    bool ok = true, help = false;
    Config cfg;
    try {
        cfg = parse_args(argc, argv, ok, help);
    } catch (const std::exception& e) {
        std::cerr << "error parsing arguments: " << e.what() << "\n";
        return 2;
    }
    if (help) { print_usage(); return 0; }
    if (!ok)  { print_usage(); return 2; }

    if (cfg.demo) { run_demo(); return 0; }

    if (cfg.dataset.empty()) {
        std::cerr << "error: no dataset provided; --dataset <name> is required\n\n";
        print_usage();
        return 2;
    }
    return run_configured(cfg);
}

void print_usage() {
    std::cout <<
        "Usage: nn --dataset <name> [options]\n"
        "       nn --demo\n"
        "       nn --help\n"
        "\n"
        "  Trains a single logistic-regression neuron on one of the built-in datasets\n"
        "  and prints a machine-readable RESULT line for the training service to parse.\n"
        "\n"
        "Datasets (--dataset, required):\n"
        "  tiny             2D, 3 samples, linearly separable\n"
        "  blobs            4D, 200 samples, linearly separable\n"
        "  xor              2D, 4 samples, NOT linearly separable\n"
        "\n"
        "Options:\n"
        "  --lr <float>     learning rate                      (default: 0.5)\n"
        "  --epochs <int>   training epochs                    (default: 500)\n"
        "  --seed <int>     RNG seed for weight init           (default: 42)\n"
        "  --demo           run the built-in three-toy demo\n"
        "  -h, --help       show this help\n"
        "\n"
        "Example:\n"
        "  nn --dataset blobs --lr 0.1 --epochs 300 --seed 7\n";
}

// Minimal hand-rolled parser for `--key value` flags. Conversion failures
// (e.g. --epochs abc) throw and are turned into a non-zero exit by main.
Config parse_args(int argc, char** argv, bool& ok, bool& help) {
    Config cfg;
    ok = true;
    help = false;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--help" || a == "-h") { help = true; return cfg; }
        if (a == "--demo") { cfg.demo = true; continue; }

        auto value = [&](const std::string& name) -> std::string {
            if (i + 1 >= argc)
                throw std::invalid_argument("missing value for " + name);
            return argv[++i];
        };

        if      (a == "--dataset") cfg.dataset = value(a);
        else if (a == "--lr")     cfg.lr     = std::stod(value(a));
        else if (a == "--epochs") cfg.epochs = std::stoi(value(a));
        else if (a == "--seed")   cfg.seed   = static_cast<unsigned>(std::stoul(value(a)));
        else { std::cerr << "unknown argument: " << a << "\n"; ok = false; }
    }
    return cfg;
}

// One configured training run on a built-in dataset. Emits human-readable progress,
// then a single `RESULT {...}` JSON line for the service to parse. Returns a
// process exit code (0 = ok, 2 = bad input) so the caller can mark jobs failed.
int run_configured(const Config& cfg) {
    if (cfg.epochs < 0) {
        std::cerr << "epochs must be >= 0\n";
        return 2;
    }

    std::mt19937 rng(cfg.seed);

    Dataset d;
    if      (cfg.dataset == "tiny")  d = make_tiny();
    else if (cfg.dataset == "blobs") d = make_blobs(200, 4, rng);
    else if (cfg.dataset == "xor")   d = make_xor();
    else {
        std::cerr << "error: unknown dataset: " << cfg.dataset
                  << "; expected one of tiny, blobs, xor\n";
        return 2;
    }

    std::cout << "=== training: dataset=" << cfg.dataset
              << " lr=" << cfg.lr << " epochs=" << cfg.epochs
              << " samples=" << d.X.size() << " features=" << d.X[0].size()
              << " seed=" << cfg.seed << " ===\n";

    Node node(d.X[0].size(), rng);
    train(node, d, cfg.lr, cfg.epochs);

    const double final_loss = node.binaryLoss(d.y, d.X);
    const double final_acc  = accuracy(node, d);

    std::cout << "final accuracy " << std::fixed << std::setprecision(4)
              << final_acc * 100 << "%\n";

    // --- machine-readable result line for the training service ---
    // A user-supplied lr can diverge the loss to inf/nan; those aren't valid
    // JSON, so guard them to `null` and flag `diverged` instead.
    const bool loss_ok = std::isfinite(final_loss);
    const bool acc_ok  = std::isfinite(final_acc);
    std::cout << std::defaultfloat << std::setprecision(8);  // undo train()'s fixed/4
    std::cout << "RESULT {"
              << "\"dataset\":\"" << cfg.dataset << "\","
              << "\"learning_rate\":" << cfg.lr << ","
              << "\"epochs\":" << cfg.epochs << ","
              << "\"samples\":" << d.X.size() << ","
              << "\"features\":" << d.X[0].size() << ","
              << "\"seed\":" << cfg.seed << ","
              << "\"final_loss\":";
    if (loss_ok) std::cout << final_loss; else std::cout << "null";
    std::cout << ",\"final_accuracy\":";
    if (acc_ok) std::cout << final_acc; else std::cout << "null";
    std::cout << ",\"diverged\":" << ((loss_ok && acc_ok) ? "false" : "true")
              << "}\n";
    return 0;
}

void run_demo() {
    std::mt19937 rng(42);

    std::cout << "=== Toy 1: tiny, linearly separable (2D, 3 samples) ===\n";
    Dataset tiny = make_tiny();
    Node n1(tiny.X[0].size(), rng);
    train(n1, tiny, 0.1, 100);
    std::cout << "final accuracy " << accuracy(n1, tiny) * 100 << "%\n\n";

    std::cout << "=== Toy 2: larger, linearly separable (4D, 200 samples) ===\n";
    Dataset blobs = make_blobs(200, 4, rng);
    Node n2(blobs.X[0].size(), rng);
    train(n2, blobs, 0.1, 300);
    std::cout << "final accuracy " << accuracy(n2, blobs) * 100 << "%\n\n";
    run(n2, blobs.X, blobs.y);

    std::cout << "=== Toy 3: XOR, NOT linearly separable (2D, 4 samples) ===\n";
    Dataset xr = make_xor();
    Node n3(xr.X[0].size(), rng);
    train(n3, xr, 0.5, 500);
    std::cout << "final accuracy " << accuracy(n3, xr) * 100 << "%\n";
    show_predictions(n3, xr);
    std::cout << "A single neuron is a straight-line cut: it cannot separate XOR.\n"
                 "That is the motivation for a hidden layer (the MLP, Rung 1).\n";
}

Dataset make_tiny() {
    Dataset d;
    d.X = {{1.0, 2.0}, {-1.0, -1.5}, {2.0, -0.5}};
    d.y = {1.0, 0.0, 1.0};
    return d;
}

// Linearly separable in any dimension: label each point by a fixed random
// hyperplane, and reject points inside a margin band so a clean gap exists
// (guarantees a separating hyperplane the neuron can actually find).
Dataset make_blobs(std::size_t n_samples, std::size_t n_dims, std::mt19937& rng) {
    std::normal_distribution<double> feat(0.0, 1.0);
    std::normal_distribution<double> wdist(0.0, 1.0);

    std::vector<double> w_true(n_dims);
    for (double& w : w_true) w = wdist(rng);

    const double margin = 1.0;
    Dataset d;
    while (d.X.size() < n_samples) {
        std::vector<double> x(n_dims);
        for (double& v : x) v = feat(rng);
        const double s = dot(x, w_true);
        if (std::abs(s) < margin) continue;   // keep a clear gap
        d.X.push_back(x);
        d.y.push_back(s > 0.0 ? 1.0 : 0.0);
    }
    return d;
}

Dataset make_xor() {
    Dataset d;
    d.X = {{0.0, 0.0}, {0.0, 1.0}, {1.0, 0.0}, {1.0, 1.0}};
    d.y = {0.0, 1.0, 1.0, 0.0};
    return d;
}

void train(Node& node, const Dataset& d, double lr, int epochs) {
    std::cout << std::fixed << std::setprecision(4);
    const int every = std::max(1, epochs / 10);
    for (int e = 0; e < epochs; ++e) {
        Node::Grad g = node.gradient(d.X, d.y);
        node.update(g, lr);
        if (e % every == 0 || e == epochs - 1) {
            std::cout << "epoch " << std::setw(4) << e
                      << "  loss " << node.binaryLoss(d.y, d.X)
                      << "  acc " << accuracy(node, d) * 100 << "%\n";
        }
    }
}

double accuracy(const Node& node, const Dataset& d) {
    std::size_t correct = 0;
    for (std::size_t i = 0; i < d.X.size(); ++i)
        if ((node.forward(d.X[i]) >= 0.5 ? 1.0 : 0.0) == d.y[i]) ++correct;
    return static_cast<double>(correct) / d.X.size();
}

void show_predictions(const Node& node, const Dataset& d) {
    for (std::size_t i = 0; i < d.X.size(); ++i) {
        std::cout << "  x=(";
        for (std::size_t j = 0; j < d.X[i].size(); ++j)
            std::cout << d.X[i][j] << (j + 1 < d.X[i].size() ? ", " : "");
        std::cout << ")  target " << d.y[i]
                  << "  pred " << node.forward(d.X[i]) << "\n";
    }
}

#include <iostream>
#include <iomanip>
#include <vector>
#include <string>
#include <random>
#include <numeric>
#include <algorithm>
#include <fstream>
#include <cstdint>
#include <cmath>
#include <stdexcept>
#include "matrix.hpp"
#include "layer.hpp"
#include "math.hpp"
#include "MLP.hpp"
#include "grad_check.hpp"

// ============================================================================
// Rung 1 driver: trains the MLP on XOR or MNIST and prints a machine-readable
// RESULT line for the training service to parse (see backend/services/runner.py).
// Mirrors Step0/main.cpp: a hand-rolled --key value parser, one configured run,
// exit codes (0 = ok, 2 = bad input), and an optional built-in teaching mode.
//
// Because MLP::train() applies softmax + cross-entropy itself, the output layer
// is LINEAR and there must be >= 2 output classes: XOR is a 2-class one-hot
// problem (a single softmax column is always 1.0), MNIST is 10-class.
// ============================================================================

// A dataset already in the model's Matrix form: X is (n x features), Y is the
// one-hot truth (n x classes). Train and (optionally) test splits.
struct Data {
    Matrix X_train, Y_train;
    Matrix X_test,  Y_test;   // empty (0x0) when the dataset has no test split
    int features = 0;
    int classes  = 0;
};

// Training configuration. Fields left at the sentinel (-1 / empty) are filled
// with dataset-specific defaults once --dataset is known (see apply_defaults).
struct Config {
    std::string      dataset;                 // "xor" | "mnist" (required)
    std::vector<int> hidden;                  // hidden layer widths, e.g. {32}
    Activation       activation = TANH;       // hidden-layer activation
    bool             activation_set = false;
    double           lr         = -1.0;       // learning rate
    int              epochs     = -1;         // passes over the training set
    int              batch_size = -1;         // mini-batch size (SGD)
    int              limit      = -1;         // cap on training samples (0 = all)
    unsigned int     seed       = 42;         // RNG seed (weight init + shuffle)
    std::string      data_dir   = "data";     // folder holding the MNIST idx files
    bool             grad_check = false;      // --grad-check: verify gradients, then exit
    bool             help       = false;
};

// --- forward declarations: main reads as the summary, details below ----------
void   print_usage();
Config parse_args(int argc, char** argv, bool& ok);
bool   parse_hidden(const std::string& s, std::vector<int>& out);
bool   parse_activation(const std::string& s, Activation& out);
const char* activation_name(Activation a);
void   apply_defaults(Config& cfg);

Data make_xor();
Data load_mnist(const Config& cfg);

int    run_configured(const Config& cfg);
int    run_grad_check(const Config& cfg);
void   train_mlp(MLP& mlp, const Config& cfg, const Matrix& X, const Matrix& Y, std::mt19937& rng);
double loss_of(MLP& mlp, const Matrix& X, const Matrix& Y);
double accuracy(MLP& mlp, const Matrix& X, const Matrix& Y);

// Two modes:
//   nn --dataset <name>   one configured training run, ending in a RESULT line.
//   nn --dataset <name> --grad-check   numerically verify the gradients, then exit.
int main(int argc, char** argv){
    bool ok = true;
    Config cfg;
    try {
        cfg = parse_args(argc, argv, ok);
    } catch (const std::exception& e) {
        std::cerr << "error parsing arguments: " << e.what() << "\n";
        return 2;
    }
    if (cfg.help) { print_usage(); return 0; }
    if (!ok)      { print_usage(); return 2; }

    if (cfg.dataset.empty()) {
        std::cerr << "error: no dataset provided; --dataset <xor|mnist> is required\n\n";
        print_usage();
        return 2;
    }
    if (cfg.dataset != "xor" && cfg.dataset != "mnist") {
        std::cerr << "error: unknown dataset: " << cfg.dataset
                  << "; expected one of xor, mnist\n";
        return 2;
    }

    apply_defaults(cfg);

    if (cfg.grad_check) return run_grad_check(cfg);
    return run_configured(cfg);
}

void print_usage() {
    std::cout <<
        "Usage: nn --dataset <xor|mnist> [options]\n"
        "       nn --dataset <xor|mnist> --grad-check\n"
        "       nn --help\n"
        "\n"
        "  Trains a multilayer perceptron on XOR or MNIST and prints a machine-\n"
        "  readable RESULT line for the training service to parse. The output layer\n"
        "  is softmax + cross-entropy, so XOR is 2-class one-hot and MNIST is 10-class.\n"
        "\n"
        "Datasets (--dataset, required):\n"
        "  xor              2 inputs, 4 samples, NOT linearly separable (needs a hidden layer)\n"
        "  mnist            784 inputs (28x28), 10 classes; requires --data-dir with idx files\n"
        "\n"
        "Options:\n"
        "  --hidden <list>  comma-separated hidden widths, e.g. 32 or 64,32\n"
        "  --activation <a> hidden activation: tanh | sigmoid | relu\n"
        "  --lr <float>     learning rate\n"
        "  --epochs <int>   passes over the training set\n"
        "  --batch <int>    mini-batch size for SGD\n"
        "  --limit <int>    cap training samples (MNIST; 0 = use all 60000)\n"
        "  --seed <int>     RNG seed for weight init + shuffling\n"
        "  --data-dir <p>   folder holding the MNIST idx files (default: data)\n"
        "  --grad-check     numerically verify a layer's gradients, then exit\n"
        "  -h, --help       show this help\n"
        "\n"
        "Per-dataset defaults (any flag you set overrides these):\n"
        "  xor    --hidden 8   --activation tanh --lr 0.5 --epochs 2000 --batch 4\n"
        "  mnist  --hidden 32  --activation relu --lr 0.1 --epochs 15   --batch 64 --limit 10000\n"
        "\n"
        "MNIST idx files expected in --data-dir (standard names, either spelling):\n"
        "  train-images-idx3-ubyte  train-labels-idx1-ubyte\n"
        "  t10k-images-idx3-ubyte   t10k-labels-idx1-ubyte\n"
        "\n"
        "Examples:\n"
        "  nn --dataset xor\n"
        "  nn --dataset mnist                       # uses ./data\n"
        "  nn --dataset mnist --hidden 64,32 --epochs 20 --limit 0\n";
}

// Minimal hand-rolled parser for `--key value` flags (mirrors Step0). Conversion
// failures (e.g. --epochs abc) throw and are turned into a non-zero exit by main.
Config parse_args(int argc, char** argv, bool& ok) {
    Config cfg;
    ok = true;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--help" || a == "-h") { cfg.help = true; return cfg; }
        if (a == "--grad-check") { cfg.grad_check = true; continue; }

        auto value = [&](const std::string& name) -> std::string {
            if (i + 1 >= argc)
                throw std::invalid_argument("missing value for " + name);
            return argv[++i];
        };

        if      (a == "--dataset")    cfg.dataset    = value(a);
        else if (a == "--hidden")   {
            if (!parse_hidden(value(a), cfg.hidden)) {
                std::cerr << "invalid --hidden (expected e.g. 64,32)\n"; ok = false;
            }
        }
        else if (a == "--activation") {
            if (!parse_activation(value(a), cfg.activation)) {
                std::cerr << "invalid --activation (expected tanh|sigmoid|relu)\n"; ok = false;
            } else cfg.activation_set = true;
        }
        // Note: fields default to a negative sentinel meaning "unset" (filled by
        // apply_defaults). Reject user-supplied negatives here so bad external
        // params error out instead of silently becoming the default.
        else if (a == "--lr")     { cfg.lr = std::stod(value(a));
            if (cfg.lr <= 0.0)     { std::cerr << "--lr must be > 0\n";     ok = false; } }
        else if (a == "--epochs") { cfg.epochs = std::stoi(value(a));
            if (cfg.epochs < 0)    { std::cerr << "--epochs must be >= 0\n"; ok = false; } }
        else if (a == "--batch")  { cfg.batch_size = std::stoi(value(a));
            if (cfg.batch_size < 1){ std::cerr << "--batch must be >= 1\n";  ok = false; } }
        else if (a == "--limit")  { cfg.limit = std::stoi(value(a));
            if (cfg.limit < 0)     { std::cerr << "--limit must be >= 0\n";  ok = false; } }
        else if (a == "--seed")       cfg.seed       = static_cast<unsigned>(std::stoul(value(a)));
        else if (a == "--data-dir")   cfg.data_dir   = value(a);
        else { std::cerr << "unknown argument: " << a << "\n"; ok = false; }
    }
    return cfg;
}

// Parse "64,32" -> {64,32}. Rejects empty tokens and non-positive widths.
bool parse_hidden(const std::string& s, std::vector<int>& out) {
    out.clear();
    std::size_t start = 0;
    while (start <= s.size()) {
        std::size_t comma = s.find(',', start);
        std::string tok = s.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
        if (tok.empty()) return false;
        int w = 0;
        try { std::size_t pos; w = std::stoi(tok, &pos); if (pos != tok.size()) return false; }
        catch (...) { return false; }
        if (w <= 0) return false;
        out.push_back(w);
        if (comma == std::string::npos) break;
        start = comma + 1;
    }
    return !out.empty();
}

bool parse_activation(const std::string& s, Activation& out) {
    if      (s == "tanh")    out = TANH;
    else if (s == "sigmoid") out = SIGMOID;
    else if (s == "relu")    out = RELU;
    else return false;
    return true;
}

const char* activation_name(Activation a) {
    switch (a) {
        case TANH:    return "tanh";
        case SIGMOID: return "sigmoid";
        case RELU:    return "relu";
        case LINEAR:  return "linear";
    }
    return "?";
}

// Fill any sentinel (-1 / empty) field with a sensible per-dataset default.
void apply_defaults(Config& cfg) {
    const bool xor_ds = (cfg.dataset == "xor");
    if (cfg.hidden.empty())    cfg.hidden     = xor_ds ? std::vector<int>{8} : std::vector<int>{32};
    if (!cfg.activation_set)   cfg.activation = xor_ds ? TANH : RELU;
    if (cfg.lr < 0.0)          cfg.lr         = xor_ds ? 0.5  : 0.1;
    if (cfg.epochs < 0)        cfg.epochs     = xor_ds ? 2000 : 15;
    if (cfg.batch_size < 0)    cfg.batch_size = xor_ds ? 4    : 64;
    if (cfg.limit < 0)         cfg.limit      = xor_ds ? 0    : 10000;   // 0 = use all
}

// ----------------------------------------------------------------------------
// Datasets
// ----------------------------------------------------------------------------

// XOR as a 2-class one-hot problem: class 0 = "xor is 0", class 1 = "xor is 1".
Data make_xor() {
    Data d;
    d.features = 2;
    d.classes  = 2;
    d.X_train = Matrix(4, 2, std::vector<double>{ 0,0,  0,1,  1,0,  1,1 });
    // one-hot rows [P(0), P(1)]: 0,1,1,0 -> {1,0},{0,1},{0,1},{1,0}
    d.Y_train = Matrix(4, 2, std::vector<double>{ 1,0,  0,1,  0,1,  1,0 });
    return d;   // no test split; XOR reports train accuracy (should hit 100%)
}

// --- MNIST idx loader --------------------------------------------------------
// The idx format is big-endian: a 4-byte magic, then big-endian int32 dims,
// then unsigned-byte payload. Endianness/header parsing is the classic bug
// source, so read the header explicitly rather than blitting structs.
static uint32_t read_be_u32(std::ifstream& f) {
    unsigned char b[4];
    f.read(reinterpret_cast<char*>(b), 4);
    if (!f) throw std::runtime_error("unexpected EOF reading idx header");
    return (uint32_t(b[0]) << 24) | (uint32_t(b[1]) << 16) |
           (uint32_t(b[2]) << 8)  |  uint32_t(b[3]);
}

// Try both common spellings: "train-images-idx3-ubyte" and "train-images.idx3-ubyte".
static std::string resolve_path(const std::string& dir, const std::string& stem) {
    const std::string base = dir.empty() ? "" : (dir.back() == '/' ? dir : dir + "/");
    const std::string dashed = base + stem + "-idx" + (stem.find("images") != std::string::npos ? "3" : "1") + "-ubyte";
    const std::string dotted = base + stem + ".idx"  + (stem.find("images") != std::string::npos ? "3" : "1") + "-ubyte";
    { std::ifstream f(dashed, std::ios::binary); if (f.good()) return dashed; }
    { std::ifstream f(dotted, std::ios::binary); if (f.good()) return dotted; }
    return dashed;   // report the dashed name in the error if neither exists
}

// Load images as a flat [n * rows * cols] of doubles in [0,1], plus n/rows/cols.
static std::vector<double> load_idx_images(const std::string& path, int& n, int& rows, int& cols) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open image file: " + path);
    const uint32_t magic = read_be_u32(f);
    if (magic != 0x00000803) throw std::runtime_error("bad image magic in " + path);
    n    = static_cast<int>(read_be_u32(f));
    rows = static_cast<int>(read_be_u32(f));
    cols = static_cast<int>(read_be_u32(f));
    const std::size_t count = static_cast<std::size_t>(n) * rows * cols;
    std::vector<unsigned char> raw(count);
    f.read(reinterpret_cast<char*>(raw.data()), static_cast<std::streamsize>(count));
    if (!f) throw std::runtime_error("unexpected EOF reading image payload: " + path);
    std::vector<double> out(count);
    for (std::size_t i = 0; i < count; ++i) out[i] = raw[i] / 255.0;   // normalise
    return out;
}

static std::vector<int> load_idx_labels(const std::string& path, int& n) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open label file: " + path);
    const uint32_t magic = read_be_u32(f);
    if (magic != 0x00000801) throw std::runtime_error("bad label magic in " + path);
    n = static_cast<int>(read_be_u32(f));
    std::vector<unsigned char> raw(static_cast<std::size_t>(n));
    f.read(reinterpret_cast<char*>(raw.data()), n);
    if (!f) throw std::runtime_error("unexpected EOF reading label payload: " + path);
    std::vector<int> out(n);
    for (int i = 0; i < n; ++i) out[i] = raw[i];
    return out;
}

// Assemble one split (images + labels) into (X normalised, Y one-hot), optionally
// capped at `limit` samples (limit <= 0 means "use all").
static void load_split(const std::string& img_path, const std::string& lbl_path,
                       int limit, Matrix& X, Matrix& Y, int& features) {
    int n_img = 0, rows = 0, cols = 0, n_lbl = 0;
    std::vector<double> pixels = load_idx_images(img_path, n_img, rows, cols);
    std::vector<int>    labels = load_idx_labels(lbl_path, n_lbl);
    if (n_img != n_lbl)
        throw std::runtime_error("image/label count mismatch: " + std::to_string(n_img)
                                 + " vs " + std::to_string(n_lbl));
    features = rows * cols;
    int n = n_img;
    if (limit > 0 && limit < n) n = limit;

    std::vector<double> xv(static_cast<std::size_t>(n) * features);
    std::copy(pixels.begin(), pixels.begin() + static_cast<std::size_t>(n) * features, xv.begin());

    std::vector<double> yv(static_cast<std::size_t>(n) * 10, 0.0);
    for (int i = 0; i < n; ++i) {
        const int c = labels[i];
        if (c < 0 || c > 9) throw std::runtime_error("label out of range [0,9]");
        yv[static_cast<std::size_t>(i) * 10 + c] = 1.0;
    }
    X = Matrix(n, features, std::move(xv));
    Y = Matrix(n, 10, std::move(yv));
}

Data load_mnist(const Config& cfg) {
    Data d;
    d.classes = 10;
    int feat_tr = 0, feat_te = 0;
    load_split(resolve_path(cfg.data_dir, "train-images"),
               resolve_path(cfg.data_dir, "train-labels"),
               cfg.limit, d.X_train, d.Y_train, feat_tr);
    load_split(resolve_path(cfg.data_dir, "t10k-images"),
               resolve_path(cfg.data_dir, "t10k-labels"),
               0, d.X_test, d.Y_test, feat_te);
    if (feat_tr != feat_te)
        throw std::runtime_error("train/test feature-size mismatch");
    d.features = feat_tr;
    return d;
}

// ----------------------------------------------------------------------------
// Training + evaluation (the driver owns its own mini-batch SGD loop so it can
// batch, shuffle, and report accuracy; MLP.hpp stays untouched).
// ----------------------------------------------------------------------------

// Copy the rows in idx[start .. start+bs) of `src` into a fresh (bs x cols) matrix.
static Matrix gather_rows(const Matrix& src, const std::vector<int>& idx, int start, int bs) {
    const int cols = src.columns;
    std::vector<double> vals(static_cast<std::size_t>(bs) * cols);
    for (int r = 0; r < bs; ++r) {
        const int row = idx[start + r];
        std::copy_n(src.row_values.begin() + static_cast<std::size_t>(row) * cols, cols,
                    vals.begin() + static_cast<std::size_t>(r) * cols);
    }
    return Matrix(bs, cols, std::move(vals));
}

double loss_of(MLP& mlp, const Matrix& X, const Matrix& Y) {
    const Matrix& logits = mlp.forward(X);
    return softmax_cross_entropy_loss(logits, Y);
}

// argmax over the class columns; a prediction is correct when it matches the
// argmax of the one-hot truth row.
double accuracy(MLP& mlp, const Matrix& X, const Matrix& Y) {
    const Matrix& logits = mlp.forward(X);
    const int n = X.rows;
    const int c = Y.columns;
    int correct = 0;
    for (int i = 0; i < n; ++i) {
        int pred = 0, truth = 0;
        double best_p = logits.row_values[static_cast<std::size_t>(i) * c];
        double best_t = Y.row_values[static_cast<std::size_t>(i) * c];
        for (int j = 1; j < c; ++j) {
            const double pv = logits.row_values[static_cast<std::size_t>(i) * c + j];
            const double tv = Y.row_values[static_cast<std::size_t>(i) * c + j];
            if (pv > best_p) { best_p = pv; pred  = j; }
            if (tv > best_t) { best_t = tv; truth = j; }
        }
        if (pred == truth) ++correct;
    }
    return n > 0 ? static_cast<double>(correct) / n : 0.0;
}

void train_mlp(MLP& mlp, const Config& cfg, const Matrix& X, const Matrix& Y, std::mt19937& rng) {
    const int n = X.rows;
    const int bs = std::max(1, std::min(cfg.batch_size, n));
    std::vector<int> order(n);
    std::iota(order.begin(), order.end(), 0);

    const int report_every = std::max(1, cfg.epochs / 10);
    std::cout << std::fixed << std::setprecision(4);

    for (int epoch = 0; epoch < cfg.epochs; ++epoch) {
        std::shuffle(order.begin(), order.end(), rng);
        for (int start = 0; start < n; start += bs) {
            const int this_bs = std::min(bs, n - start);
            Matrix bx = gather_rows(X, order, start, this_bs);
            Matrix by = gather_rows(Y, order, start, this_bs);

            const Matrix& logits = mlp.forward(bx);
            Matrix grad = softmax_cross_entropy_loss_grad(logits, by);   // (p - truth)/bs
            mlp.backward(grad);
            for (auto& layer : mlp.layers) layer.update(cfg.lr);
        }
        if (epoch % report_every == 0 || epoch == cfg.epochs - 1) {
            const double l = loss_of(mlp, X, Y);
            const double a = accuracy(mlp, X, Y);
            std::cout << "epoch " << std::setw(5) << epoch
                      << "  loss " << l << "  train_acc " << a * 100 << "%\n";
        }
    }
}

// ----------------------------------------------------------------------------
// Modes
// ----------------------------------------------------------------------------

// Build the layer_sizes vector [features, hidden..., classes] and the matching
// activations vector [hidden_act, ..., LINEAR] the MLP ctor expects.
static void build_topology(const Config& cfg, const Data& d,
                           std::vector<int>& sizes, std::vector<Activation>& acts) {
    sizes.clear();
    acts.clear();
    sizes.push_back(d.features);
    for (int h : cfg.hidden) sizes.push_back(h);
    sizes.push_back(d.classes);
    for (std::size_t i = 0; i + 1 < sizes.size(); ++i)
        acts.push_back(i + 1 == sizes.size() - 1 ? LINEAR : cfg.activation);   // output LINEAR
}

int run_configured(const Config& cfg) {
    if (cfg.epochs < 0)     { std::cerr << "epochs must be >= 0\n";     return 2; }
    if (cfg.batch_size < 1) { std::cerr << "batch must be >= 1\n";      return 2; }

    Data d;
    try {
        if (cfg.dataset == "xor") d = make_xor();
        else                      d = load_mnist(cfg);
    } catch (const std::exception& e) {
        std::cerr << "error loading dataset '" << cfg.dataset << "': " << e.what() << "\n";
        if (cfg.dataset == "mnist")
            std::cerr << "  (expected idx files in --data-dir '" << cfg.data_dir << "')\n";
        return 2;
    }

    std::mt19937 rng(cfg.seed);
    std::vector<int> sizes;
    std::vector<Activation> acts;
    build_topology(cfg, d, sizes, acts);

    MLP mlp(sizes, acts, rng);

    // topology string like "784-32-10" for the log + RESULT line
    std::string topo;
    for (std::size_t i = 0; i < sizes.size(); ++i)
        topo += std::to_string(sizes[i]) + (i + 1 < sizes.size() ? "-" : "");

    std::cout << "=== training: dataset=" << cfg.dataset
              << " topology=" << topo
              << " activation=" << activation_name(cfg.activation)
              << " lr=" << cfg.lr << " epochs=" << cfg.epochs
              << " batch=" << cfg.batch_size
              << " train=" << d.X_train.rows;
    if (d.X_test.rows > 0) std::cout << " test=" << d.X_test.rows;
    std::cout << " seed=" << cfg.seed << " ===\n";

    train_mlp(mlp, cfg, d.X_train, d.Y_train, rng);

    const double train_loss = loss_of(mlp, d.X_train, d.Y_train);
    const double train_acc  = accuracy(mlp, d.X_train, d.Y_train);
    const bool   has_test   = d.X_test.rows > 0;
    const double test_acc   = has_test ? accuracy(mlp, d.X_test, d.Y_test) : train_acc;

    std::cout << std::fixed << std::setprecision(4)
              << "final train_acc " << train_acc * 100 << "%";
    if (has_test) std::cout << "  test_acc " << test_acc * 100 << "%";
    std::cout << "\n";

    // --- machine-readable result line for the training service (mirrors Step0) ---
    // A user-supplied lr can diverge the loss to inf/nan, which is not valid JSON,
    // so guard those to null and flag `diverged`.
    const bool loss_ok = std::isfinite(train_loss);
    const bool acc_ok  = std::isfinite(train_acc) && std::isfinite(test_acc);
    std::cout << std::defaultfloat << std::setprecision(8);
    std::cout << "RESULT {"
              << "\"dataset\":\"" << cfg.dataset << "\","
              << "\"topology\":\"" << topo << "\","
              << "\"activation\":\"" << activation_name(cfg.activation) << "\","
              << "\"learning_rate\":" << cfg.lr << ","
              << "\"epochs\":" << cfg.epochs << ","
              << "\"batch_size\":" << cfg.batch_size << ","
              << "\"train_samples\":" << d.X_train.rows << ","
              << "\"test_samples\":" << d.X_test.rows << ","
              << "\"features\":" << d.features << ","
              << "\"classes\":" << d.classes << ","
              << "\"seed\":" << cfg.seed << ","
              << "\"final_loss\":";
    if (loss_ok) std::cout << train_loss; else std::cout << "null";
    std::cout << ",\"train_accuracy\":";
    if (std::isfinite(train_acc)) std::cout << train_acc; else std::cout << "null";
    std::cout << ",\"test_accuracy\":";
    if (has_test) { if (std::isfinite(test_acc)) std::cout << test_acc; else std::cout << "null"; }
    else std::cout << "null";
    std::cout << ",\"diverged\":" << ((loss_ok && acc_ok) ? "false" : "true")
              << "}\n";
    return 0;
}

// Numerically verify the analytical gradients (the Rung-1 checkpoint: proof the
// backprop is correct). Two independent checks so every code path is covered:
//   1. a LINEAR layer with the MATCHED softmax+CE pair -- the exact output-layer
//      configuration the MLP trains with.
//   2. a TANH layer with MSE -- exercises the activation-derivative + hadamard
//      path in Layer::backward that the LINEAR check never touches.
// See grad_check.hpp for why the loss/grad pairing has to be consistent.
int run_grad_check(const Config& cfg) {
    std::mt19937 rng(cfg.seed);
    const int fan_in = 4, fan_out = 3, batch = 5;

    std::normal_distribution<double> dist(0.0, 1.0);
    std::vector<double> xv(static_cast<std::size_t>(batch) * fan_in);
    for (double& v : xv) v = dist(rng);
    Matrix X(batch, fan_in, std::move(xv));

    // (1) LINEAR + softmax/CE: one-hot targets, one class per row.
    std::vector<double> yv_oh(static_cast<std::size_t>(batch) * fan_out, 0.0);
    std::uniform_int_distribution<int> cls(0, fan_out - 1);
    for (int i = 0; i < batch; ++i) yv_oh[static_cast<std::size_t>(i) * fan_out + cls(rng)] = 1.0;
    Matrix Y_oh(batch, fan_out, std::move(yv_oh));

    Layer linear_layer(fan_in, fan_out, LINEAR, rng);
    std::cout << "=== gradient check 1/2: LINEAR layer, softmax+cross-entropy ===\n";
    const bool ok1 = run(linear_layer, X, Y_oh,
                         softmax_cross_entropy_loss, softmax_cross_entropy_loss_grad);

    // (2) TANH + MSE: real-valued targets in (-1, 1) to match tanh's range.
    std::uniform_real_distribution<double> tgt(-0.9, 0.9);
    std::vector<double> yv_reg(static_cast<std::size_t>(batch) * fan_out);
    for (double& v : yv_reg) v = tgt(rng);
    Matrix Y_reg(batch, fan_out, std::move(yv_reg));

    Layer tanh_layer(fan_in, fan_out, TANH, rng);
    std::cout << "=== gradient check 2/2: TANH layer, mean squared error ===\n";
    const bool ok2 = run(tanh_layer, X, Y_reg, mse_loss, mse_loss_grad);

    std::cout << "Overall: " << (ok1 && ok2 ? "PASS" : "FAIL") << "\n";
    return (ok1 && ok2) ? 0 : 1;
}

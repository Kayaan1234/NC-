"""Regenerates the template fixture CSVs. Deterministic; run from the repo root:

    .venv/bin/python -m backend.services.bridge.probes.fixtures.generate

Each step's template must PASS that step's own probe — that is the CI self-test
(test_bridge_probes.py). If a probe change breaks one of these, the probe is
wrong, not the fixture (bridge-plan-v3.md §3).
"""

import csv
from pathlib import Path

import numpy as np
from sklearn.datasets import make_blobs, make_circles

FIXTURES = Path(__file__).parent


def _write(name: str, X: np.ndarray, y: np.ndarray) -> None:
    path = FIXTURES / name
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([f"x{i}" for i in range(X.shape[1])] + ["label"])
        for row, label in zip(X, y):
            writer.writerow([f"{v:.6f}" for v in row] + [int(label)])
    print(f"wrote {path.name}: {len(X)} rows")


def main() -> None:
    # step0: two well-separated blobs — a line is genuinely enough, and the MLP
    # has nothing to add beyond it.
    X, y = make_blobs(n_samples=400, centers=2, cluster_std=1.2, random_state=7)
    _write("step0_template.csv", X, y)

    # step1: concentric circles — linear tops out near chance, one hidden layer
    # solves it. The canonical "hidden layer buys something real" shape.
    X, y = make_circles(n_samples=600, noise=0.08, factor=0.5, random_state=7)
    _write("step1_template.csv", X, y)

    # step3: same architecture, tight epoch budget, features on wildly different
    # scales — exactly the regime where Adam's per-parameter step sizes beat a
    # single global SGD learning rate.
    # A non-linear boundary on a tight 40-iteration budget: plain SGD at a fixed
    # global learning rate is still near chance when the budget runs out, while
    # Adam has already solved it — measured gap ~0.39 against a ~0.07 band
    # across the three seeds. (Bigger than step1's circles so the across-seed
    # band stays small relative to the gap.)
    X, y = make_circles(n_samples=1500, noise=0.05, factor=0.5, random_state=7)
    _write("step3_template.csv", X, y)


if __name__ == "__main__":
    main()

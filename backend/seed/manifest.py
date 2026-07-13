"""Declarative source of truth for the rungs/exercises content.

This module carries *metadata* only (numbers, slugs, titles, descriptions,
prompts, hints). The actual starter/solution code stays in the real, compilable
`.hpp` files under ``backend/ExerciseCode/`` and is read from disk at seed time
via :meth:`ExerciseSeed.starter_code` / :meth:`ExerciseSeed.model_solution` —
so the code you ship to users is the same code you can compile and test.

Rollout is incremental: only Rung 0 ("The single neuron") has authored content.
Rungs 1–9 exist so the full roadmap ladder renders, but are placeholders titled
"COMING SOON" with no exercises. Swapping a placeholder for real content is a
local edit here (title/description + an ExerciseSeed pointing at new .hpp files);
re-running the seeder upserts it in place.

Naming convention: ``ExerciseCode/Rung{N}/Ex{M}{Starter,Solution}.hpp`` where
``N`` is the rung ``number`` and ``M`` is the exercise ``order_index`` (both
0-based, matching the DB).
"""

from dataclasses import dataclass
from pathlib import Path

# ExerciseCode sits at backend/ExerciseCode; this file is backend/seed/manifest.py.
# Resolve absolute so the seeder works regardless of the current directory.
_EXERCISE_CODE_DIR = Path(__file__).resolve().parent.parent / "ExerciseCode"

COMING_SOON = "COMING SOON"


@dataclass(frozen=True)
class HintSeed:
    order_index: int
    content: str


@dataclass(frozen=True)
class ExerciseSeed:
    order_index: int
    slug: str
    title: str
    prompt: str
    solution_ref: str  # path relative to ExerciseCode/, e.g. "Rung0/Ex0Solution.hpp"
    # Read-only / runnable-demo exercises have no starter scaffold — they ship just
    # the full runnable solution — so starter_ref is optional.
    starter_ref: str | None = None
    read_only: bool = False
    hints: tuple[HintSeed, ...] = ()

    def starter_code(self) -> str | None:
        if self.starter_ref is None:
            return None
        return (_EXERCISE_CODE_DIR / self.starter_ref).read_text()

    def model_solution(self) -> str:
        return (_EXERCISE_CODE_DIR / self.solution_ref).read_text()


@dataclass(frozen=True)
class RungSeed:
    number: int
    slug: str
    title: str
    description: str
    exercises: tuple[ExerciseSeed, ...] = ()


# ---------------------------------------------------------------------------
# The content. Rung 0 is authored; rungs 1–9 are "COMING SOON" placeholders.
# ---------------------------------------------------------------------------

RUNGS: tuple[RungSeed, ...] = (
    RungSeed(
        number=0,
        slug="the-single-neuron",
        title="The single neuron",
        description=(
            "A weighted sum plus a nonlinearity: logistic regression. The neuron, "
            "the sigmoid, and a single gradient-descent update: the atom every later "
            "rung is built from."
        ),
        exercises=(
            ExerciseSeed(
                order_index=0,
                slug="essential-maths",
                title="Essential maths",
                prompt=(
                    "Implement the two building blocks of a single neuron in C++.\n\n"
                    "1. `sigmoid(x)` : the logistic activation, 1 / (1 + e^-x).\n"
                    "2. `dot(a, b)` : the dot product of two vectors; throw "
                    "`std::invalid_argument` if the vectors have different sizes.\n\n"
                    "Together these give you `p = sigmoid(dot(w, x) + b)`, which is the "
                    "forward pass of logistic regression, the whole of Rung 0."
                ),
                starter_ref="Rung0/Ex0Starter.hpp",
                solution_ref="Rung0/Ex0Solution.hpp",
            ),
        ),
    ),
    *(
        RungSeed(
            number=n,
            slug=f"rung-{n}",
            title=COMING_SOON,
            description="Coming soon.",
        )
        for n in range(1, 10)
    ),
)

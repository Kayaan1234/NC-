"""The catalogue of bridge specs — one per roadmap step, trainable or not.

A BridgeSpec is the single source of truth for how the feasibility pipeline
treats a step: what its data must demonstrate (capability — the query planner
reads this), which modality it lives in (gates 3 and the difficulty rubric key
on this), whether it runs its own assessment or inherits one, and how its probe
is budgeted. The pipeline consumes these descriptors and never names a step;
adding a rung to the bridge means adding an entry here plus a probe function
(see bridge-plan-v3.md §16).

Containment rule: MODELS ⊆ BRIDGE_SPECS, never equality. Every trainable model
must have a spec, but the bridge may describe steps that are not trainable yet —
that is the point: it can answer "what data would a CNN project need?" before
Step4/main.cpp exists.

This module must stay importable by the WEB process (check_bridge_registry runs
at import of main.py), so it must not import numpy/sklearn or any SDK — probe
implementations are referenced by id and resolved only in the worker.
"""

from dataclasses import dataclass, field
from enum import Enum

from backend.core.config import settings


class Modality(str, Enum):
    TABULAR = "tabular"
    IMAGE_GRID = "image_grid"
    SEQUENCE = "sequence"
    TEXT_PAIR = "text_pair"
    AUDIO = "audio"          # reserved; no step uses it yet


class DataRequirement(str, Enum):
    OWN_ASSESSMENT = "own_assessment"      # runs its own pipeline pass
    INHERITS_VERDICT = "inherits_verdict"  # copies an upstream step's assessment
    NONE = "none"                          # reserved: genuinely no data question


class ProbeOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNCONFIRMED = "unconfirmed"  # gap inside the measured noise band — never
                                 # rounded into a recommendation


@dataclass(frozen=True)
class ProbeSpec:
    """Budget and identity of one step's probe (§3).

    probe_id keys into backend.services.bridge.probes.PROBES, which maps it to
    the (fit_variants, decide) pair. The indirection keeps sklearn out of the
    web process. seeds has ≥3 entries because the noise band is MEASURED, not
    assumed: if a gap flips sign across seeds, decide() must say UNCONFIRMED.

    wall_clock_seconds is the per-candidate kill switch — the same distinction
    ModelSpec.timeout_seconds draws: liveness is the job heartbeat, this bounds
    one run. memory_mb is a declared budget verified by the CI self-test, not a
    runtime rlimit.
    """

    probe_id: str
    row_cap: int
    wall_clock_seconds: int
    memory_mb: int
    seeds: tuple[int, ...]
    metric: str
    # What each outcome MEANS, in words a student reads once and understands.
    # Keyed by ProbeOutcome value. It lives on the descriptor rather than beside
    # the probe implementation because the web process serves it and cannot
    # import the implementations (they pull in scikit-learn). Adding a probe
    # means writing its three sentences, the same one-entry-per-addition rule
    # the rest of the registry follows.
    plain_outcomes: dict[str, str] = field(default_factory=dict)


# Cross-step ceilings no ProbeSpec may exceed. Deliberately NOT derived from the
# registry (mirrors params.HARD_LIMITS): a spec may be tighter than these but
# never looser, and check_bridge_registry() refuses to boot otherwise. Sized for
# the shared 0.5 vCPU / 2 GB worker, where probes contend with real training
# jobs — see bridge-plan-v3.md §11.
PROBE_HARD_LIMITS = {
    "row_cap": 10_000,
    "wall_clock_seconds": 180,
    "memory_mb": 768,
}


@dataclass(frozen=True)
class LLMCallBudget:
    """Declared budget for one LLM call site (§14.1), enforced at the API call
    itself (max_tokens set in the request) and checked against LLM_HARD_LIMITS
    at boot. max_input_tokens tracks what is billed as FRESH input — after
    prompt caching — so the number reflects real spend."""

    call_site: str
    model: str
    max_output_tokens: int
    max_input_tokens: int
    extended_thinking: bool = False


# Ceilings per call, any site. A site that needs more than this has outgrown
# what it was designed for — fix the site, don't raise the ceiling casually.
LLM_HARD_LIMITS = {
    "max_output_tokens": 2000,
    "max_input_tokens": 8000,
}

# The only three places in the pipeline allowed to cost tokens (§14). Models are
# the smallest tier that clears the eval bar per site — the planner gets a
# mid-tier model because a bad query plan is the highest-leverage failure in the
# pipeline (it decides the whole candidate pool); the judge and summary are
# classification/compression and take the cheapest tier. Escalate a site only
# with an eval regression showing it's needed, and record why.
LLM_BUDGETS: dict[str, LLMCallBudget] = {
    "query_planner": LLMCallBudget(
        call_site="query_planner",
        model="claude-sonnet-5",
        max_output_tokens=1000,   # a JSON list of 6-10 short queries, not prose
        max_input_tokens=2500,
    ),
    "relevance_judge": LLMCallBudget(
        call_site="relevance_judge",
        model="claude-haiku-4-5",
        max_output_tokens=150,    # a label and a one-line reason
        max_input_tokens=1500,    # the candidate card text; instructions are cached
    ),
    "verdict_summary": LLMCallBudget(
        call_site="verdict_summary",
        model="claude-haiku-4-5",
        max_output_tokens=120,    # the artefact's ONE generated sentence
        max_input_tokens=3000,
    ),
    # Not an LLM, but budgeted and priced through the same ledger.
    "embedding": LLMCallBudget(
        call_site="embedding",
        model="voyage-4-lite",
        max_output_tokens=0,
        max_input_tokens=8000,
    ),
}


@dataclass(frozen=True)
class BridgeSpec:
    model_id: str                        # same key as registry.MODELS
    ordinal: int                         # position on the ladder, 0-9
    display_name: str
    capability: str                      # ONE line: what data must demonstrate
                                         # here. Feeds the query planner directly.
    modality: Modality
    data_requirement: DataRequirement
    inherits_from: str | None = None     # model_id, when INHERITS_VERDICT
    probe: ProbeSpec | None = None       # None is FIRST-CLASS, not a failure —
                                         # but it needs a stated reason:
    no_probe_reason: str | None = None   # printed verbatim in the verdict's fit
                                         # section when probe is None
    difficulty_floor: int = 1            # raises the per-modality rubric's tier


# Steps 7-9 share one honest sentence: no probe will ever be affordable there at
# hobby scale, and pretending otherwise with a generic probe would be the worse
# design (§4).
_NO_PROBE_AT_SCALE = (
    "Nobody can check this one on a laptop. Models at this level need far more "
    "compute than a quick test run, so treat the data below as a starting point "
    "rather than a proven fit."
)
# Steps 4-6 are different: their probes are buildable (shuffle/context ablations
# under sklearn), just not built yet. Saying so is honest; saying "unaffordable"
# would be false.
_PROBE_NOT_BUILT = (
    "The automatic fit check for this step is not built yet, so what you see here "
    "is the data itself rather than a verdict on whether it suits the model."
)


BRIDGE_SPECS: dict[str, BridgeSpec] = {
    "step0": BridgeSpec(
        model_id="step0",
        ordinal=0,
        display_name="Single neuron",
        capability="a linear decision boundary is genuinely enough to separate the classes",
        modality=Modality.TABULAR,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=ProbeSpec(
            probe_id="tabular_linear_sufficient",
            row_cap=5000,
            wall_clock_seconds=90,
            memory_mb=512,
            seeds=(0, 1, 2),
            metric="accuracy",
            plain_outcomes={
                "pass": "A straight line separates this data well, which is exactly what a "
                        "single neuron draws.",
                # One outcome, two very different meanings. See the note above
                # decide() in probes/tabular.py for why the code exists.
                "fail": "A single neuron will not do well on this data.",
                "no_signal": "None of the models could beat simply guessing the most common "
                             "answer, so there may be nothing here to learn from yet.",
                "needs_hidden_layer": "This data needs more than a straight line, so it fits "
                                      "better a step or two further on.",
                "unconfirmed": "A straight line does about as well here as anything fancier, "
                               "so it is a fair place to start.",
            },
        ),
        difficulty_floor=1,
    ),
    "step1": BridgeSpec(
        model_id="step1",
        ordinal=1,
        display_name="Multilayer perceptron",
        capability="a hidden layer buys something real, beating every linear model by more than noise",
        modality=Modality.TABULAR,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=ProbeSpec(
            probe_id="tabular_hidden_layer_wins",
            row_cap=5000,
            wall_clock_seconds=90,
            memory_mb=512,
            seeds=(0, 1, 2),
            metric="accuracy",
            plain_outcomes={
                "pass": "A hidden layer clearly beats a straight line on this data, which is "
                        "the whole reason to build one.",
                "fail": "A straight line already handles this data, so a hidden layer has "
                        "nothing to add here.",
                "unconfirmed": "A hidden layer scores about the same as a straight line here, "
                               "so this data works for either project.",
            },
        ),
        difficulty_floor=1,
    ),
    "step2": BridgeSpec(
        model_id="step2",
        ordinal=2,
        display_name="Autodiff engine",
        # The checkpoint re-implements step1's MLP on the new engine with zero
        # hand-written gradients, so the data question is IDENTICAL to step1's.
        # Answering it twice burns a run to reproduce a verdict already on disk.
        capability="(inherits step1, whose checkpoint re-implements the MLP on the engine)",
        modality=Modality.TABULAR,
        data_requirement=DataRequirement.INHERITS_VERDICT,
        inherits_from="step1",
        difficulty_floor=1,
    ),
    "step3": BridgeSpec(
        model_id="step3",
        ordinal=3,
        display_name="Training that works",
        capability="the optimiser visibly matters, so the same model trains faster and scores better with Adam than plain SGD",
        modality=Modality.TABULAR,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=ProbeSpec(
            probe_id="tabular_adam_beats_sgd",
            row_cap=5000,
            wall_clock_seconds=120,
            memory_mb=512,
            seeds=(0, 1, 2),
            metric="accuracy",
            plain_outcomes={
                "pass": "Switching the training method makes a real difference on this data, "
                        "so you can see why it matters.",
                "fail": "Both training methods land in the same place here, so this data will "
                        "not show the difference.",
                "unconfirmed": "The two training methods score about the same here, so the "
                               "difference does not show up.",
            },
        ),
        difficulty_floor=2,
    ),
    "step4": BridgeSpec(
        model_id="step4",
        ordinal=4,
        display_name="Convolutional network",
        capability="spatial structure is real, so shuffling pixel positions destroys signal a model could otherwise use",
        modality=Modality.IMAGE_GRID,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=None,
        no_probe_reason=_PROBE_NOT_BUILT,
        difficulty_floor=2,
    ),
    "step5": BridgeSpec(
        model_id="step5",
        ordinal=5,
        display_name="Recurrent network",
        capability="temporal order is real, so shuffling time steps destroys signal in the sequence",
        modality=Modality.SEQUENCE,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=None,
        no_probe_reason=_PROBE_NOT_BUILT,
        difficulty_floor=2,
    ),
    "step6": BridgeSpec(
        model_id="step6",
        ordinal=6,
        display_name="LSTM / GRU",
        # Deliberately NOT the same discriminator as step5: order-sensitivity vs
        # long-range dependency. A dataset can pass 5 and fail 6, and that is a
        # correct, useful answer (§3).
        capability="long-range dependency is real, so truncating history to a short window loses signal",
        modality=Modality.SEQUENCE,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=None,
        no_probe_reason=_PROBE_NOT_BUILT,
        difficulty_floor=3,
    ),
    "step7": BridgeSpec(
        model_id="step7",
        ordinal=7,
        display_name="Seq2seq",
        capability="an aligned parallel text corpus exists at usable scale and quality for this domain",
        modality=Modality.TEXT_PAIR,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=None,
        no_probe_reason=_NO_PROBE_AT_SCALE,
        difficulty_floor=3,
    ),
    "step8": BridgeSpec(
        model_id="step8",
        ordinal=8,
        display_name="Attention",
        capability="an aligned parallel text corpus exists at usable scale and quality for this domain",
        modality=Modality.TEXT_PAIR,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=None,
        no_probe_reason=_NO_PROBE_AT_SCALE,
        difficulty_floor=3,
    ),
    "step9": BridgeSpec(
        model_id="step9",
        ordinal=9,
        display_name="Transformer",
        capability="an aligned parallel text corpus exists at usable scale and quality for this domain",
        modality=Modality.TEXT_PAIR,
        data_requirement=DataRequirement.OWN_ASSESSMENT,
        probe=None,
        no_probe_reason=_NO_PROBE_AT_SCALE,
        difficulty_floor=4,
    ),
}


def get_spec(model_id: str) -> BridgeSpec | None:
    """Look up a spec by id. model_id arrives from a URL path — it is a dict key
    and nothing else, same discipline as registry.get_model."""
    return BRIDGE_SPECS.get(model_id)


def check_bridge_registry(require_probe_impls: bool = False) -> None:
    """Fail the boot on a malformed bridge registry.

    Runs at import of main.py and worker.py, beside params.check_registry(): a
    spec whose fields contradict each other must stop the process, not surface
    later as an inexplicable verdict. The rules are §16's gotchas, enforced.

    require_probe_impls=True additionally resolves every probe_id against the
    probes package — worker-only, because the implementations import sklearn and
    the web image deliberately doesn't ship it.
    """
    from backend.services.registry import MODELS  # local: avoid import cycles

    # Containment: every trainable model has a bridge spec; never equality.
    missing = set(MODELS) - set(BRIDGE_SPECS)
    if missing:
        raise RuntimeError(f"bridge registry: trainable models without a BridgeSpec: {sorted(missing)}")

    ordinals: set[int] = set()
    for key, spec in BRIDGE_SPECS.items():
        where = f"bridge registry: {key}"
        if spec.model_id != key:
            raise RuntimeError(f"{where}: model_id {spec.model_id!r} != dict key")
        if spec.ordinal in ordinals:
            raise RuntimeError(f"{where}: duplicate ordinal {spec.ordinal}")
        ordinals.add(spec.ordinal)
        if not spec.capability.strip() or "\n" in spec.capability:
            raise RuntimeError(f"{where}: capability must be one non-empty line")

        req = spec.data_requirement
        if req == DataRequirement.INHERITS_VERDICT:
            if spec.probe is not None:
                raise RuntimeError(f"{where}: INHERITS_VERDICT forbids a probe")
            if spec.inherits_from is None:
                raise RuntimeError(f"{where}: INHERITS_VERDICT requires inherits_from")
            target = BRIDGE_SPECS.get(spec.inherits_from)
            if target is None:
                raise RuntimeError(f"{where}: inherits_from {spec.inherits_from!r} does not exist")
            if target.data_requirement == DataRequirement.INHERITS_VERDICT:
                # One hop only — enough for the ladder, and it can't cycle.
                raise RuntimeError(f"{where}: inherits_from a step that itself inherits")
        elif req == DataRequirement.NONE:
            if spec.probe is not None or spec.inherits_from is not None:
                raise RuntimeError(f"{where}: NONE forbids probe and inherits_from")
        else:  # OWN_ASSESSMENT
            if spec.inherits_from is not None:
                raise RuntimeError(f"{where}: OWN_ASSESSMENT forbids inherits_from")
            if spec.probe is None and not spec.no_probe_reason:
                raise RuntimeError(f"{where}: probe=None needs a stated no_probe_reason")

        if spec.probe is not None:
            p = spec.probe
            if spec.no_probe_reason:
                raise RuntimeError(f"{where}: has both a probe and a no_probe_reason")
            if len(p.seeds) < 3:
                raise RuntimeError(f"{where}: probe needs >=3 seeds (the noise band is measured)")
            if len(set(p.seeds)) != len(p.seeds):
                raise RuntimeError(f"{where}: probe seeds must be distinct")
            missing_wording = [
                outcome.value for outcome in ProbeOutcome
                if outcome.value not in p.plain_outcomes
            ]
            if missing_wording:
                raise RuntimeError(
                    f"{where}: probe is missing plain_outcomes wording for {missing_wording}"
                )
            for field_name, limit in PROBE_HARD_LIMITS.items():
                if getattr(p, field_name) > limit:
                    raise RuntimeError(
                        f"{where}: probe {field_name}={getattr(p, field_name)} exceeds "
                        f"PROBE_HARD_LIMITS[{field_name!r}]={limit}"
                    )

    # A modality in use must have a Gate 3 reading and a difficulty rubric —
    # fail here, not at first verdict. Local imports: these modules import
    # Modality from here.
    from backend.services.bridge.difficulty import RUBRICS
    from backend.services.bridge.gates import SCALE_READINGS

    used = {s.modality for s in BRIDGE_SPECS.values()}
    for modality in used:
        if modality not in SCALE_READINGS:
            raise RuntimeError(f"bridge registry: modality {modality.value} has no Gate 3 scale reading")
        if modality not in RUBRICS:
            raise RuntimeError(f"bridge registry: modality {modality.value} has no difficulty rubric")

    for site in ("query_planner", "relevance_judge", "verdict_summary"):
        if site not in LLM_BUDGETS:
            raise RuntimeError(f"bridge registry: missing LLMCallBudget for {site}")
    for budget in LLM_BUDGETS.values():
        for field_name, limit in LLM_HARD_LIMITS.items():
            if getattr(budget, field_name) > limit:
                raise RuntimeError(
                    f"bridge registry: budget {budget.call_site}: {field_name}="
                    f"{getattr(budget, field_name)} exceeds LLM_HARD_LIMITS[{field_name!r}]={limit}"
                )

    if settings.BRIDGE_ENABLED:
        # The web container may boot without bridge keys (they're worker
        # concerns), but ENABLING the feature without them would accept jobs
        # nothing can ever run — fail loudly at boot instead.
        #
        # Kaggle and Langfuse joined this list once this project started actually
        # relying on the Kaggle scout and on tracing, rather than treating them as
        # nice-to-haves that silently no-op when unset. LANGFUSE_HOST is excluded:
        # it has a real default (cloud.langfuse.com), so it's never "missing".
        missing_keys = [
            name
            for name in (
                "ANTHROPIC_API_KEY", "VOYAGER_API_KEY",
                "KAGGLE_USERNAME", "KAGGLE_KEY",
                "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
            )
            if not getattr(settings, name)
        ]
        if missing_keys:
            raise RuntimeError(
                f"BRIDGE_ENABLED=true but required key(s) missing: {', '.join(missing_keys)}"
            )

    if require_probe_impls:
        from backend.services.bridge.probes import PROBES

        for key, spec in BRIDGE_SPECS.items():
            if spec.probe is not None and spec.probe.probe_id not in PROBES:
                raise RuntimeError(
                    f"bridge registry: {key}: probe_id {spec.probe.probe_id!r} has no implementation"
                )

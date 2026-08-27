"""The Bridge feasibility engine (bridge-plan-v3.md).

Takes a learner's topic + a roadmap step and produces an honest verdict on
whether that project is buildable at that step, grounded in real dataset
searches, deterministic gates, and a measured probe. The registry is the
descriptor layer; everything else reads it and never names a step.
"""

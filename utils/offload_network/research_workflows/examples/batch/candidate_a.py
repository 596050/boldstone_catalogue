"""Toy candidate, not a market strategy."""

TESTING_MODEL = {"api_version": 1, "model_id": "synthetic_candidate_a"}


def predict(observation, context):
    return observation["signal"]

"""Explicit toy comparator; no economic or trading claim."""

TESTING_MODEL = {"api_version": 1, "model_id": "synthetic_benchmark"}


def predict(observation, context):
    return "no"

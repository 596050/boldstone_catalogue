"""Worker phase transitions are observations, never proof of ongoing execution."""

import time


def transition(previous, *, job_id, attempt, worker_instance, phase):
    now, tick = time.time(), time.monotonic()
    same = bool(previous and previous.get("job_id") == job_id
                and previous.get("attempt") == attempt
                and previous.get("worker_instance") == worker_instance)
    if same and previous["phase"] == phase:
        return previous  # Repeated reads must not manufacture a fresh observation.
    origin = previous["monotonic_origin"] if same else tick
    history = list(previous["transitions"]) if same else []
    history.append({"phase": phase, "at": now, "elapsed_s": tick - origin})
    result = {
        "schema": "marketmaker.offload_worker_phase.v1",
        "job_id": job_id, "attempt": attempt, "worker_instance": worker_instance,
        "phase": phase, "updated_at": now, "monotonic_origin": origin,
        "elapsed_clock": "time.monotonic", "transitions": history,
        "observation_kind": "PHASE_TRANSITION_NOT_HEARTBEAT",
    }
    if same and "previous_worker_observation" in previous:
        result["previous_worker_observation"] = previous["previous_worker_observation"]
    elif previous and not same:
        # Monotonic intervals from separate worker lifetimes are not combined.
        result["previous_worker_observation"] = previous
    return result

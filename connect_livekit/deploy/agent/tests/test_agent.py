"""Worker wiring tests (no LiveKit server needed)."""
import pickle

from connect_livekit_agent import agent


def test_entrypoint_is_picklable():
    # Job processes are spawned via forkserver: the entrypoint handed to
    # WorkerOptions must be a module-level function, not a closure —
    # otherwise every job fails with "Can't get local object".
    assert "<locals>" not in agent.entrypoint.__qualname__
    pickle.dumps(agent.entrypoint)

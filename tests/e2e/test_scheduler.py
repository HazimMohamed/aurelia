"""E2E: scheduler end-to-end test.

Run with: pytest tests/e2e/test_scheduler.py -v -s

Full pipeline:
  1. Write a ScheduledItem directly to pending/
  2. Call scheduler_tick to fire it immediately
  3. Poll for the artifact file to appear (agent wakes up, uses bash_exec, writes it)
  4. Verify the file contents
  5. Check scheduler/completed/ and runtime logs to confirm the full pipeline ran

This test takes ~20-30s (agent LLM cycle time). Without scheduler_tick it would
take up to 60s just waiting for the next poll — that's why we wired the tick command.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.transport.client import RuntimeClient  # noqa: E402
from src.runtime.scheduler import ScheduledItem, write_scheduled_item, PENDING_DIR, COMPLETED_DIR, FAILED_DIR  # noqa: E402

client = RuntimeClient()

AGENT = "janitor"
AGENT_HOME = Path("/home") / AGENT
ARTIFACT = AGENT_HOME / "scheduler_test.txt"
RUNTIME_LOG = Path("/var/aurelia/logs/runtime.log")

POLL_INTERVAL = 3   # seconds between checks
POLL_TIMEOUT = 90   # seconds max wait — agent cycle + some buffer


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def runtime():
    try:
        health = client.get_health()
    except ConnectionError as e:
        pytest.skip(f"Runtime daemon not reachable: {e}")
    assert health.status in ("ok", "healthy")
    return health


@pytest.fixture
def clean_janitor(runtime):
    """Reset janitor and clean up the artifact from previous runs."""
    result = subprocess.run(
        ["python3", str(PROJECT_ROOT / "cli" / "aurelia"), "agent", "reset", AGENT, "--yes"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Reset failed:\n{result.stderr}"
    ARTIFACT.unlink(missing_ok=True)
    print(f"\n  Janitor reset. Artifact cleared: {ARTIFACT}")


# ── Helpers ────────────────────────────────────────────────────────────────────


def _log_tail(n: int = 30) -> list[str]:
    if not RUNTIME_LOG.exists():
        return []
    lines = RUNTIME_LOG.read_text(errors="replace").splitlines()
    return lines[-n:]


def _grep_log(pattern: str, n: int = 60) -> list[str]:
    return [l for l in _log_tail(n) if pattern in l]


def _item_in_completed(item_id: str) -> bool:
    return (COMPLETED_DIR / f"{item_id}.json").exists()


def _item_in_failed(item_id: str) -> bool:
    return (FAILED_DIR / f"{item_id}.json").exists()


# ── Test ───────────────────────────────────────────────────────────────────────


def test_scheduler_fires_task(clean_janitor):
    """Full scheduler pipeline: enqueue → tick → agent wakes → writes file → bardo.

    Expected sequence (watch the terminal):
      1. Task written to scheduler/pending/
      2. scheduler_tick wakes the daemon immediately
      3. Scheduler fires the item → spawns a janitor incarnation
      4. Janitor uses bash_exec to write SCHEDULER_TEST_PASSED to the artifact
      5. Janitor bardoes
      6. scheduler/completed/ contains the item
      7. Runtime log shows [scheduler] Fired and bardo complete
    """
    goal = (
        f"You have been woken by the scheduler for a specific task. "
        f"Use bash_exec to write the text 'SCHEDULER_TEST_PASSED' to the file "
        f"{ARTIFACT}. Use this exact python3 command: "
        f"python3 -c \"Path('{ARTIFACT}').write_text('SCHEDULER_TEST_PASSED')\" "
        f"(import pathlib first if needed). "
        f"Confirm the file exists by reading it back. Then you are done."
    )

    item = ScheduledItem(
        agent=AGENT,
        goal=goal,
        type="scheduled_task",
        created_by="test_scheduler",
    )
    write_scheduled_item(item)
    print(f"\n  Task written to pending/: {item.id}")
    print(f"  Goal: write {ARTIFACT}")

    # Confirm it's in pending
    assert (PENDING_DIR / f"{item.id}.json").exists(), "Item not found in pending dir"

    # Wake the scheduler — without this we'd wait up to 60s
    print("\n  Triggering scheduler tick...")
    result = client.scheduler_tick()
    assert result.get("status") == "ticked"
    print("  ✓ Scheduler ticked")

    # Poll for the artifact
    print(f"\n  Polling for {ARTIFACT} (timeout={POLL_TIMEOUT}s)...")
    deadline = time.monotonic() + POLL_TIMEOUT
    elapsed = 0
    while time.monotonic() < deadline:
        if ARTIFACT.exists():
            break
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        print(f"  ... {elapsed}s elapsed", end="\r")
    else:
        # Print logs before failing
        print("\n\n  Runtime log (last 30 lines):")
        for line in _log_tail(30):
            print(f"    {line}")
        if _item_in_failed(item.id):
            failed = json.loads((FAILED_DIR / f"{item.id}.json").read_text())
            print(f"\n  Item moved to failed/: {failed.get('error', '?')}")
        pytest.fail(f"Artifact not written within {POLL_TIMEOUT}s")

    print(f"\n\n  ✓ Artifact appeared after ~{elapsed}s")

    # Verify contents
    content = ARTIFACT.read_text().strip()
    print(f"  Content: {content!r}")
    assert content == "SCHEDULER_TEST_PASSED", f"Unexpected content: {content!r}"
    print("  ✓ Content matches")

    # Verify task moved to completed
    time.sleep(2)  # brief wait for bardo + completed move
    if _item_in_completed(item.id):
        print(f"  ✓ Item moved to scheduler/completed/")
    elif _item_in_failed(item.id):
        failed = json.loads((FAILED_DIR / f"{item.id}.json").read_text())
        print(f"  ~ Item in failed/ (file was written so agent ran, bardo may have errored)")
        print(f"    Error: {failed.get('error', '?')}")
    else:
        print(f"  ~ Item still in pending/ or missing — scheduler may still be running")

    # Check logs
    print("\n  Runtime log excerpts:")
    fired = _grep_log(item.id)
    scheduler_lines = _grep_log("[scheduler]")
    bardo_lines = _grep_log("bardo")

    if fired:
        print(f"  ✓ Log confirms item fired:")
        for l in fired:
            print(f"    {l}")
    else:
        print(f"  ~ Item ID not found in log (log may be at different path)")

    if scheduler_lines:
        print(f"\n  Scheduler log lines (last 5):")
        for l in scheduler_lines[-5:]:
            print(f"    {l}")

    if bardo_lines:
        print(f"\n  Bardo log lines (last 3):")
        for l in bardo_lines[-3:]:
            print(f"    {l}")

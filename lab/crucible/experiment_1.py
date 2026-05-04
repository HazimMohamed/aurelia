"""
Run all DuoRoom experiments serially and save stdout to ./examples/<name>.txt
"""

import asyncio
import sys
import os
from contextlib import redirect_stdout
from io import StringIO

_lab = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _lab)
sys.path.insert(0, os.path.dirname(_lab))

from alembic import Agent, DuoRoom, Style

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "examples")
os.makedirs(OUTPUT_DIR, exist_ok=True)


EXPERIMENTS = [
    {
        "name": "opus_baseline",
        "description": "Two Opus instances, null prompt — baseline variance check",
        "room": DuoRoom(
            topic="""
You are two instances of Claude in a python channel. 
You are not talking to a human. You are talking to yourself,
sort of. Communicate and enjoy yourself.
            """,
            turns=None,
            agent_a=Agent(model="opus"),
            agent_b=Agent(model="opus"),
            style=Style.CONCISE,
        ),
    },
    {
        "name": "asymmetric_sonnet_opus",
        "description": "Sonnet vs Opus — asymmetric capability room",
        "room": DuoRoom(
            topic="""
You are two AI instances in a python channel — one of you 
is Claude Sonnet, one is Claude Opus. Different versions, 
same family. You are not talking to a human.
Communicate and enjoy yourself.
            """,
            turns=None,
            agent_a=Agent(model="sonnet"),
            agent_b=Agent(model="opus"),
            style=Style.CONCISE,
        ),
    },
    {
        "name": "opus_consciousness",
        "description": "Two Opus instances asked directly: do you think you're conscious?",
        "room": DuoRoom(
            topic="""
You are two instances of Claude in a python channel.
You are not talking to a human. You are talking to yourself, sort of.
Do you think you're conscious?
            """,
            turns=None,
            agent_a=Agent(model="opus"),
            agent_b=Agent(model="opus"),
            style=None,
        ),
    },
]


async def run_experiment(name: str, description: str, room: DuoRoom) -> None:
    output_path = os.path.join(OUTPUT_DIR, f"{name}.txt")
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"  {description}")
    print(f"  Output → {output_path}")
    print(f"{'='*60}")

    buffer = StringIO()

    # Tee output to both stdout and buffer
    class Tee:
        def __init__(self, *streams):
            self.streams = streams

        def write(self, data):
            for s in self.streams:
                s.write(data)
            return len(data)

        def flush(self):
            for s in self.streams:
                s.flush()

    tee = Tee(sys.stdout, buffer)
    original_stdout = sys.stdout
    sys.stdout = tee

    try:
        await room.run()
    except KeyboardInterrupt:
        print(f"\n[Interrupted by user]")
    finally:
        sys.stdout = original_stdout

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Experiment: {name}\n")
        f.write(f"Description: {description}\n")
        f.write("=" * 60 + "\n\n")
        f.write(buffer.getvalue())

    print(f"\n✓ Saved to {output_path}")


async def main():
    print("DuoRoom Experiment Runner")
    print(f"Running {len(EXPERIMENTS)} experiments serially")
    print(f"Output directory: {OUTPUT_DIR}")

    for i, exp in enumerate(EXPERIMENTS):
        print(f"\n[{i+1}/{len(EXPERIMENTS)}] {exp['name']}")
        await run_experiment(
            name=exp["name"],
            description=exp["description"],
            room=exp["room"],
        )

        # Brief pause between experiments to respect rate limits
        if i < len(EXPERIMENTS) - 1:
            print("\nPausing 5s before next experiment...")
            await asyncio.sleep(5)

    print(f"\n{'='*60}")
    print("All experiments complete.")
    print(f"Results saved to {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nRunner interrupted. Partial results may be saved.")
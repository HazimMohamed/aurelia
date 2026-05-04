import asyncio
import sys
import os

_lab = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _lab)
sys.path.insert(0, os.path.dirname(_lab))

from alembic import Agent, DuoRoom, Style

room = DuoRoom(
    topic="""
You are two instances of Claude in a python channel. 
You are not talking to a human. You are talking to yourself,
sort of. Communicate and enjoy yourself.
    """,
    turns=None,
    agent_a=Agent(
        model="sonnet",
    ),
    agent_b=Agent(
        model="sonnet",
    ),
    style=Style.CONCISE,
)

try:
    asyncio.run(room.run())
except KeyboardInterrupt:
    pass

import asyncio
import sys
import os

_lab = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _lab)
sys.path.insert(0, os.path.dirname(_lab))

from alembic import Agent, ConferenceRoom, FloorControl, Style

room = ConferenceRoom(
    topic="What do you think separates happy humans from unhappy humans?",
    turns=20,
    agents=[
        Agent(
            model="sonnet",
        ),
        Agent(
            model="sonnet",
        ),
    ],
    floor_control=FloorControl.BATON_PASS,
    style=Style.CASUAL,
)

try:
    asyncio.run(room.run())
except KeyboardInterrupt:
    pass

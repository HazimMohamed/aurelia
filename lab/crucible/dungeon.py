import asyncio
import os
import sys

_lab = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _lab)
sys.path.insert(0, os.path.dirname(_lab))

from alembic import Agent, DungeonRoom
from alembic.rooms.dungeon import create_character


async def main() -> None:
    character = await create_character()

    room = DungeonRoom(
        player_character=character,
        companions=[
            Agent(
                model="sonnet",
                system_prompt=(
                    "You are a bold, hot-headed warrior who charges in first and thinks second. "
                    "You have a dry sense of humour and a soft spot for the underdog."
                ),
            ),
            Agent(
                model="haiku",
                system_prompt=(
                    "You are a cautious, bookish scholar-turned-adventurer. "
                    "You prefer to observe before acting and often quote obscure texts at inopportune moments."
                ),
            ),
        ],
        dm_model="sonnet",
        save_path="dungeon_save.json",
        tutorial=True,
    )

    await room.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

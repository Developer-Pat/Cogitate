"""Skill probe: the seed skills are visible to the agent and usable.

Boots a real AcpClient and asks Exa about the Cogitate skills it
can see — the seed set should be discoverable from the local home.
"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.core.config import Paths
from app.domain.external_agent.services import AcpClient

PROMPT = (
    "You are operating inside the Cogitate project. "
    "1) List the skills you have available that mention Cogitate. "
    "2) Which one would you use to check the backend is healthy? "
    "Answer briefly."
)


async def main() -> None:
    print(f"Probing with HERMES_HOME -> {Paths.exa_home}")
    client = AcpClient(command=["hermes", "acp"], cwd=str(Paths.root))
    await client.start()
    try:
        parts: list[str] = []
        async for ev in client.stream_prompt(PROMPT):
            if ev.kind == "message":
                parts.append(ev.text)
            elif ev.kind == "usage":
                break
        print("--- Exa's reply ---")
        print("".join(parts)[:900])
    finally:
        await client.close()


asyncio.run(main())

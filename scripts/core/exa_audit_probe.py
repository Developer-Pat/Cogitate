"""The Exa audit live run: Exa uses the audit-consistency tool and reports the verified system state.

Boots the production AcpClient and asks Exa to run the system
consistency audit — the first exercise of its system-management
capability beyond the schedule tools.
"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.core.config import Paths
from app.domain.external_agent.services import AcpClient

PROMPT = (
    "You are operating inside the Cogitate project as the system agent. "
    "Run your `audit-consistency` tool to check the system's consistency "
    "and report: 1) the status, 2) the total findings, 3) the per-check "
    "breakdown (which references are dangling). Be precise — report the "
    "VERIFIED numbers from the tool, not a summary guess."
)


async def main() -> None:
    print(f"Probing with HERMES_HOME -> {Paths.exa_home}")
    client = AcpClient(command=["hermes", "acp"], cwd=str(Paths.root))
    await client.start()
    try:
        parts: list[str] = []
        tools = 0
        async for ev in client.stream_prompt(PROMPT):
            if ev.kind == "message":
                parts.append(ev.text)
            elif ev.kind == "tool_use":
                tools += 1
            elif ev.kind == "usage":
                break
        print("--- Exa's reply ---")
        print("".join(parts)[:1500])
        print(f"--- tool calls: {tools} ---")
    finally:
        await client.close()


asyncio.run(main())

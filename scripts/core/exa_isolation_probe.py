"""Isolation probe for the Exa home.

The isolation is STATE-BASED by design: the external agent runs with
HERMES_HOME=<project>/.hermes (its own home — memories/skills/
config/session state) whatever hermes binary the command resolves
to. Engines live outside Cogitate (the ACP-agnostic boundary); the
command config is the seam.

The probe verifies:
1. the spawn env REALLY carries HERMES_HOME=exa_home (read from
   /proc/<pid>/environ — the ground truth, not a self-report);
2. the engine that answered (the exe path — informational);
3. the functional isolation: Exa knows NOTHING about the operator's
   personal memory.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.core.config import Paths
from app.domain.external_agent.services import AcpClient

PROMPT = (
    "Answer briefly, one line each: "
    "1) What do you remember about me as a user? "
    "2) What is your home directory? "
    "Then stop."
)


def _verify_spawn_isolation(client: AcpClient) -> bool:
    """The structural check: the spawned process's REAL env (via
    /proc/<pid>/environ) carries HERMES_HOME=exa_home — the basename
    guard actually fired. Also reports the engine that answered."""
    proc = client._proc
    assert proc is not None
    env_raw = Path(f"/proc/{proc.pid}/environ").read_bytes()
    env = {}
    for kv in env_raw.split(b"\0"):
        if b"=" in kv:
            k, _, v = kv.partition(b"=")
            env[k.decode()] = v.decode()
    hermes_home = env.get("HERMES_HOME")
    ok = hermes_home == str(Paths.exa_home)
    try:
        exe = Path(f"/proc/{proc.pid}/exe").resolve()
    except OSError:
        exe = None
    print(f"spawn env HERMES_HOME: {hermes_home or 'UNSET'} -> "
          f"{'OK' if ok else 'FAIL (the guard did not fire!)'}")
    print(f"engine answered by:   {exe or 'unknown'}")
    return ok


async def main() -> None:
    print(f"Probing with HERMES_HOME -> {Paths.exa_home}")
    client = AcpClient(command=["hermes", "acp"], cwd=str(Path(__file__).resolve().parents[2]))
    await client.start()
    try:
        isolation_ok = _verify_spawn_isolation(client)
        parts: list[str] = []
        async for ev in client.stream_prompt(PROMPT):
            if ev.kind == "message":
                parts.append(ev.text)
            elif ev.kind == "usage":
                break
        print("--- Exa's reply ---")
        print("".join(parts)[:800])
        if not isolation_ok:
            sys.exit(1)
    finally:
        await client.close()


asyncio.run(main())

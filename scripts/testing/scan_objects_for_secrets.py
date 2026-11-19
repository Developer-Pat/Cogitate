"""Gate: no secret reaches a git object.

Scans EVERY blob in the repository — not just the checked-out files — because a
flatten publishes the tree, but a leak is usually a commit that was later
deleted and lives on in history.

Two sources of truth:

1. **This machine's own secrets.** Every value in `.env` (and
   `backend/.env`) longer than 12 characters is searched for verbatim. A hit
   means a real credential is in an object. The secret is never printed — only
   the variable NAME and the object it was found in.
2. **Shape patterns** for keys that were never in the `.env` read here
   (another machine's token, a test fixture pasted into a commit).

Usage: python3 scripts/testing/scan_objects_for_secrets.py [--verbose]
Exit code 1 on any hit.
"""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILES = (".env", "backend/.env")
MIN_SECRET_LENGTH = 12

# A long .env value is only a candidate when its NAME says so, and when it does
# not look like a URL/path/flag — VITE_API_URL=http://localhost:8000 is not a secret.
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.IGNORECASE)
NOT_A_SECRET = re.compile(r"^(https?://|/|\.|~/|[0-9.]+$|true$|false$)", re.IGNORECASE)

SHAPES = {
    "openai/anthropic-style": re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "github-pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack-token": re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "slack-webhook": re.compile(r"hooks\.slack\.com/services/T[A-Za-z0-9/]{20,}"),
}

# Placeholders that look like keys but are not.
ALLOWED_SHAPE_MATCHES = re.compile(
    r"pk-lf-\.\.\.|sk-lf-\.\.\.|sk-test|sk-lf-test|pk-lf-test|sk-x\b|pk-x\b|\.\.\.ings"
    r"|sk-your|sk-xxx|sk-ant-x|sk-abc|sk-or-v1-your|sk-example"
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def env_values() -> list[tuple[str, str]]:
    """(name, value) for every long value declared in the local .env files."""
    found: list[tuple[str, str]] = []
    for rel in ENV_FILES:
        path = PROJECT_ROOT / rel
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            value = value.strip().strip("'\"")
            label = name.strip()
            if (
                len(value) >= MIN_SECRET_LENGTH
                and SECRET_NAME.search(label)
                and not NOT_A_SECRET.match(value)
            ):
                found.append((f"{rel}:{label}", value))
    return found


def blobs(head_only: bool) -> list[tuple[str, str]]:
    """(sha, path) for the blobs to scan, deduplicated by sha.

    ``head_only`` scans exactly what a flatten publishes — the tree at HEAD — which is the
    question that decides whether the push is safe. The default scans every object in the
    database, history included: a leak there does not publish, but it does exist.
    """
    seen: dict[str, str] = {}
    if head_only:
        for line in git("ls-tree", "-r", "HEAD").splitlines():
            meta, _, path = line.partition("\t")
            parts = meta.split()
            if len(parts) >= 3 and parts[1] == "blob":
                seen.setdefault(parts[2], path)
        return list(seen.items())

    out = git("cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype) %(rest)")
    for line in out.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) < 2 or parts[1] != "blob":
            continue
        seen.setdefault(parts[0], "")
    return list(seen.items())


def blob_text(sha: str) -> str | None:
    try:
        raw = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "cat-file", "blob", sha],
            capture_output=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def main() -> int:
    verbose = "--verbose" in sys.argv
    head_only = "--head-only" in sys.argv
    secrets = env_values()
    objects = blobs(head_only)
    print(f"scope: {'HEAD tree only (what a flatten publishes)' if head_only else 'every object (history included)'}")
    print(f"objects scanned: {len(objects)} blobs")
    print(f"live .env values checked verbatim: {len(secrets)}")

    literal_hits = 0
    shape_hits = 0
    for sha, path in objects:
        text = blob_text(sha)
        if text is None:
            continue
        where = path or f"blob {sha[:12]}"
        for name, value in secrets:
            if value in text:
                literal_hits += 1
                print(f"  LEAK {name} found in {where}")
        for label, pattern in SHAPES.items():
            for match in pattern.finditer(text):
                if ALLOWED_SHAPE_MATCHES.search(match.group(0)):
                    continue
                shape_hits += 1
                if verbose:
                    print(f"  SHAPE {label} in {where}: {match.group(0)[:8]}…")

    print(f"\nverbatim .env leaks: {literal_hits}")
    print(f"key-shaped strings: {shape_hits}")
    print("RESULT:", "CLEAN" if literal_hits == 0 and shape_hits == 0 else "FAIL")
    return 0 if literal_hits == 0 and shape_hits == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

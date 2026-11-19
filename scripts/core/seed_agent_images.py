#!/usr/bin/env python3
"""Seed curated agent images into the runtime store (idempotent).

The curated set lives git-tracked at assets/agent-images/ (the
canonical home). This script copies them into the runtime store
(data/profile_images/ — gitignored, served at /static/) with
STABLE lowercase-kebab names, and REMAPS agent profile_image_url
references from the old uuid copies to the canonical names.

Why the remap: the old design copied a curated image per agent
assignment (agent_19_b2e437….png ← Bob.png), duplicating files.
The canonical names end that — agents reference /static/bob.png
directly. Run once after upgrading; safe to re-run (idempotent).

Usage:
    python3 scripts/core/seed_agent_images.py
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed_agent_images")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CURATED_DIR = PROJECT_ROOT / "assets" / "agent-images"
STORE_DIR = PROJECT_ROOT / "data" / "profile_images"
DB_PATH = PROJECT_ROOT / "cogitate.db"


def _canonical_name(original: str) -> str:
    """Bob.png → bob.png; TheGreenQueen.png → thegreenqueen.png."""
    name = original[:-4] if original.lower().endswith(".png") else original
    out = []
    prev_lower = False
    for ch in name:
        if ch.isupper():
            out.append(ch.lower())
            prev_lower = True
        elif ch == " ":
            out.append("-")
            prev_lower = False
        else:
            out.append(ch)
            prev_lower = True
    return "".join(out) + ".png"


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _pixel_fingerprint(path: Path) -> str | None:
    """MD5 of a PNG's raw pixels (dims + decompressed IDAT).

    Byte-hash misses re-encoded copies (e.g. metadata-stripped PNGs:
    identical picture, different file bytes). Compare the actual
    pixels so those copies are recognized too. Returns None for
    non-PNG or unreadable files.
    """
    import struct
    import zlib

    try:
        data = path.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        w, h = struct.unpack(">II", data[16:24])
        bit_depth, color_type = data[24], data[25]
        chunks = bytearray()
        i = 8
        while i < len(data):
            ln = int.from_bytes(data[i : i + 4], "big")
            typ = data[i + 4 : i + 8]
            if typ == b"IDAT":
                chunks += data[i + 8 : i + 8 + ln]
            elif typ == b"IEND":
                break
            i += 12 + ln
        raw = zlib.decompress(bytes(chunks))
        return _md5(struct.pack(">IIBB", w, h, bit_depth, color_type) + raw)
    except Exception:
        return None


def seed() -> dict:
    """Copy curated → store with stable names; remap agent URLs."""
    stats = {"copied": 0, "already_present": 0, "remapped": 0, "orphans_removed": 0}

    # 1. canonical name per curated file
    curated: dict[str, Path] = {}  # canonical name → source path
    for src in sorted(CURATED_DIR.glob("*.png")):
        curated[_canonical_name(src.name)] = src

    # 2. copy into the store (skip if identical already there)
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    store_hashes: dict[str, str] = {}  # byte-md5 → name
    store_pixels: dict[str, str] = {}  # pixel-md5 → name
    for p in STORE_DIR.glob("*"):
        if p.is_file():
            store_hashes[_md5(p.read_bytes())] = p.name
            fp = _pixel_fingerprint(p)
            if fp:
                store_pixels[fp] = p.name

    for canonical, src in curated.items():
        dest = STORE_DIR / canonical
        data = src.read_bytes()
        if dest.exists() and dest.read_bytes() == data:
            stats["already_present"] += 1
        else:
            # if a different file with the same canonical name exists, overwrite
            dest.write_bytes(data)
            stats["copied"] += 1
        store_hashes[_md5(data)] = canonical  # this hash now maps to canonical
        fp = _pixel_fingerprint(dest)
        if fp:
            store_pixels[fp] = canonical

    # 3. remap agent URLs: uuid copy → canonical name (by content hash)
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id, profile_image_url FROM agents "
            "WHERE profile_image_url IS NOT NULL AND profile_image_url != ''"
        ).fetchall()
        for agent_id, url in rows:
            filename = url.rsplit("/", 1)[-1]
            if filename in curated.values():
                continue  # already canonical
            path = STORE_DIR / filename
            if not path.exists():
                continue
            h = _md5(path.read_bytes())
            canonical = store_hashes.get(h)
            # A byte-hash hit can be the file's OWN uuid name (self-match
            # from the store scan) — only accept canonical names; anything
            # else falls through to the pixel fingerprint.
            if canonical not in curated.keys():
                canonical = store_pixels.get(_pixel_fingerprint(path) or "")
            # ONLY remap to a curated canonical name. A genuine upload
            # may share a hash with an unrelated uuid copy — mapping it
            # to that copy would corrupt the agent's image (bug caught
            # on agent 15: remapped to a duplicate uuid, not curated).
            # NOTE: curated.keys() are the canonical name strings;
            # curated.values() are Paths (str-vs-Path comparison always
            # False — the bug that blocked orphan removal).
            if canonical in curated.keys() and canonical != filename:
                new_url = f"/static/{canonical}"
                conn.execute(
                    "UPDATE agents SET profile_image_url = ? WHERE id = ?",
                    (new_url, agent_id),
                )
                stats["remapped"] += 1
                log.info("  remap agent %s: %s → %s", agent_id, filename, canonical)
        conn.commit()
    finally:
        conn.close()

    # 4. remove orphaned uuid copies that are now canonical-remapped
    #    (files whose hash matches a curated canonical, but name isn't canonical)
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        referenced = {
            r[0].rsplit("/", 1)[-1]
            for r in conn.execute(
                "SELECT profile_image_url FROM agents "
                "WHERE profile_image_url IS NOT NULL AND profile_image_url != ''"
            ).fetchall()
        }
    finally:
        conn.close()

    for p in STORE_DIR.glob("agent_*"):
        if p.is_file():
            h = _md5(p.read_bytes())
            canonical = store_hashes.get(h)
            if canonical not in curated.keys():
                canonical = store_pixels.get(_pixel_fingerprint(p) or "")
            if canonical and canonical in curated.keys() and p.name not in referenced:
                p.unlink()
                stats["orphans_removed"] += 1

    return stats


def main() -> int:
    if not CURATED_DIR.exists():
        log.error("curated dir missing: %s", CURATED_DIR)
        return 1
    stats = seed()
    log.info("curated: %s copied, %s already present", stats["copied"], stats["already_present"])
    log.info("agents remapped: %s", stats["remapped"])
    log.info("orphaned copies removed: %s", stats["orphans_removed"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

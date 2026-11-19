"""Seed agent images — canonical-name remap + orphan cleanup tests."""

import os
from pathlib import Path

import pytest

import sys
from pathlib import Path

# scripts/ is at the project root; the sweep runs pytest from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root

from scripts.core import seed_agent_images


@pytest.fixture
def seeded_store(tmp_path):
    """A fake project root: assets/agent-images + data/profile_images + db."""
    root = tmp_path / "proj"
    curated = root / "assets" / "agent-images"
    store = root / "data" / "profile_images"
    curated.mkdir(parents=True)
    store.mkdir(parents=True)
    # one curated image (Bob content)
    bob_content = b"bob-image-bytes"
    (curated / "Bob.png").write_bytes(bob_content)
    # a uuid copy of the same content (the duplication we kill)
    (store / "agent_19_b2e4371da26048ef92e02cf1384c95c3.png").write_bytes(bob_content)
    # a genuine upload (different content, must be left alone)
    (store / "agent_15_2731c91a44fc4b3e97074ec25fcb2dce.png").write_bytes(b"genuine-upload")
    return root


class TestCanonicalName:
    def test_lowercases_and_kebabs(self):
        assert seed_agent_images._canonical_name("Bob.png") == "bob.png"
        assert seed_agent_images._canonical_name("TheGreenQueen.png") == "thegreenqueen.png"
        assert seed_agent_images._canonical_name("alien-01.png") == "alien-01.png"


class TestPixelFallback:
    def test_reencoded_copy_is_recognized(self, tmp_path, monkeypatch):
        """A metadata-stripped PNG (same pixels, different bytes) must
        still be recognized as a curated copy via pixel fingerprint."""
        import sqlite3
        import struct
        import zlib

        def chunk(t: bytes, d: bytes) -> bytes:
            cc = t + d
            return struct.pack(">I", len(d)) + cc + struct.pack(">I", zlib.crc32(cc))

        ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
        pixels = b"\x00" + bytes([255, 0, 0]) * 4  # 1 filter byte + 4 RGB pixels
        idat = zlib.compress(pixels)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")

        root = tmp_path / "proj"
        curated = root / "assets" / "agent-images"
        store = root / "data" / "profile_images"
        curated.mkdir(parents=True)
        store.mkdir(parents=True)
        (curated / "red.png").write_bytes(png)  # canonical

        # re-encoded copy: same pixels, extra tEXt chunk (metadata) → different bytes
        meta = chunk(b"tEXt", b"Comment\x00stripped")
        reencoded = png[: len(png) - 12] + meta + png[len(png) - 12 :]  # inject before IEND
        uuid_copy = store / "agent_9_1234567890abcdef1234567890abcdef.png"
        uuid_copy.write_bytes(reencoded)

        monkeypatch.setattr(seed_agent_images, "PROJECT_ROOT", root)
        monkeypatch.setattr(seed_agent_images, "CURATED_DIR", curated)
        monkeypatch.setattr(seed_agent_images, "STORE_DIR", store)

        db = root / "cogitate.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE agents (id INTEGER PRIMARY KEY, profile_image_url TEXT)")
        conn.execute("INSERT INTO agents VALUES (9, '/static/agent_9_1234567890abcdef1234567890abcdef.png')")
        conn.commit()
        monkeypatch.setattr(seed_agent_images, "DB_PATH", db)

        # byte hashes differ (proves the test is meaningful)
        assert seed_agent_images._md5(png) != seed_agent_images._md5(reencoded)
        # pixel fingerprints match
        assert seed_agent_images._pixel_fingerprint(curated / "red.png") == seed_agent_images._pixel_fingerprint(uuid_copy)

        stats = seed_agent_images.seed()

        assert stats["remapped"] == 1
        url = conn.execute("SELECT profile_image_url FROM agents WHERE id=9").fetchone()[0]
        assert url == "/static/red.png"
        assert not uuid_copy.exists()  # orphan removed via pixel match
        conn.close()


class TestSeed:
    def test_copies_and_remaps(self, seeded_store, tmp_path, monkeypatch):
        root = seeded_store
        monkeypatch.setattr(seed_agent_images, "PROJECT_ROOT", root)
        monkeypatch.setattr(seed_agent_images, "CURATED_DIR", root / "assets" / "agent-images")
        monkeypatch.setattr(seed_agent_images, "STORE_DIR", root / "data" / "profile_images")

        import sqlite3
        db = root / "cogitate.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE agents (id INTEGER PRIMARY KEY, profile_image_url TEXT)")
        conn.execute("INSERT INTO agents VALUES (19, '/static/agent_19_b2e4371da26048ef92e02cf1384c95c3.png')")
        conn.execute("INSERT INTO agents VALUES (15, '/static/agent_15_2731c91a44fc4b3e97074ec25fcb2dce.png')")
        conn.commit()
        monkeypatch.setattr(seed_agent_images, "DB_PATH", db)

        stats = seed_agent_images.seed()

        # canonical copied
        assert (root / "data" / "profile_images" / "bob.png").exists()
        # agent 19 remapped to canonical
        url19 = conn.execute("SELECT profile_image_url FROM agents WHERE id=19").fetchone()[0]
        assert url19 == "/static/bob.png"
        # agent 15 untouched (genuine upload)
        url15 = conn.execute("SELECT profile_image_url FROM agents WHERE id=15").fetchone()[0]
        assert url15 == "/static/agent_15_2731c91a44fc4b3e97074ec25fcb2dce.png"
        # uuid copy removed (orphan), genuine upload kept
        store_files = {p.name for p in (root / "data" / "profile_images").iterdir()}
        assert "agent_19_b2e4371da26048ef92e02cf1384c95c3.png" not in store_files
        assert "agent_15_2731c91a44fc4b3e97074ec25fcb2dce.png" in store_files
        conn.close()

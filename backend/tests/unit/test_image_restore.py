"""Restore-curated — the additive recovery path for curated images."""

import io

import pytest
from fastapi import UploadFile

from app.api.v1 import images_router


def _tiny_png(red: int = 255) -> bytes:
    import struct, zlib

    def chunk(t: bytes, d: bytes) -> bytes:
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00" + bytes([red, 0, 0])))
        + chunk(b"IEND", b"")
    )


class TestRestoreCurated:
    """Point _curated_dir at a fake assets/agent-images/ and verify
    the copy semantics — additive-only, idempotent, uploads safe."""

    async def test_copies_missing_curated(self, tmp_path, monkeypatch):
        store = tmp_path / "store"
        store.mkdir()
        curated = tmp_path / "assets" / "agent-images"
        curated.mkdir(parents=True)
        (curated / "bob.png").write_bytes(_tiny_png(red=10))
        (curated / "kimi.png").write_bytes(_tiny_png(red=20))

        monkeypatch.setattr(images_router, "get_settings",
                            lambda: type("S", (), {"profile_images_dir": str(store)})())
        monkeypatch.setattr(
            images_router,
            "_curated_dir",
            lambda: curated,
        )

        result = await images_router.restore_curated_images()
        assert sorted(result["restored"]) == ["bob.png", "kimi.png"]
        assert result["skipped"] == 0
        assert (store / "bob.png").exists()
        assert (store / "kimi.png").exists()

    async def test_skips_existing_idempotent(self, tmp_path, monkeypatch):
        store = tmp_path / "store"
        store.mkdir()
        curated = tmp_path / "assets" / "agent-images"
        curated.mkdir(parents=True)
        (curated / "bob.png").write_bytes(_tiny_png(red=10))
        # store already has bob.png (maybe user-replaced)
        (store / "bob.png").write_bytes(b"user version")

        monkeypatch.setattr(images_router, "get_settings",
                            lambda: type("S", (), {"profile_images_dir": str(store)})())
        monkeypatch.setattr(images_router, "_curated_dir", lambda: curated)

        r1 = await images_router.restore_curated_images()
        assert r1["restored"] == []
        assert r1["skipped"] == 1
        # user version untouched
        assert (store / "bob.png").read_bytes() == b"user version"
        # idempotent second call
        r2 = await images_router.restore_curated_images()
        assert r2["restored"] == [] and r2["skipped"] == 1

    async def test_restores_deleted_after_delete_roundtrip(self, tmp_path, monkeypatch):
        store = tmp_path / "store"
        store.mkdir()
        curated = tmp_path / "assets" / "agent-images"
        curated.mkdir(parents=True)
        (curated / "bob.png").write_bytes(_tiny_png(red=10))

        monkeypatch.setattr(images_router, "get_settings",
                            lambda: type("S", (), {"profile_images_dir": str(store)})())
        monkeypatch.setattr(images_router, "_curated_dir", lambda: curated)
        # no agents reference the image (else delete 409s — in-use
        # protection, separate concern)
        monkeypatch.setattr(images_router, "_agent_usage", lambda: {})

        # delete it (user action — allowed)
        (store / "bob.png").write_bytes(_tiny_png(red=10))
        deleted = await images_router.delete_image("bob.png")
        assert deleted is None
        assert not (store / "bob.png").exists()

        # restore brings it back
        r = await images_router.restore_curated_images()
        assert r["restored"] == ["bob.png"]
        assert (store / "bob.png").exists()

    async def test_uploads_untouched(self, tmp_path, monkeypatch):
        store = tmp_path / "store"
        store.mkdir()
        curated = tmp_path / "assets" / "agent-images"
        curated.mkdir(parents=True)
        (curated / "bob.png").write_bytes(_tiny_png(red=10))
        # a user upload
        (store / "img_abc123.png").write_bytes(b"user upload")

        monkeypatch.setattr(images_router, "get_settings",
                            lambda: type("S", (), {"profile_images_dir": str(store)})())
        monkeypatch.setattr(images_router, "_curated_dir", lambda: curated)

        await images_router.restore_curated_images()
        assert (store / "img_abc123.png").read_bytes() == b"user upload"
        assert (store / "bob.png").exists()

    async def test_missing_curated_dir_raises(self, tmp_path, monkeypatch):
        store = tmp_path / "store"
        store.mkdir()
        monkeypatch.setattr(images_router, "get_settings",
                            lambda: type("S", (), {"profile_images_dir": str(store)})())
        monkeypatch.setattr(images_router, "_curated_dir", lambda: tmp_path / "nope")

        with pytest.raises(Exception) as ei:
            await images_router.restore_curated_images()
        assert ei.value.status_code == 404

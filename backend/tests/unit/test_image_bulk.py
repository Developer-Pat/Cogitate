"""Bulk image operations — upload-bulk + batch-delete."""

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


def _settings(tmp_path, max_size=10000):
    class S:
        profile_images_dir = str(tmp_path)
        max_upload_size = max_size
        allowed_image_types = ["image/png", "image/jpeg", "image/webp"]

    return S()


def _up(name: str, data: bytes, content_type: str = "image/png") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=name,
                      headers={"content-type": content_type})


class TestBulkUpload:
    async def test_uploads_multiple(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        files = [_up("a.png", _tiny_png(red=10)), _up("b.png", _tiny_png(red=20))]
        result = await images_router.upload_images_bulk(files)
        assert result["total_requested"] == 2
        assert result["total_added"] == 2
        assert result["total_errors"] == 0
        assert len(list(tmp_path.iterdir())) == 2

    async def test_mixed_valid_and_invalid(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        files = [
            _up("ok.png", _tiny_png()),
            _up("bad.txt", b"not an image", content_type="text/plain"),
        ]
        result = await images_router.upload_images_bulk(files)
        assert result["total_added"] == 1
        assert result["total_errors"] == 1
        assert result["errors"][0]["filename"] == "bad.txt"
        # the good one still landed
        assert len(list(tmp_path.iterdir())) == 1

    async def test_dedup_reuses_existing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        png = _tiny_png(red=99)
        files = [_up("one.png", png), _up("two.png", png)]
        result = await images_router.upload_images_bulk(files)
        assert result["total_added"] == 2
        assert len({f["filename"] for f in result["added"]}) == 1  # same pixels → same file
        assert len(list(tmp_path.iterdir())) == 1  # no duplicate written

    async def test_empty_list_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        with pytest.raises(Exception) as ei:
            await images_router.upload_images_bulk([])
        assert ei.value.status_code == 400


class TestBatchDelete:
    async def test_deletes_multiple(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        (tmp_path / "a.png").write_bytes(_tiny_png())
        (tmp_path / "b.png").write_bytes(_tiny_png(red=1))
        result = await images_router.batch_delete_images({"filenames": ["a.png", "b.png"]})
        assert result["total_deleted"] == 2
        assert result["total_failed"] == 0
        assert len(list(tmp_path.iterdir())) == 0

    async def test_in_use_reported_not_deleted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        (tmp_path / "used.png").write_bytes(_tiny_png())
        (tmp_path / "free.png").write_bytes(_tiny_png(red=2))
        # agent 7 references used.png
        monkeypatch.setattr(
            images_router,
            "_agent_usage",
            lambda: {"used.png": [7]},
        )
        result = await images_router.batch_delete_images({"filenames": ["used.png", "free.png"]})
        assert result["total_deleted"] == 1
        assert result["total_failed"] == 1
        assert result["failed"][0]["filename"] == "used.png"
        assert "in use" in result["failed"][0]["reason"]
        assert (tmp_path / "used.png").exists()  # protected
        assert not (tmp_path / "free.png").exists()  # deleted

    async def test_missing_reported(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        result = await images_router.batch_delete_images({"filenames": ["ghost.png"]})
        assert result["total_deleted"] == 0
        assert result["total_failed"] == 1
        assert result["failed"][0]["reason"] == "not found"

    async def test_path_traversal_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        result = await images_router.batch_delete_images({"filenames": ["../evil.png"]})
        assert result["total_deleted"] == 0
        assert result["total_failed"] == 1
        assert result["failed"][0]["reason"] == "invalid filename"

    async def test_empty_filenames_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        with pytest.raises(Exception) as ei:
            await images_router.batch_delete_images({"filenames": []})
        assert ei.value.status_code == 400

    async def test_missing_key_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(images_router, "get_settings", lambda: _settings(tmp_path))
        with pytest.raises(Exception) as ei:
            await images_router.batch_delete_images({})
        assert ei.value.status_code == 400

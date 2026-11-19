"""Image management API tests — the asset store (images-only scope)."""

import io
from zipfile import ZipFile

import pytest
from fastapi import HTTPException

from app.api.v1 import images_router


def _tiny_png() -> bytes:
    import struct, zlib

    def chunk(t: bytes, d: bytes) -> bytes:
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


class TestValidateImage:
    def test_rejects_bad_type(self):
        with pytest.raises(HTTPException) as ei:
            images_router._validate_image(b"x", "text/html")
        assert ei.value.status_code == 400

    def test_rejects_oversize(self, monkeypatch):
        class S:
            allowed_image_types = ["image/png"]
            max_upload_size = 10

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        with pytest.raises(HTTPException) as ei:
            images_router._validate_image(b"x" * 20, "image/png")
        assert ei.value.status_code == 400

    def test_accepts_valid(self, monkeypatch):
        class S:
            allowed_image_types = ["image/png"]
            max_upload_size = 1000

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        # no raise
        images_router._validate_image(b"x" * 5, "image/png")


class TestExportImport:
    async def test_export_import_roundtrip(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        # seed two files
        (tmp_path / "a.png").write_bytes(_tiny_png())
        (tmp_path / "b.jpg").write_bytes(b"jpegdata")

        # export
        resp = await images_router.export_images()
        chunks = [chunk async for chunk in resp.body_iterator]
        zip_bytes = b"".join(chunks)
        z = ZipFile(io.BytesIO(zip_bytes))
        names = set(z.namelist())
        assert names == {"a.png", "b.jpg"}

    async def test_import_adds_files(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)
            max_upload_size = 10000

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        buf = io.BytesIO()
        with ZipFile(buf, "w") as zf:
            zf.writestr("one.png", _tiny_png())
            zf.writestr("two.jpg", b"jpegdata")
            zf.writestr("notes.txt", "not an image")  # skipped
        buf.seek(0)

        from fastapi import UploadFile

        f = UploadFile(file=io.BytesIO(buf.getvalue()), filename="import.zip")
        result = await images_router.import_images(f)
        assert result["added_count"] == 2
        assert len(result["errors"]) == 0
        files = list(tmp_path.iterdir())
        assert len(files) == 2  # both images, no txt


class TestCuratedFilter:
    """GET /images?curated= filters before pagination."""

    async def test_filters_by_curated(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        monkeypatch.setattr(images_router, "_curated_names", lambda: {"bob.png"})
        (tmp_path / "bob.png").write_bytes(_tiny_png())
        (tmp_path / "img_user1.png").write_bytes(_tiny_png())
        (tmp_path / "img_user2.png").write_bytes(_tiny_png())

        all_resp = await images_router.list_images()
        assert all_resp["total"] == 3

        curated_resp = await images_router.list_images(curated="true")
        assert curated_resp["total"] == 1
        assert curated_resp["images"][0]["filename"] == "bob.png"

        uploads_resp = await images_router.list_images(curated="false")
        assert uploads_resp["total"] == 2
        names = {i["filename"] for i in uploads_resp["images"]}
        assert names == {"img_user1.png", "img_user2.png"}


class TestSorting:
    """GET /images sorting — default alphabetical, sortable columns."""

    async def test_default_alphabetical(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        monkeypatch.setattr(images_router, "_curated_names", lambda: set())
        (tmp_path / "zebra.png").write_bytes(_tiny_png())
        (tmp_path / "apple.png").write_bytes(_tiny_png())
        (tmp_path / "mango.png").write_bytes(_tiny_png())

        resp = await images_router.list_images()
        names = [i["filename"] for i in resp["images"]]
        assert names == ["apple.png", "mango.png", "zebra.png"]

    async def test_size_sort(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        monkeypatch.setattr(images_router, "_curated_names", lambda: set())
        (tmp_path / "small.png").write_bytes(b"x")
        (tmp_path / "big.png").write_bytes(b"x" * 100)
        (tmp_path / "mid.png").write_bytes(b"x" * 10)

        resp = await images_router.list_images(sort_by="size", sort_dir="asc")
        assert [i["filename"] for i in resp["images"]] == ["small.png", "mid.png", "big.png"]
        resp = await images_router.list_images(sort_by="size", sort_dir="desc")
        assert [i["filename"] for i in resp["images"]] == ["big.png", "mid.png", "small.png"]

    async def test_invalid_sort_falls_back(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        monkeypatch.setattr(images_router, "_curated_names", lambda: set())
        (tmp_path / "b.png").write_bytes(_tiny_png())
        (tmp_path / "a.png").write_bytes(_tiny_png())

        resp = await images_router.list_images(sort_by="nonsense")
        names = [i["filename"] for i in resp["images"]]
        assert names == ["a.png", "b.png"]  # fell back to filename asc


class TestImportPreservesNames:
    """Import/export is a round-trip of the store — filenames MUST
    be preserved (agent URLs reference canonical names). Regression:
    2026-08-11 — import renamed everything to img_<uuid>, breaking
    restore + agent references (user caught it live)."""

    async def test_import_keeps_original_filenames(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)
            max_upload_size = 100000

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        buf = io.BytesIO()
        with ZipFile(buf, "w") as zf:
            zf.writestr("blondie.png", _tiny_png())
            # different pixels — a re-encoded/sized variant
            zf.writestr("bob.png", b"\x89PNG\r\n\x1a\n" + b"x" * 40)
        buf.seek(0)

        from fastapi import UploadFile

        f = UploadFile(file=io.BytesIO(buf.getvalue()), filename="store.zip")
        result = await images_router.import_images(f)
        assert result["added_count"] == 2
        # canonical names preserved — NOT renamed to img_<uuid>
        assert (tmp_path / "blondie.png").exists()
        assert (tmp_path / "bob.png").exists()
        assert not list(tmp_path.glob("img_*"))

    async def test_import_idempotent_no_duplicates(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)
            max_upload_size = 100000

        monkeypatch.setattr(images_router, "get_settings", lambda: S())
        buf = io.BytesIO()
        with ZipFile(buf, "w") as zf:
            zf.writestr("blondie.png", _tiny_png())
        buf.seek(0)

        from fastapi import UploadFile

        f1 = UploadFile(file=io.BytesIO(buf.getvalue()), filename="store.zip")
        r1 = await images_router.import_images(f1)
        assert r1["added_count"] == 1
        f2 = UploadFile(file=io.BytesIO(buf.getvalue()), filename="store.zip")
        r2 = await images_router.import_images(f2)
        assert r2["added_count"] == 1
        # still exactly one file — dedup reuses, no img_<uuid> copies
        assert len(list(tmp_path.iterdir())) == 1
        assert (tmp_path / "blondie.png").exists()

"""Metadata stripping — EXIF/ComfyUI workflow removal from PNGs."""

import struct
import zlib

from app.domain.assets import pixel_fingerprint, strip_metadata


def make_png(red: int = 255, with_meta: bool = True) -> bytes:
    """1x1 PNG; optionally embeds a tEXt chunk (ComfyUI-style)."""
    def chunk(t: bytes, d: bytes) -> bytes:
        cc = t + d
        return struct.pack(">I", len(d)) + cc + struct.pack(">I", zlib.crc32(cc))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" + bytes([red, 0, 0]))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    if with_meta:
        # ComfyUI embeds its workflow as a tEXt chunk
        png += chunk(b"tEXt", b"prompt\x00{\"workflow\": \"comfy\"}")
    png += chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    return png


def chunks_of(data: bytes) -> list[bytes]:
    out = []
    i = 8
    while i < len(data):
        ln = int.from_bytes(data[i : i + 4], "big")
        out.append(data[i + 4 : i + 8])
        i += 12 + ln
    return out


class TestStripMetadata:
    def test_strips_text_chunks(self):
        data = make_png(with_meta=True)
        cleaned, stripped = strip_metadata(data)
        assert stripped is True
        assert b"tEXt" not in chunks_of(cleaned)
        assert b"prompt" not in cleaned

    def test_keeps_pixels_identical(self):
        data = make_png(red=200, with_meta=True)
        cleaned, _ = strip_metadata(data)
        assert pixel_fingerprint(data) == pixel_fingerprint(cleaned)

    def test_no_metadata_returns_original_untouched(self):
        data = make_png(with_meta=False)
        cleaned, stripped = strip_metadata(data)
        assert stripped is False
        assert cleaned == data  # byte-identical — dedup unaffected

    def test_keeps_color_chunks(self):
        data = make_png(with_meta=True)
        # inject a gAMA chunk to simulate color data
        def chunk(t: bytes, d: bytes) -> bytes:
            cc = t + d
            return struct.pack(">I", len(d)) + cc + struct.pack(">I", zlib.crc32(cc))
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b"\x00\xff\x00\x00")
        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"gAMA", struct.pack(">I", 45455))
            + chunk(b"tEXt", b"Comment\x00x")
            + chunk(b"IDAT", idat)
            + chunk(b"IEND", b"")
        )
        cleaned, stripped = strip_metadata(png)
        assert stripped is True
        cs = chunks_of(cleaned)
        assert b"gAMA" in cs  # color chunk kept
        assert b"tEXt" not in cs  # metadata dropped

    def test_non_png_passthrough(self):
        data = b"not a png"
        cleaned, stripped = strip_metadata(data)
        assert stripped is False
        assert cleaned == data

    def test_malformed_png_passthrough(self):
        # truncated: declares a 100-byte chunk but the file ends
        data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 100) + b"IHDR" + b"short"
        cleaned, stripped = strip_metadata(data)
        assert stripped is False
        assert cleaned == data


class TestUploadStripParam:
    """upload-bulk with strip=true removes metadata; reports nothing
    misleading — the response surfaces the choice."""

    async def test_strip_true_removes_metadata(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)
            max_upload_size = 100000
            allowed_image_types = ["image/png", "image/jpeg", "image/webp"]

        monkeypatch.setattr("app.api.v1.images_router.get_settings", lambda: S())

        from fastapi import UploadFile
        import io

        f = UploadFile(
            file=io.BytesIO(make_png(red=50, with_meta=True)),
            filename="comfy.png",
            headers={"content-type": "image/png"},
        )
        result = await __import__("app.api.v1.images_router", fromlist=["upload_images_bulk"]).upload_images_bulk([f], strip=True)
        assert result["total_added"] == 1
        saved = list(tmp_path.iterdir())[0]
        assert b"prompt" not in saved.read_bytes()  # ComfyUI workflow gone
        assert b"tEXt" not in saved.read_bytes()

    async def test_strip_false_keeps_metadata(self, tmp_path, monkeypatch):
        class S:
            profile_images_dir = str(tmp_path)
            max_upload_size = 100000
            allowed_image_types = ["image/png", "image/jpeg", "image/webp"]

        monkeypatch.setattr("app.api.v1.images_router.get_settings", lambda: S())

        from fastapi import UploadFile
        import io

        f = UploadFile(
            file=io.BytesIO(make_png(red=60, with_meta=True)),
            filename="keep.png",
            headers={"content-type": "image/png"},
        )
        result = await __import__("app.api.v1.images_router", fromlist=["upload_images_bulk"]).upload_images_bulk([f], strip=False)
        assert result["total_added"] == 1
        saved = list(tmp_path.iterdir())[0]
        assert b"prompt" in saved.read_bytes()  # kept as-is — no surprises

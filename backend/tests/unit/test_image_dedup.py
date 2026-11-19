"""Image upload dedup — pixel-fingerprint reuses existing files."""

import struct
import zlib
from pathlib import Path

import pytest

from app.domain.assets import dedup_upload, find_existing_by_fingerprint, pixel_fingerprint


def make_png(red: int = 255) -> bytes:
    """Tiny 2x2 PNG with a solid color; metadata can be injected."""
    def chunk(t: bytes, d: bytes) -> bytes:
        cc = t + d
        return struct.pack(">I", len(d)) + cc + struct.pack(">I", zlib.crc32(cc))

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    pixels = b"\x00" + bytes([red, 0, 0]) * 4
    idat = zlib.compress(pixels)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def add_metadata(png: bytes) -> bytes:
    """Inject a tEXt chunk before IEND — same pixels, different bytes."""
    meta = struct.pack(">I", 12) + b"tEXtComment\x00meta" + struct.pack(">I", zlib.crc32(b"tEXtComment\x00meta"))
    return png[: len(png) - 12] + meta + png[len(png) - 12 :]


class TestPixelFingerprint:
    def test_identical_pixels_differing_bytes(self):
        a = make_png(red=200)
        b = add_metadata(a)
        assert a != b  # bytes differ
        assert pixel_fingerprint(a) == pixel_fingerprint(b)  # pixels match

    def test_different_image_different_fingerprint(self):
        assert pixel_fingerprint(make_png(red=10)) != pixel_fingerprint(make_png(red=200))

    def test_non_png_returns_none(self):
        assert pixel_fingerprint(b"not a png") is None


class TestDedupUpload:
    def test_first_upload_creates_file(self, tmp_path):
        name, created = dedup_upload(tmp_path, make_png(), name_for_new="one.png")
        assert created is True
        assert name == "one.png"
        assert (tmp_path / "one.png").exists()

    def test_reupload_reuses_existing(self, tmp_path):
        a = make_png(red=150)
        name1, created1 = dedup_upload(tmp_path, a, name_for_new="one.png")
        # same image, different name attempt
        name2, created2 = dedup_upload(tmp_path, a, name_for_new="two.png")
        assert created1 is True
        assert created2 is False
        assert name2 == name1 == "one.png"  # reused, not a new copy
        assert len(list(tmp_path.iterdir())) == 1  # no duplicate file

    def test_metadata_stripped_copy_reused(self, tmp_path):
        a = make_png(red=80)
        b = add_metadata(a)  # byte-different, pixel-identical
        name1, _ = dedup_upload(tmp_path, a, name_for_new="one.png")
        name2, created2 = dedup_upload(tmp_path, b, name_for_new="two.png")
        assert created2 is False
        assert name2 == name1

    def test_different_image_creates_new(self, tmp_path):
        dedup_upload(tmp_path, make_png(red=10), name_for_new="red.png")
        name2, created2 = dedup_upload(tmp_path, make_png(red=200), name_for_new="blue.png")
        assert created2 is True
        assert name2 == "blue.png"
        assert len(list(tmp_path.iterdir())) == 2


class TestFindExisting:
    def test_finds_match_among_files(self, tmp_path):
        (tmp_path / "bob.png").write_bytes(make_png(red=120))
        assert find_existing_by_fingerprint(tmp_path, make_png(red=120)) == "bob.png"

    def test_no_match_returns_none(self, tmp_path):
        (tmp_path / "bob.png").write_bytes(make_png(red=120))
        assert find_existing_by_fingerprint(tmp_path, make_png(red=200)) is None

    def test_empty_dir_returns_none(self, tmp_path):
        assert find_existing_by_fingerprint(tmp_path, make_png()) is None

"""
Image store helpers — pixel-fingerprint dedup for uploads.

The image store is data/profile_images/. Uploads create uuid-named
files; re-uploading the same image (or a metadata-stripped copy)
used to create ANOTHER uuid copy — the duplication we killed in
the curated set. Both upload paths (agent profile image + image
store) route through here: fingerprint the incoming bytes, look for
an existing file with the same PIXELS, and reuse it instead of
saving a duplicate.

Byte hashes miss re-encoded copies (identical pixels, different
file bytes — e.g. metadata stripped). Compare the decompressed
pixels instead.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def pixel_fingerprint(data: bytes) -> str | None:
    """MD5 of a PNG's raw pixels (dims + decompressed IDAT).

    Returns None for non-PNG or unreadable data — those fall back
    to byte-identity dedup only.
    """
    try:
        if data[:8] != _PNG_SIG:
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
        import hashlib

        return hashlib.md5(struct.pack(">IIBB", w, h, bit_depth, color_type) + raw).hexdigest()
    except Exception:
        return None


def find_existing_by_fingerprint(store_dir: Path, data: bytes) -> str | None:
    """Return the filename of an existing store file with the same
    pixels as `data`, or None. Skips non-image files.

    Args:
        store_dir: data/profile_images/
        data: incoming upload bytes

    Returns:
        Existing filename (e.g. "img_abc123.png") or None.
    """
    fp = pixel_fingerprint(data)
    if fp is None:
        return None
    if not store_dir.exists():
        return None
    for p in store_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in _IMAGE_EXTS:
            continue
        try:
            if pixel_fingerprint(p.read_bytes()) == fp:
                return p.name
        except Exception:
            continue
    return None


def dedup_upload(
    store_dir: Path,
    data: bytes,
    *,
    name_for_new: str,
) -> tuple[str, bool]:
    """Save an upload, deduplicated by pixels.

    Args:
        store_dir: data/profile_images/
        data: incoming upload bytes
        name_for_new: filename to use if no existing match
            (caller generates uuid names)

    Returns:
        (filename, saved_new) — the filename in the store (existing
        or newly written), and whether this call wrote a new file.
    """
    store_dir.mkdir(parents=True, exist_ok=True)
    existing = find_existing_by_fingerprint(store_dir, data)
    if existing:
        return existing, False
    (store_dir / name_for_new).write_bytes(data)
    return name_for_new, True


# Chunks that define color/rendering — kept when stripping.
# Everything else (tEXt/zTXt/iTXt/eXIf/tIME/unknown) is dropped:
# tEXt/zTXt/iTXt carry EXIF, GPS, and tool metadata (ComfyUI embeds
# its generation workflow there); they also bloat the file and can
# leak prompt/graph details. Keeping the color chunks means pixels
# and colors are untouched — only metadata is removed.
_KEEP_CHUNKS = {
    b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM",
    b"sRGB", b"iCCP", b"pHYs", b"bKGD", b"sBIT",
}


def strip_metadata(data: bytes) -> tuple[bytes, bool]:
    """Strip non-color metadata chunks from a PNG.

    Returns (bytes, stripped): the cleaned PNG (unchanged if there
    was nothing to strip — byte-identity preserved so dedup still
    matches), and whether anything was removed.

    Non-PNG input returns (data, False) untouched — the caller
    decides how to handle other formats (currently they pass
    through; JPEG/WebP stripping needs Pillow, tracked as a gap).
    """
    if data[:8] != _PNG_SIG:
        return data, False

    out = bytearray(data[:8])
    stripped = False
    i = 8
    try:
        while i < len(data):
            ln = int.from_bytes(data[i : i + 4], "big")
            typ = data[i + 4 : i + 8]
            if len(typ) < 4 or i + 12 + ln > len(data):
                # truncated/declared-beyond-buffer chunk — malformed
                # PNG; don't destroy it, pass through untouched
                return data, False
            chunk = data[i : i + 12 + ln]
            if typ in _KEEP_CHUNKS:
                out += chunk
            else:
                stripped = True
            i += 12 + ln
    except Exception:
        # malformed PNG — don't destroy it, pass through
        return data, False

    if not stripped:
        return data, False
    return bytes(out), True

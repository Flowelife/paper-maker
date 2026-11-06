"""Read intrinsic image size and resolution without third-party packages."""

from __future__ import annotations

import struct
from pathlib import Path

DEFAULT_DPI = 96.0


def _png_size(data: bytes) -> tuple[int, int, float]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG 文件")
    width, height = struct.unpack(">II", data[16:24])
    dpi = DEFAULT_DPI
    offset = 8
    while offset + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[offset:offset + 8])
        if ctype == b"pHYs" and length >= 9:
            ppu_x, ppu_y, unit = struct.unpack(">IIB", data[offset + 8:offset + 17])
            if unit == 1 and ppu_x:
                dpi = ppu_x * 0.0254
            break
        if ctype in (b"IDAT", b"IEND"):
            break
        offset += 12 + length
    return width, height, dpi


def _jpeg_size(data: bytes) -> tuple[int, int, float]:
    if data[:2] != b"\xff\xd8":
        raise ValueError("不是 JPEG 文件")
    dpi = DEFAULT_DPI
    offset = 2
    width = height = 0
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
        segment = data[offset + 4:offset + 2 + length]
        if marker == 0xE0 and segment[:5] == b"JFIF\x00" and len(segment) >= 12:
            units = segment[7]
            xdensity = struct.unpack(">H", segment[8:10])[0]
            if xdensity:
                if units == 1:
                    dpi = float(xdensity)
                elif units == 2:
                    dpi = xdensity * 2.54
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", segment[1:5])
            break
        offset += 2 + length
    if not width or not height:
        raise ValueError("JPEG 尺寸解析失败")
    return width, height, dpi


def _gif_size(data: bytes) -> tuple[int, int, float]:
    width, height = struct.unpack("<HH", data[6:10])
    return width, height, DEFAULT_DPI


def _bmp_size(data: bytes) -> tuple[int, int, float]:
    width, height = struct.unpack("<ii", data[18:26])
    return abs(width), abs(height), DEFAULT_DPI


def read_image_size(path: str | Path) -> tuple[int, int, float]:
    """Return ``(pixel_width, pixel_height, dpi)``."""
    path = Path(path)
    data = path.read_bytes()
    head = data[:16]
    if head.startswith(b"\x89PNG"):
        return _png_size(data)
    if head.startswith(b"\xff\xd8"):
        return _jpeg_size(data)
    if head.startswith(b"GIF8"):
        return _gif_size(data)
    if head.startswith(b"BM"):
        return _bmp_size(data)
    raise ValueError(f"不支持的图片格式: {path.suffix or '未知'}（支持 PNG/JPEG/GIF/BMP）")


def image_extent_cm(path: str | Path) -> tuple[float, float]:
    """Intrinsic size of an image in centimetres."""
    width, height, dpi = read_image_size(path)
    dpi = dpi if dpi and dpi > 0 else DEFAULT_DPI
    return width / dpi * 2.54, height / dpi * 2.54

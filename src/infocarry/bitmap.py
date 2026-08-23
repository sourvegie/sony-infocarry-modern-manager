"""Small, dependency-free decoders for the InfoCarry monochrome BMP records."""

from __future__ import annotations

from dataclasses import dataclass


MAX_BITMAP_PIXELS = 16_000_000


class BitmapFormatError(ValueError):
    """Raised when a preserved BMP payload is not safely displayable."""


@dataclass(frozen=True)
class BitmapPreview:
    """A bounded decoded image with offline and Tk-friendly representations."""

    width: int
    height: int
    ppm: bytes
    photo_rows: tuple[str, ...]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _i32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def decode_monochrome_bmp(payload: bytes) -> BitmapPreview:
    """Decode an uncompressed 1-bit Windows BMP into an RGB PPM image.

    The legacy records observed in complete backups use a 40-byte
    ``BITMAPINFOHEADER``, a two-entry BGRA palette, and four-byte-aligned
    scanlines.  The decoder accepts both bottom-up and top-down images and
    deliberately rejects other formats rather than guessing at their pixels.
    """

    if len(payload) < 62 or payload[:2] != b"BM":
        raise BitmapFormatError("BMP payload is too short or has no BM signature")
    declared_length = _u32(payload, 2)
    if declared_length != len(payload):
        raise BitmapFormatError(
            f"BMP declares {declared_length} bytes; payload contains {len(payload)}"
        )
    pixel_offset = _u32(payload, 10)
    dib_size = _u32(payload, 14)
    if dib_size < 40 or 14 + dib_size > len(payload):
        raise BitmapFormatError(f"unsupported BMP DIB header size {dib_size}")
    width = _i32(payload, 18)
    signed_height = _i32(payload, 22)
    planes = _u16(payload, 26)
    bits_per_pixel = _u16(payload, 28)
    compression = _u32(payload, 30)
    if width <= 0 or signed_height == 0:
        raise BitmapFormatError("BMP dimensions must be positive and non-zero")
    height = abs(signed_height)
    if width * height > MAX_BITMAP_PIXELS:
        raise BitmapFormatError("BMP is too large to display safely")
    if planes != 1 or bits_per_pixel != 1 or compression != 0:
        raise BitmapFormatError(
            "only uncompressed 1-bit BMP images are supported for preview"
        )

    colors_used = _u32(payload, 46)
    palette_entries = colors_used or 2
    if palette_entries < 2:
        raise BitmapFormatError("1-bit BMP must contain a two-entry palette")
    palette_start = 14 + dib_size
    palette_end = palette_start + palette_entries * 4
    if palette_end > len(payload) or pixel_offset < palette_end:
        raise BitmapFormatError("BMP palette or pixel offset is outside the payload")
    palette = []
    for index in range(2):
        entry = payload[palette_start + index * 4 : palette_start + index * 4 + 4]
        # BMP palette entries are blue, green, red, reserved.
        palette.append((entry[2], entry[1], entry[0]))

    row_stride = ((width + 31) // 32) * 4
    pixel_end = pixel_offset + row_stride * height
    if pixel_end > len(payload):
        raise BitmapFormatError("BMP scanlines exceed the payload")

    # Keep an ASCII P3 form for portable offline diagnostics.  The desktop
    # view uses ``photo_rows`` below rather than asking Tk to parse PPM data.
    ppm_rows = []
    photo_rows = []
    for output_y in range(height):
        source_y = height - 1 - output_y if signed_height > 0 else output_y
        row_start = pixel_offset + source_y * row_stride
        ppm_colors = []
        photo_colors = []
        for x in range(width):
            byte = payload[row_start + x // 8]
            palette_index = (byte >> (7 - (x % 8))) & 1
            red, green, blue = palette[palette_index]
            ppm_colors.append(f"{red} {green} {blue}")
            photo_colors.append(f"#{red:02x}{green:02x}{blue:02x}")
        ppm_rows.append(" ".join(ppm_colors))
        # ``PhotoImage.put`` expects a Tcl row list.  Constructing the image
        # this way avoids Tk's platform-dependent PPM data parser entirely.
        photo_rows.append("{" + " ".join(photo_colors) + "}")

    ppm = f"P3\n{width} {height}\n255\n" + "\n".join(ppm_rows) + "\n"
    return BitmapPreview(
        width=width,
        height=height,
        ppm=ppm.encode("ascii"),
        photo_rows=tuple(photo_rows),
    )


__all__ = ["BitmapFormatError", "BitmapPreview", "MAX_BITMAP_PIXELS", "decode_monochrome_bmp"]

"""Dependency-free offline authoring and page-layout primitives.

This module is deliberately separate from the USB and backup layers.  It
provides the first canonical integration boundary for the existing conversion
project without importing that project's duplicate ``infocarry`` package or
adding a raster/font dependency.  Text conversion is strict CP932/CRLF and
page layout is deterministic code-point wrapping; glyph rasterization and
EPUB/MOBI parsing remain later, separately gated work.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
from typing import Sequence

from .text_authoring import EncodedText, TextAuthoringError, encode_cp932_text


class OfflineConversionError(ValueError):
    """Raised when an offline conversion input or output is unsafe."""


@dataclass(frozen=True)
class PageLayout:
    """Logical page settings for the current 240 x 320 device profile.

    ``columns`` and ``lines_per_page`` are layout units, not a claim about a
    particular font's pixel metrics.  The defaults match the conservative
    6x16-cell planning profile (40 columns by 20 lines) used for previews.
    """

    width_px: int = 240
    height_px: int = 320
    columns: int = 40
    lines_per_page: int = 20

    def __post_init__(self) -> None:
        if (self.width_px, self.height_px) != (240, 320):
            raise OfflineConversionError("only the verified 240 x 320 profile is supported")
        if not 1 <= self.columns <= self.width_px:
            raise OfflineConversionError("page columns must be between 1 and 240")
        if not 1 <= self.lines_per_page <= self.height_px:
            raise OfflineConversionError("page line count must be between 1 and 320")


DEFAULT_PAGE_LAYOUT = PageLayout()


@dataclass(frozen=True)
class TextPage:
    """One deterministic logical page."""

    number: int
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class OfflineTextDocument:
    """Strictly authored text plus a deterministic logical page plan."""

    source_path: Path
    source_sha256: str
    original_text: str
    authored: EncodedText
    pages: tuple[TextPage, ...]
    layout: PageLayout

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def report(self) -> dict[str, object]:
        return {
            "format": "infocarry-offline-text-document-v1",
            "source_path": str(self.source_path),
            "source_sha256": self.source_sha256,
            "encoding": "cp932",
            "newline_policy": "crlf",
            "source_characters": len(self.original_text),
            "source_utf8_bytes": len(self.original_text.encode("utf-8")),
            "normalized_characters": len(self.authored.normalized_text),
            "encoded_payload_bytes": len(self.authored.payload),
            "encoded_payload_sha256": hashlib.sha256(self.authored.payload).hexdigest(),
            "page_count": self.page_count,
            "page_layout": {
                "width_px": self.layout.width_px,
                "height_px": self.layout.height_px,
                "columns": self.layout.columns,
                "lines_per_page": self.layout.lines_per_page,
            },
            "device_accessed": False,
            "candidate_bytes_included": False,
        }


def paginate_text(
    text: str,
    layout: PageLayout = DEFAULT_PAGE_LAYOUT,
) -> tuple[TextPage, ...]:
    """Wrap text deterministically into logical pages.

    Wrapping is intentionally code-point based.  It preserves explicit blank
    lines and never invents a line break based on an unverified font metric.
    """

    if not isinstance(text, str):
        raise OfflineConversionError("text must be a Unicode string")
    logical_lines: list[str] = []
    for physical in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not physical:
            logical_lines.append("")
            continue
        logical_lines.extend(
            physical[start : start + layout.columns]
            for start in range(0, len(physical), layout.columns)
        )
    if not logical_lines:
        logical_lines = [""]
    pages = tuple(
        TextPage(number=index + 1, lines=tuple(logical_lines[start : start + layout.lines_per_page]))
        for index, start in enumerate(range(0, len(logical_lines), layout.lines_per_page))
    )
    return pages


def load_utf8_text_document(
    source: Path,
    *,
    layout: PageLayout = DEFAULT_PAGE_LAYOUT,
) -> OfflineTextDocument:
    """Read one UTF-8 source and author it without USB or output writes."""

    path = Path(source).expanduser().resolve()
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise OfflineConversionError(f"could not read strict UTF-8 text {path}: {exc}") from exc
    try:
        authored = encode_cp932_text(text)
    except TextAuthoringError as exc:
        raise OfflineConversionError(str(exc)) from exc
    return OfflineTextDocument(
        source_path=path,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        original_text=text,
        authored=authored,
        pages=paginate_text(text, layout),
        layout=layout,
    )


def export_text_document(document: OfflineTextDocument, destination: Path) -> Path:
    """Write a new, self-contained offline conversion package.

    The destination must not already exist.  The package contains native
    CP932 text, a UTF-8 archival copy, logical page text files, and a manifest;
    it never contains candidate device bytes or performs USB I/O.
    """

    if not isinstance(document, OfflineTextDocument):
        raise OfflineConversionError("document must be an OfflineTextDocument")
    root = Path(destination).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
        (root / "pages").mkdir()
        (root / "text_cp932.txt").write_bytes(document.authored.payload)
        (root / "text_utf8.txt").write_text(document.original_text, encoding="utf-8", newline="")
        for page in document.pages:
            (root / "pages" / f"page-{page.number:04d}.txt").write_text(
                page.text + "\n", encoding="utf-8", newline=""
            )
        (root / "manifest.json").write_text(
            json.dumps(document.report(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="",
        )
    except FileExistsError as exc:
        raise OfflineConversionError(f"refusing to overwrite existing output {root}") from exc
    except OSError as exc:
        raise OfflineConversionError(f"could not create offline conversion package {root}: {exc}") from exc
    return root


def monochrome_bmp_bytes(
    pixels: Sequence[Sequence[bool]],
    *,
    width: int = 240,
    height: int = 320,
) -> bytes:
    """Serialize a validated black/white pixel matrix as a Windows BMP.

    ``True`` means black and ``False`` means white.  This is a renderer
    boundary, not a font renderer: callers must supply pixels from a future
    verified glyph engine.  The output is always uncompressed, bottom-up,
    1-bit, and uses the established 240 x 320 profile by default.
    """

    if width <= 0 or height <= 0:
        raise OfflineConversionError("BMP dimensions must be positive")
    if len(pixels) != height or any(len(row) != width for row in pixels):
        raise OfflineConversionError(f"pixel matrix must be exactly {width} x {height}")
    row_stride = ((width + 31) // 32) * 4
    pixel_bytes = bytearray(row_stride * height)
    for output_y, row in enumerate(reversed(pixels)):
        row_start = output_y * row_stride
        for x, black in enumerate(row):
            if not black:
                pixel_bytes[row_start + x // 8] |= 0x80 >> (x % 8)
    pixel_offset = 14 + 40 + 8
    file_size = pixel_offset + len(pixel_bytes)
    header = bytearray()
    header.extend(b"BM")
    header.extend(struct.pack("<IHHI", file_size, 0, 0, pixel_offset))
    header.extend(struct.pack("<IiiHHIIiiII", 40, width, height, 1, 1, 0, len(pixel_bytes), 3780, 3780, 0, 0))
    header.extend(bytes((0, 0, 0, 0, 255, 255, 255, 0)))
    return bytes(header) + bytes(pixel_bytes)


__all__ = [
    "DEFAULT_PAGE_LAYOUT",
    "OfflineConversionError",
    "OfflineTextDocument",
    "PageLayout",
    "TextPage",
    "export_text_document",
    "load_utf8_text_document",
    "monochrome_bmp_bytes",
    "paginate_text",
]

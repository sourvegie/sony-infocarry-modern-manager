"""Bounded, device-neutral EPUB inspection and preparation.

This module is an internal adapter for :mod:`infocarry.content_workspace`.
It reads only local ZIP/OCF resources, applies the existing CP932/CRLF text
authoring policy, and produces the canonical prepared-content artifact.  It
does not construct a device candidate, authorize an operation, or import USB
or sender code.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any, Callable, Mapping, Optional
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ElementTree
import zipfile

from .prepared_content import PreparedContentArtifact, PreparedContentChild, PreparedContentError
from .prepared_media_package import PreparedMediaPackageError, validate_bmp_payload
from .text_authoring import TextAuthoringError, encode_cp932_text, normalization_occurrences
from .transfer_shape import TransferShapeAssessment, assess_transfer_shape


CONTENT_WORKSPACE_FORMAT = "infocarry-content-workspace-v1"
PREPARED_EPUB_PROFILE_ID = "prepared-epub-content-v1"
SUPPORTED_EPUB_MEDIA_TYPES = frozenset({"application/xhtml+xml", "text/html"})
SUPPORTED_EPUB_IMAGE_MEDIA_TYPES = frozenset({"image/bmp", "image/x-ms-bmp"})

EPUB_MAX_SOURCE_BYTES = 64 * 1024 * 1024
EPUB_MAX_ARCHIVE_ENTRIES = 512
EPUB_MAX_ENTRY_UNCOMPRESSED_BYTES = 8 * 1024 * 1024
EPUB_MAX_TOTAL_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
EPUB_MAX_COMPRESSION_RATIO = 1000
EPUB_MAX_TITLE_CHARACTERS = 1024
EPUB_MAX_CHAPTERS = 256
EPUB_MAX_TEXT_CHARACTERS = 4_000_000
EPUB_MAX_IMAGE_CHILDREN = 256


class EpubSecurityError(ValueError):
    """Raised when an EPUB violates the bounded untrusted-input policy."""


class EpubPackageError(ValueError):
    """Raised when an EPUB container or package document is malformed."""


@dataclass(frozen=True)
class EpubLimits:
    max_source_bytes: int = EPUB_MAX_SOURCE_BYTES
    max_archive_entries: int = EPUB_MAX_ARCHIVE_ENTRIES
    max_entry_uncompressed_bytes: int = EPUB_MAX_ENTRY_UNCOMPRESSED_BYTES
    max_total_uncompressed_bytes: int = EPUB_MAX_TOTAL_UNCOMPRESSED_BYTES
    max_compression_ratio: int = EPUB_MAX_COMPRESSION_RATIO
    max_title_characters: int = EPUB_MAX_TITLE_CHARACTERS
    max_chapters: int = EPUB_MAX_CHAPTERS
    max_text_characters: int = EPUB_MAX_TEXT_CHARACTERS
    max_image_children: int = EPUB_MAX_IMAGE_CHILDREN

    def __post_init__(self) -> None:
        for name in (
            "max_source_bytes",
            "max_archive_entries",
            "max_entry_uncompressed_bytes",
            "max_total_uncompressed_bytes",
            "max_compression_ratio",
            "max_title_characters",
            "max_chapters",
            "max_text_characters",
            "max_image_children",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


DEFAULT_EPUB_LIMITS = EpubLimits()


@dataclass(frozen=True)
class PreparedContentPayload:
    name: str
    kind: str
    payload: bytes
    source_sha256: str
    source_bytes: int
    source_reference: str
    normalized: bool = False
    normalization_occurrences: tuple[tuple[int, int, str, str], ...] = ()

    @property
    def payload_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class EpubInspection:
    source_path: Path
    source_sha256: str
    title: str
    opf_path: str
    spine_paths: tuple[str, ...]
    unsupported_features: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "source_sha256": self.source_sha256,
            "title": self.title,
            "opf_path": self.opf_path,
            "spine_paths": list(self.spine_paths),
            "unsupported_features": [dict(feature) for feature in self.unsupported_features],
        }


@dataclass(frozen=True)
class PreparedContentResult:
    source_path: Path
    source_sha256: str
    source_format: str
    title: str
    artifact: PreparedContentArtifact
    payloads: tuple[PreparedContentPayload, ...]
    unsupported_features: tuple[Mapping[str, Any], ...]
    normalized_text_children: int
    normalization_events: int
    transfer_shape: TransferShapeAssessment

    def __post_init__(self) -> None:
        if len(self.payloads) != len(self.artifact.children):
            raise ValueError("prepared payloads do not match canonical children")
        for payload, child in zip(self.payloads, self.artifact.children):
            if payload.name != child.name or payload.kind != child.kind:
                raise ValueError("prepared payload order differs from canonical children")
            if payload.payload_sha256 != child.payload_sha256:
                raise ValueError("prepared payload hash differs from canonical content")
        if self.transfer_shape.artifact_identity != self.artifact.artifact_identity:
            raise ValueError("transfer-shape assessment is not bound to the artifact")

    @property
    def normalization_occurred(self) -> bool:
        return self.normalization_events > 0

    @property
    def user_notice(self) -> Optional[str]:
        return "Some characters were adjusted for InfoCarry compatibility." if self.normalization_occurred else None

    def preview_children(self, *, max_text_characters: int = 1200) -> tuple[dict[str, Any], ...]:
        if isinstance(max_text_characters, bool) or not isinstance(max_text_characters, int) or max_text_characters <= 0:
            raise ValueError("max_text_characters must be a positive integer")
        previews: list[dict[str, Any]] = []
        for payload in self.payloads:
            value: dict[str, Any] = {
                "name": payload.name,
                "kind": payload.kind,
                "prepared_bytes": len(payload.payload),
            }
            if payload.kind == "txt":
                try:
                    text = payload.payload.decode("cp932", errors="strict")
                except UnicodeDecodeError:
                    text = "[text preview unavailable]"
                value["text"] = text[:max_text_characters]
                value["truncated"] = len(text) > max_text_characters
                value["normalization_occurrences"] = [
                    {
                        "source": payload.source_reference,
                        "coordinate_basis": "extracted chapter text",
                        "line": line,
                        "column": column,
                        "from": source,
                        "to": replacement,
                    }
                    for line, column, source, replacement
                    in payload.normalization_occurrences
                ]
            else:
                value["image"] = {
                    "width": 237,
                    "height": 320,
                    "bits_per_pixel": 1,
                    "profile": "validated-uncompressed-monochrome-bmp",
                }
            previews.append(value)
        return tuple(previews)

    def report(self) -> dict[str, Any]:
        return {
            "format": CONTENT_WORKSPACE_FORMAT,
            "version": 1,
            "source": {
                "path": str(self.source_path),
                "format": self.source_format,
                "sha256": self.source_sha256,
            },
            "metadata": {
                "title": self.title,
                "normalized_text_children": self.normalized_text_children,
                "normalization_events": self.normalization_events,
                "normalization_occurred": self.normalization_occurred,
                "user_notice": self.user_notice,
            },
            "preview": {
                "children": [dict(child) for child in self.preview_children()],
                "aggregate_prepared_bytes": self.artifact.aggregate_size,
            },
            "prepared_content_artifact": self.artifact.to_dict(),
            "transfer_shape_assessment": self.transfer_shape.to_dict(),
            "unsupported_features": [dict(feature) for feature in self.unsupported_features],
            "safety": {
                "usb_accessed": False,
                "device_change": "none",
                "candidate_constructed": False,
                "authorization_created": False,
                "transaction_constructed": False,
                "sender_called": False,
                "automatic_retry": False,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return self.report()


@dataclass(frozen=True)
class _EpubPackage:
    source_path: Path
    source_sha256: str
    files: Mapping[str, bytes]
    opf_path: str
    title: str
    manifest: Mapping[str, Mapping[str, Any]]
    spine: tuple[Mapping[str, Any], ...]
    unsupported_features: tuple[Mapping[str, Any], ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _feature(kind: str, detail: str, *, resource: Optional[str] = None) -> dict[str, Any]:
    value: dict[str, Any] = {"kind": kind, "detail": detail}
    if resource is not None:
        value["resource"] = resource
    return value


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1].casefold()


def _safe_xml(data: bytes, label: str) -> ElementTree.Element:
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper or re.search(rb"\b(?:SYSTEM|PUBLIC)\s+['\"]", upper):
        raise EpubSecurityError(f"{label} contains a prohibited XML entity or external declaration")
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise EpubPackageError(f"{label} is malformed XML") from exc


def _normal_path(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise EpubSecurityError(f"{label} is empty or contains NUL")
    if "\\" in value:
        raise EpubSecurityError(f"{label} must use forward-slash paths")
    decoded = unquote(value)
    parts = decoded.split("/")
    if any(part in {"", ".", ".."} for part in parts) or decoded.startswith("/"):
        raise EpubSecurityError(f"{label} is absolute or escapes the package root")
    return "/".join(PurePosixPath(decoded).parts)


def _resolve(base_path: str, href: str, label: str) -> str:
    if not isinstance(href, str) or not href:
        raise EpubPackageError(f"{label} href is missing")
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        raise EpubSecurityError(f"{label} uses a remote resource; network fetching is disabled")
    if parsed.query:
        raise EpubPackageError(f"{label} href query strings are unsupported")
    relative = unquote(parsed.path)
    if not relative or relative.startswith("/") or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise EpubSecurityError(f"{label} href is absolute or escapes the package root")
    return "/".join(PurePosixPath(PurePosixPath(base_path).parent, relative).parts)


def _read_zip(source: Path, limits: EpubLimits) -> tuple[dict[str, bytes], str]:
    if source.is_symlink() or not source.is_file():
        raise ValueError("EPUB source must be a regular non-symbolic file")
    try:
        size = source.stat().st_size
        if size > limits.max_source_bytes:
            raise EpubSecurityError(f"EPUB source exceeds the {limits.max_source_bytes}-byte bound")
        raw = source.read_bytes()
        archive = zipfile.ZipFile(source, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise EpubPackageError("EPUB source is not a valid ZIP container") from exc
    files: dict[str, bytes] = {}
    seen: set[str] = set()
    total = 0
    try:
        infos = archive.infolist()
        if not 1 <= len(infos) <= limits.max_archive_entries:
            raise EpubSecurityError(f"EPUB archive entry count exceeds the {limits.max_archive_entries}-entry bound")
        for info in infos:
            name = _normal_path(info.filename, "EPUB archive entry")
            if name.casefold() in seen:
                raise EpubSecurityError(f"EPUB contains a normalized duplicate archive path: {name}")
            seen.add(name.casefold())
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000 or info.flag_bits & 0x1:
                raise EpubSecurityError(f"EPUB archive entry is a symlink or encrypted: {name}")
            if info.file_size > limits.max_entry_uncompressed_bytes:
                raise EpubSecurityError(f"EPUB entry exceeds the configured size bound: {name}")
            if info.compress_size and info.file_size > info.compress_size * limits.max_compression_ratio:
                raise EpubSecurityError(f"EPUB entry exceeds the decompression-ratio bound: {name}")
            if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise EpubSecurityError(f"EPUB compression method is unsupported: {name}")
            with archive.open(info, "r") as stream:
                chunks: list[bytes] = []
                read_total = 0
                while True:
                    chunk = stream.read(64 * 1024)
                    if not chunk:
                        break
                    read_total += len(chunk)
                    total += len(chunk)
                    if read_total > limits.max_entry_uncompressed_bytes or total > limits.max_total_uncompressed_bytes:
                        raise EpubSecurityError("EPUB decompressed data exceeds the configured bound")
                    chunks.append(chunk)
            if read_total != info.file_size:
                raise EpubPackageError(f"EPUB entry size changed while reading: {name}")
            files[name] = b"".join(chunks)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise EpubPackageError("EPUB entry could not be read") from exc
    finally:
        archive.close()
    return files, _sha256(raw)


def _parse_package(files: Mapping[str, bytes], opf_path: str, limits: EpubLimits) -> tuple[str, dict[str, dict[str, Any]], tuple[dict[str, Any], ...], tuple[Mapping[str, Any], ...]]:
    root = _safe_xml(files[opf_path], "EPUB OPF package document")
    if _local_name(root.tag) != "package" or root.attrib.get("version") not in {"2.0", "3.0"}:
        raise EpubPackageError("EPUB OPF version or root is unsupported")
    metadata = next((child for child in root if _local_name(child.tag) == "metadata"), None)
    manifest_element = next((child for child in root if _local_name(child.tag) == "manifest"), None)
    spine_element = next((child for child in root if _local_name(child.tag) == "spine"), None)
    if manifest_element is None or spine_element is None:
        raise EpubPackageError("EPUB OPF manifest or spine is missing")
    title = ""
    if metadata is not None:
        for element in metadata.iter():
            if _local_name(element.tag) == "title" and (element.text or "").strip():
                title = " ".join((element.text or "").split())
                break
    title = title or Path(opf_path).stem
    if len(title) > limits.max_title_characters:
        raise EpubSecurityError("EPUB title metadata exceeds the configured bound")
    manifest: dict[str, dict[str, Any]] = {}
    features: list[Mapping[str, Any]] = []
    for element in manifest_element:
        if _local_name(element.tag) != "item":
            continue
        item_id = element.attrib.get("id")
        href = element.attrib.get("href")
        media_type = element.attrib.get("media-type", "").casefold()
        if not item_id or not href or not media_type or item_id in manifest:
            raise EpubPackageError("EPUB manifest item is malformed or duplicated")
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            features.append(_feature("remote-resources", "remote manifest resources are not fetched", resource=href))
            manifest[item_id] = {"id": item_id, "path": href, "media_type": media_type, "properties": element.attrib.get("properties", ""), "remote": True}
            continue
        path = _resolve(opf_path, href, f"EPUB manifest item {item_id}")
        if path not in files:
            raise EpubPackageError(f"EPUB manifest resource is missing: {path}")
        manifest[item_id] = {"id": item_id, "path": path, "media_type": media_type, "properties": element.attrib.get("properties", ""), "remote": False}
        if media_type not in SUPPORTED_EPUB_MEDIA_TYPES | SUPPORTED_EPUB_IMAGE_MEDIA_TYPES:
            features.append(_feature("unsupported-resource", f"manifest resource media type {media_type} was not converted", resource=path))
    spine: list[dict[str, Any]] = []
    for element in spine_element:
        if _local_name(element.tag) != "itemref":
            continue
        item_id = element.attrib.get("idref")
        if not item_id or item_id not in manifest:
            raise EpubPackageError("EPUB spine itemref is missing or not in the manifest")
        item = manifest[item_id]
        if item["remote"]:
            features.append(_feature("remote-resources", "remote spine resources are not fetched", resource=str(item["path"]))); continue
        if element.attrib.get("linear", "yes").casefold() == "no":
            features.append(_feature("non-linear-spine-item", "non-linear spine content was not included", resource=str(item["path"]))); continue
        spine.append(dict(item))
    if not spine:
        raise EpubPackageError("EPUB spine contains no linear document resources")
    if len(spine) > limits.max_chapters:
        raise EpubSecurityError("EPUB linear spine exceeds the configured chapter bound")
    for item in manifest.values():
        properties = str(item["properties"]).casefold().split()
        if "scripted" in properties:
            features.append(_feature("javascript", "script execution is disabled", resource=str(item["path"])))
        if "remote-resources" in properties:
            features.append(_feature("remote-resources", "remote resources are not fetched", resource=str(item["path"])))
    return title, manifest, tuple(spine), tuple(features)


def _package_from_source(source: Path, limits: EpubLimits) -> _EpubPackage:
    files, source_sha256 = _read_zip(source, limits)
    if "META-INF/encryption.xml" in files or "META-INF/rights.xml" in files:
        raise EpubPackageError("EPUB DRM or encryption metadata is not supported")
    container = files.get("META-INF/container.xml")
    if container is None:
        raise EpubPackageError("EPUB META-INF/container.xml is missing")
    root = _safe_xml(container, "EPUB container.xml")
    paths = [element.attrib.get("full-path") for element in root.iter() if _local_name(element.tag) == "rootfile"]
    if len(paths) != 1 or not paths[0]:
        raise EpubPackageError("EPUB container.xml must identify exactly one package document")
    opf_path = _normal_path(str(paths[0]), "EPUB container rootfile")
    if opf_path not in files:
        raise EpubPackageError("EPUB package document is missing from the container")
    title, manifest, spine, features = _parse_package(files, opf_path, limits)
    return _EpubPackage(source, source_sha256, files, opf_path, title, manifest, spine, features)


class _TextExtractor(HTMLParser):
    _BLOCKS = {"body", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p", "section", "table", "tr"}

    def __init__(self, resource: str) -> None:
        super().__init__(convert_charrefs=True)
        self.resource = resource
        self.parts: list[str] = []
        self.images: list[tuple[str, str]] = []
        self.features: list[Mapping[str, Any]] = []
        self._skip_depth = 0

    def _newline(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.casefold()
        attrs_map = dict(attrs)
        if tag in {"script", "style"}:
            self.features.append(_feature("javascript" if tag == "script" else "css-dependent-layout", f"{tag} content was not executed", resource=self.resource))
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self._BLOCKS:
            self._newline()
        if tag == "img" or tag == "image":
            href = attrs_map.get("src") or attrs_map.get("href")
            if href:
                self.images.append((href, attrs_map.get("alt") or ""))
                if attrs_map.get("alt"):
                    self.parts.append(attrs_map["alt"] or "")
        if any(key in attrs_map and str(attrs_map[key]).startswith(("http:", "https:")) for key in ("src", "href")):
            self.features.append(_feature("remote-resources", "remote XHTML resources are not fetched", resource=self.resource))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"script", "style"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if not self._skip_depth and tag in self._BLOCKS:
            self._newline()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        value = "".join(self.parts)
        lines = [" ".join(line.split()) for line in value.splitlines()]
        return "\n".join(line for line in lines if line).strip()


def _extract_xhtml(data: bytes, resource: str) -> tuple[str, tuple[tuple[str, str], ...], tuple[Mapping[str, Any], ...]]:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise EpubPackageError(f"EPUB XHTML is not valid UTF-8: {resource}") from exc
    parser = _TextExtractor(resource)
    try:
        parser.feed(text); parser.close()
    except ValueError as exc:
        raise EpubPackageError(f"EPUB XHTML could not be parsed: {resource}") from exc
    return parser.text(), tuple(parser.images), tuple(parser.features)


def _check_cancel(cancelled: Optional[Callable[[], bool]]) -> None:
    if cancelled is not None and cancelled():
        # Import lazily so the canonical workspace can re-export the same
        # typed error without creating an import cycle during module load.
        from .content_workspace import ContentWorkspaceError

        raise ContentWorkspaceError("EPUB preparation was cancelled before device access")


def _root_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(character in value for character in ("/", "\\", "\x00")):
        raise ValueError("prepared EPUB root name is malformed")
    try:
        value.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("prepared EPUB root name is not representable in CP932") from exc
    return value.strip()


def _payload(
    name: str,
    kind: str,
    payload: bytes,
    source: bytes,
    reference: str,
    *,
    normalized: bool = False,
    normalization_occurrences: tuple[tuple[int, int, str, str], ...] = (),
) -> PreparedContentPayload:
    return PreparedContentPayload(
        name,
        kind,
        payload,
        _sha256(source),
        len(source),
        reference,
        normalized,
        normalization_occurrences,
    )


def inspect_epub(source: Path, *, limits: EpubLimits = DEFAULT_EPUB_LIMITS) -> EpubInspection:
    package = _package_from_source(Path(source).expanduser().resolve(), limits)
    return EpubInspection(package.source_path, package.source_sha256, package.title, package.opf_path, tuple(str(item["path"]) for item in package.spine), package.unsupported_features)


def prepare_epub(source: Path, *, root_name: Optional[str] = None, limits: EpubLimits = DEFAULT_EPUB_LIMITS, cancelled: Optional[Callable[[], bool]] = None) -> PreparedContentResult:
    path = Path(source).expanduser()
    if path.is_symlink():
        raise ValueError("EPUB source must not be a symbolic link")
    package = _package_from_source(path.resolve(), limits)
    chosen_root = _root_name(package.title if root_name is None else root_name)
    payloads: list[PreparedContentPayload] = []
    features: list[Mapping[str, Any]] = list(package.unsupported_features)
    normalized_children = 0
    normalization_events = 0
    total_text = 0
    image_count = 0
    for chapter_index, item in enumerate(package.spine, 1):
        _check_cancel(cancelled)
        resource = str(item["path"])
        if str(item["media_type"]) not in SUPPORTED_EPUB_MEDIA_TYPES:
            features.append(_feature("unsupported-spine-media-type", "spine media type was not converted", resource=resource)); continue
        text, image_refs, chapter_features = _extract_xhtml(package.files[resource], resource)
        features.extend(chapter_features)
        total_text += len(text)
        if total_text > limits.max_text_characters:
            raise EpubSecurityError("extracted EPUB text exceeds the configured character bound")
        name = f"chapter-{chapter_index:03d}.txt"
        try:
            authored = encode_cp932_text(text)
        except TextAuthoringError as exc:
            raise EpubPackageError(
                f"EPUB chapter cannot be represented by CP932 ({resource}): {exc}"
            ) from exc
        payloads.append(
            _payload(
                name,
                "txt",
                authored.payload,
                package.files[resource],
                resource,
                normalized=authored.original_text != authored.normalized_text,
                normalization_occurrences=normalization_occurrences(text),
            )
        )
        normalized_children += 1
        normalization_events += int(authored.original_text != authored.normalized_text)
        for image_index, (href, _alt) in enumerate(image_refs, 1):
            _check_cancel(cancelled)
            image_path = _resolve(resource, href, "EPUB XHTML image")
            image_item = next((value for value in package.manifest.values() if value["path"] == image_path), None)
            image_bytes = package.files.get(image_path)
            if image_bytes is None:
                features.append(_feature("missing-local-image", "local image resource is missing", resource=image_path)); continue
            if image_item is None or image_item["media_type"] not in SUPPORTED_EPUB_IMAGE_MEDIA_TYPES:
                features.append(_feature("unsupported-embedded-image", "image media type is not converted", resource=image_path)); continue
            try:
                validate_bmp_payload(image_bytes)
            except PreparedMediaPackageError as exc:
                features.append(_feature("unsupported-embedded-image", f"BMP is outside the exact supported media profile: {exc}", resource=image_path)); continue
            image_count += 1
            if image_count > limits.max_image_children:
                raise EpubSecurityError("embedded EPUB image count exceeds the configured bound")
            payloads.append(_payload(f"chapter-{chapter_index:03d}-image-{image_index:03d}.bmp", "bmp", image_bytes, image_bytes, image_path))
    if not payloads:
        raise EpubPackageError("EPUB produced no supported text or image content")
    children = tuple(
        PreparedContentChild(
            order=index,
            kind=value.kind,
            name=value.name,
            path=f"root\\{chosen_root}\\{value.name}",
            payload_sha256=value.payload_sha256,
            payload_bytes=len(value.payload),
            payload_path=f"prepared/{chosen_root}/{value.name}",
            source_sha256=value.source_sha256,
            source_bytes=value.source_bytes,
        )
        for index, value in enumerate(payloads)
    )
    try:
        artifact = PreparedContentArtifact(chosen_root, children, profile_id=PREPARED_EPUB_PROFILE_ID)
    except PreparedContentError as exc:
        raise ValueError(f"prepared EPUB artifact is invalid: {exc}") from exc
    return PreparedContentResult(
        source_path=package.source_path,
        source_sha256=package.source_sha256,
        source_format="epub",
        title=package.title,
        artifact=artifact,
        payloads=tuple(payloads),
        unsupported_features=tuple(dict(feature) for feature in features),
        normalized_text_children=normalized_children,
        normalization_events=normalization_events,
        transfer_shape=assess_transfer_shape(artifact),
    )


def materialize(result: PreparedContentResult, destination: Path) -> Path:
    if not isinstance(result, PreparedContentResult):
        raise TypeError("result must be a PreparedContentResult")
    target = Path(destination).expanduser().resolve()
    if target.exists():
        from .content_workspace import ContentWorkspaceError

        raise ContentWorkspaceError(f"refusing to overwrite existing prepared output: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        prepared_root = temporary / "prepared" / result.artifact.root_name
        prepared_root.mkdir(parents=True)
        for payload in result.payloads:
            (prepared_root / payload.name).write_bytes(payload.payload)
        (temporary / "manifest.json").write_text(json.dumps(result.report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
        (temporary / "source.json").write_text(json.dumps({"path": str(result.source_path), "sha256": result.source_sha256, "format": result.source_format}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
        temporary.rename(target)
    except OSError as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        from .content_workspace import ContentWorkspaceError

        raise ContentWorkspaceError(f"could not materialize prepared content: {target}") from exc
    return target


__all__ = [
    "CONTENT_WORKSPACE_FORMAT",
    "DEFAULT_EPUB_LIMITS",
    "EPUB_MAX_ARCHIVE_ENTRIES",
    "EPUB_MAX_CHAPTERS",
    "EPUB_MAX_COMPRESSION_RATIO",
    "EPUB_MAX_ENTRY_UNCOMPRESSED_BYTES",
    "EPUB_MAX_IMAGE_CHILDREN",
    "EPUB_MAX_SOURCE_BYTES",
    "EPUB_MAX_TEXT_CHARACTERS",
    "EPUB_MAX_TITLE_CHARACTERS",
    "EPUB_MAX_TOTAL_UNCOMPRESSED_BYTES",
    "EpubInspection",
    "EpubLimits",
    "EpubPackageError",
    "EpubSecurityError",
    "PREPARED_EPUB_PROFILE_ID",
    "PreparedContentPayload",
    "PreparedContentResult",
    "SUPPORTED_EPUB_IMAGE_MEDIA_TYPES",
    "SUPPORTED_EPUB_MEDIA_TYPES",
    "inspect_epub",
    "materialize",
    "prepare_epub",
]

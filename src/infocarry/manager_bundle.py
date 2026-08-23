"""Offline synchronized mutations for an existing InfoCarry content bundle.

This module implements narrow, evidence-backed offline mutations: an existing
file can be renamed, a new file can be added using a captured record template,
or a leaf file can be deleted. Exact matching ``VICMEM.bin`` and
``VICLV.bin`` paths are updated/removed for rename/delete. ``order.vnw`` is
parsed and preserved byte-for-byte because its generated-basename lifecycle is
not yet sufficient for a complete model synchronizer. No function opens USB
or writes a device.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .order_control import parse_order_control
from .vicdata import (
    OBSERVED_VICDATA_XOR_KEY,
    VicDataError,
    add_file_from_template_vicdata,
    decode_vicdata,
    delete_existing_vicdata,
    rename_existing_vicdata,
)
from .viclv import (
    parse_viclv,
    remove_viclv_exact_path,
    replace_viclv_exact_path,
)
from .vicmem import (
    parse_vicmem,
    remove_vicmem_exact_path,
    replace_vicmem_exact_path,
)


class ManagerBundleError(ValueError):
    """Raised when a bounded manager-bundle mutation is unsafe."""


@dataclass(frozen=True)
class ManagerBundle:
    """A validated, offline bundle of manager-side files."""

    vicdata: bytes
    vicmem: Optional[bytes] = None
    viclv: Optional[bytes] = None
    order: Optional[bytes] = None

    def __post_init__(self) -> None:
        if not isinstance(self.vicdata, bytes):
            raise ManagerBundleError("vicdata must be bytes")
        for label, value in (
            ("vicmem", self.vicmem),
            ("viclv", self.viclv),
            ("order", self.order),
        ):
            if value is not None and not isinstance(value, bytes):
                raise ManagerBundleError(f"{label} must be bytes or None")


def _full_file_path(path_parts: tuple[str, ...], extension: str) -> str:
    path = "\\".join(path_parts)
    return f"{path}.{extension}" if extension else path


def rename_existing_file_bundle(
    encoded_vicdata: bytes,
    record_offset: int,
    new_name: str,
    *,
    vicmem: Optional[bytes] = None,
    viclv: Optional[bytes] = None,
    order: Optional[bytes] = None,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> ManagerBundle:
    """Rename one existing reachable file and update exact sidecar paths.

    Exact matching ``VICLV.bin`` entries are updated while category/order and
    opaque padding remain unchanged. ``order.vnw`` is validated and retained
    byte-for-byte because it contains generated basenames rather than a
    directly addressable full path. The returned encoded VICDATA and optional
    sidecars are parsed again before the bundle is returned.
    """

    try:
        before = decode_vicdata(encoded_vicdata, key=key)
    except VicDataError as exc:
        raise ManagerBundleError(str(exc)) from exc
    try:
        record = before.record_at(record_offset)
    except Exception as exc:
        raise ManagerBundleError(f"could not resolve record 0x{record_offset:x}") from exc
    if record.kind != "file":
        raise ManagerBundleError("bounded bundle rename requires an existing file record")
    path_parts = before.paths.get(record_offset)
    if path_parts is None:
        raise ManagerBundleError(f"record 0x{record_offset:x} is not reachable")
    old_full_path = _full_file_path(path_parts, record.extension)
    new_path_parts = path_parts[:-1] + (new_name,)
    new_full_path = _full_file_path(new_path_parts, record.extension)

    try:
        rebuilt_vicdata = rename_existing_vicdata(
            encoded_vicdata, record_offset, new_name, key=key
        )
    except VicDataError as exc:
        raise ManagerBundleError(str(exc)) from exc

    rebuilt_vicmem = vicmem
    if vicmem is not None:
        try:
            mem = parse_vicmem(vicmem)
            rebuilt_vicmem = replace_vicmem_exact_path(
                mem, old_full_path, new_full_path
            ).to_bytes()
            parse_vicmem(rebuilt_vicmem)
        except ValueError as exc:
            raise ManagerBundleError(f"VICMEM rename failed: {exc}") from exc

    rebuilt_viclv = viclv
    if viclv is not None:
        try:
            rebuilt_viclv = replace_viclv_exact_path(
                parse_viclv(viclv), old_full_path, new_full_path
            ).to_bytes()
            parse_viclv(rebuilt_viclv)
        except ValueError as exc:
            raise ManagerBundleError(f"VICLV rename failed: {exc}") from exc
    if order is not None:
        try:
            if parse_order_control(order).to_bytes() != order:
                raise ManagerBundleError("order.vnw round-trip is not byte-identical")
        except ValueError as exc:
            raise ManagerBundleError(f"order.vnw validation failed: {exc}") from exc

    after = decode_vicdata(rebuilt_vicdata, key=key)
    if after.paths.get(record_offset, ())[-1:] != (new_name,):
        raise ManagerBundleError("VICDATA rename did not survive final validation")
    return ManagerBundle(
        vicdata=rebuilt_vicdata,
        vicmem=rebuilt_vicmem,
        viclv=rebuilt_viclv,
        order=order,
    )


def _validate_preserved_sidecars(viclv: Optional[bytes], order: Optional[bytes]) -> None:
    if viclv is not None:
        try:
            if parse_viclv(viclv).to_bytes() != viclv:
                raise ManagerBundleError("VICLV round-trip is not byte-identical")
        except ValueError as exc:
            raise ManagerBundleError(f"VICLV validation failed: {exc}") from exc
    if order is not None:
        try:
            if parse_order_control(order).to_bytes() != order:
                raise ManagerBundleError("order.vnw round-trip is not byte-identical")
        except ValueError as exc:
            raise ManagerBundleError(f"order.vnw validation failed: {exc}") from exc


def add_file_bundle(
    encoded_vicdata: bytes,
    target_directory_offset: int,
    source_offset: int,
    new_name: str,
    payload: bytes,
    *,
    vicmem: Optional[bytes] = None,
    viclv: Optional[bytes] = None,
    order: Optional[bytes] = None,
    timestamp_be32: Optional[int] = None,
    flag: Optional[int] = None,
    metadata_timestamp_be32: Optional[int] = None,
    metadata_timestamps: Optional[dict[int, int]] = None,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> ManagerBundle:
    """Add one template-backed file while preserving unmodeled sidecars.

    ``VICMEM.bin`` is validated and returned unchanged because a new file is
    not automatically a selected/bookmarked file. Callers that need a
    selected entry must update that sidecar explicitly after reviewing its
    category semantics.
    """

    try:
        decode_vicdata(encoded_vicdata, key=key)
        rebuilt_vicdata = add_file_from_template_vicdata(
            encoded_vicdata,
            target_directory_offset,
            source_offset,
            new_name,
            payload,
            timestamp_be32=timestamp_be32,
            flag=flag,
            metadata_timestamp_be32=metadata_timestamp_be32,
            metadata_timestamps=metadata_timestamps,
            key=key,
        )
    except VicDataError as exc:
        raise ManagerBundleError(str(exc)) from exc
    if vicmem is not None:
        try:
            if parse_vicmem(vicmem).to_bytes() != vicmem:
                raise ManagerBundleError("VICMEM round-trip is not byte-identical")
        except ValueError as exc:
            raise ManagerBundleError(f"VICMEM validation failed: {exc}") from exc
    _validate_preserved_sidecars(viclv, order)
    return ManagerBundle(vicdata=rebuilt_vicdata, vicmem=vicmem, viclv=viclv, order=order)


def delete_file_bundle(
    encoded_vicdata: bytes,
    record_offset: int,
    *,
    vicmem: Optional[bytes] = None,
    viclv: Optional[bytes] = None,
    order: Optional[bytes] = None,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> ManagerBundle:
    """Delete one leaf file and remove exact matching ``VICMEM`` paths.

    Exact matching ``VICLV.bin`` entries are removed. ``order.vnw`` remains
    byte-identical because its basename ordering and generated-file lifecycle
    are not inferred by this bounded operation.
    """

    try:
        before = decode_vicdata(encoded_vicdata, key=key)
        record = before.record_at(record_offset)
    except (VicDataError, ValueError) as exc:
        raise ManagerBundleError(f"could not resolve delete target: {exc}") from exc
    if record.kind != "file" or record_offset not in before.paths:
        raise ManagerBundleError("file-bundle delete requires a reachable file record")
    path_parts = before.paths[record_offset]
    old_full_path = _full_file_path(path_parts, record.extension)
    try:
        rebuilt_vicdata = delete_existing_vicdata(encoded_vicdata, record_offset, key=key)
    except VicDataError as exc:
        raise ManagerBundleError(str(exc)) from exc

    rebuilt_vicmem = vicmem
    if vicmem is not None:
        try:
            rebuilt_vicmem = remove_vicmem_exact_path(parse_vicmem(vicmem), old_full_path).to_bytes()
            parse_vicmem(rebuilt_vicmem)
        except ValueError as exc:
            raise ManagerBundleError(f"VICMEM delete failed: {exc}") from exc
    rebuilt_viclv = viclv
    if viclv is not None:
        try:
            rebuilt_viclv = remove_viclv_exact_path(
                parse_viclv(viclv), old_full_path
            ).to_bytes()
            parse_viclv(rebuilt_viclv)
        except ValueError as exc:
            raise ManagerBundleError(f"VICLV delete failed: {exc}") from exc
    _validate_preserved_sidecars(rebuilt_viclv, order)
    return ManagerBundle(
        vicdata=rebuilt_vicdata,
        vicmem=rebuilt_vicmem,
        viclv=rebuilt_viclv,
        order=order,
    )


__all__ = [
    "ManagerBundle",
    "ManagerBundleError",
    "add_file_bundle",
    "delete_file_bundle",
    "rename_existing_file_bundle",
]

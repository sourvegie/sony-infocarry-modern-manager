"""Isolated Experimental Library transfer entrypoint.

This is the only product-facing integration shim for the exact P17 Library
profile.  It accepts the immutable operation bundle as the sole operation
description and delegates all safety, sender, one-shot, post-backup, and
P17-019 reconciliation behavior to the reviewed canonical components.  It is
not imported by the normal CLI or ttk GUI import graph.
"""

from __future__ import annotations

from typing import Any

from .prepared_library_package_live_adapter import (
    PreparedLibraryPackageLiveResult,
    PreparedLibraryPackageLiveWrapperResult,
    execute_prepared_library_package_live,
    reconcile_prepared_library_package_live_result,
)
from .prepared_library_package_operation_bundle import PreparedLibraryPackageOperationBundle


def run_experimental_library_transfer(
    operation_bundle: PreparedLibraryPackageOperationBundle,
    *,
    low_level_bulk_write_calls: int | None = None,
    **runner_kwargs: Any,
) -> PreparedLibraryPackageLiveResult | PreparedLibraryPackageLiveWrapperResult:
    """Run the exact guarded path from one immutable bundle.

    ``runner_kwargs`` are runtime callbacks and policy controls only.  Reports,
    backups, catalog, template, capacity, candidate, transaction, and output
    paths are resolved from ``operation_bundle`` or allocated by the canonical
    runner; callers cannot manually pair those safety inputs here.
    """

    result = execute_prepared_library_package_live(operation_bundle, **runner_kwargs)
    if runner_kwargs.get("preflight_only", False):
        return result
    return reconcile_prepared_library_package_live_result(
        result,
        low_level_bulk_write_calls=low_level_bulk_write_calls,
    )


__all__ = ["run_experimental_library_transfer"]

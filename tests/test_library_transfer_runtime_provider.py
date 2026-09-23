"""Host-only tests for packaged production Library runtime wiring."""

import hashlib
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.app_paths import application_paths
from infocarry.execution_claim_store import PersistentExecutionClaimStore
from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
from infocarry.library_transfer_execution import LibraryTransferExecutionFacade
from infocarry.library_transfer_runtime_provider import (
    LibraryTransferRuntimeConfigurationError,
    ProductionLibraryTransferRuntimeProvider,
    create_production_library_transfer_facade,
    launch_production_manager,
)
from infocarry.write_safety_boundary import PersistentWriteSafetyOwner
import scripts.macos_manager_entry as macos_entry
import scripts.windows_manager_entry as windows_entry


class ProductionLibraryTransferRuntimeProviderTests(unittest.TestCase):
    def test_shared_manager_launcher_injects_only_lazy_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = application_paths(
                home=Path(temporary),
                environ={},
                platform="darwin",
                os_name="posix",
            )
            with patch(
                "infocarry.library_transfer_runtime_provider.application_paths",
                return_value=paths,
            ), patch("infocarry.desktop_ttk.launch_ttk_desktop") as launch, patch(
                "infocarry.usb_access.find_one_device"
            ) as discover, patch(
                "infocarry.transport.InfoCarrySession.open"
            ) as open_session:
                launch_production_manager()

            launch.assert_called_once()
            facade = launch.call_args.kwargs["execution_facade"]
            self.assertIsInstance(facade, LibraryTransferExecutionFacade)
            self.assertIsInstance(
                facade.runtime_provider,
                ProductionLibraryTransferRuntimeProvider,
            )
            self.assertIsNone(facade.runtime)
            self.assertIsNone(facade.operation_binding)
            self.assertEqual(facade.evidence_namespace, paths.evidence_root / "Library Transfer Operations")
            discover.assert_not_called()
            open_session.assert_not_called()
            self.assertFalse(paths.execution_claims_database.exists())
            self.assertFalse(paths.indeterminate_write_lock.exists())

    def test_macos_and_windows_normal_entrypoints_use_shared_launcher(self):
        for entry in (macos_entry, windows_entry):
            with self.subTest(entry=entry.__name__), patch.object(
                sys, "argv", [entry.__file__]
            ), patch(
                "infocarry.library_transfer_runtime_provider.launch_production_manager"
            ) as launch:
                self.assertEqual(entry.main(), 0)
                launch.assert_called_once_with()

    def test_runtime_configuration_fails_closed_before_any_device_callback(self):
        for template_contents in (None, b"not the reviewed template"):
            with self.subTest(template=template_contents is not None):
                with tempfile.TemporaryDirectory() as temporary:
                    paths = application_paths(
                        home=Path(temporary),
                        environ={},
                        platform="darwin",
                        os_name="posix",
                    )
                    if template_contents is not None:
                        paths.evidence_root.mkdir(parents=True)
                        (paths.evidence_root / "reviewed-vnw-v15-library-template.bin").write_bytes(
                            template_contents
                        )
                    device_calls = []
                    provider = ProductionLibraryTransferRuntimeProvider(
                        paths=paths,
                        discover_device=lambda: device_calls.append("discover"),
                        open_session=lambda *_args, **_kwargs: device_calls.append("open"),
                        unix_time=lambda: 1,
                    )
                    owner = PersistentWriteSafetyOwner(
                        execution_claim_store=PersistentExecutionClaimStore(
                            paths.execution_claims_database
                        ),
                        indeterminate_write_lock=PersistentIndeterminateWriteLock(
                            paths.indeterminate_write_lock
                        ),
                    )

                    with self.assertRaises(LibraryTransferRuntimeConfigurationError):
                        provider.create_runtime(write_safety_owner=owner)
                    self.assertEqual(device_calls, [])

    def test_alternate_safety_paths_cannot_be_injected_into_production_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = application_paths(
                home=root / "profile",
                environ={},
                platform="darwin",
                os_name="posix",
            )
            alternate_owner = PersistentWriteSafetyOwner(
                execution_claim_store=PersistentExecutionClaimStore(
                    root / "alternate" / "claims.sqlite3"
                ),
                indeterminate_write_lock=PersistentIndeterminateWriteLock(
                    root / "alternate" / "lock.json"
                ),
            )
            device_calls = []
            provider = ProductionLibraryTransferRuntimeProvider(
                paths=paths,
                discover_device=lambda: device_calls.append("discover"),
                open_session=lambda *_args, **_kwargs: device_calls.append("open"),
                unix_time=lambda: 1,
            )

            with self.assertRaisesRegex(
                LibraryTransferRuntimeConfigurationError,
                "canonical application claim and lock paths",
            ):
                provider.create_runtime(write_safety_owner=alternate_owner)
            self.assertEqual(device_calls, [])

    def test_valid_reviewed_template_builds_canonical_runtime_without_device_access(self):
        try:
            from test_prepared_library_package_live_adapter import _named_template_blob
        except ModuleNotFoundError:
            from tests.test_prepared_library_package_live_adapter import _named_template_blob

        with tempfile.TemporaryDirectory() as temporary:
            paths = application_paths(
                home=Path(temporary),
                environ={},
                platform="darwin",
                os_name="posix",
            )
            paths.evidence_root.mkdir(parents=True)
            template_bytes = _named_template_blob()
            template_path = paths.evidence_root / "reviewed-vnw-v15-library-template.bin"
            template_path.write_bytes(template_bytes)
            claim_store = PersistentExecutionClaimStore(paths.execution_claims_database)
            lock = PersistentIndeterminateWriteLock(paths.indeterminate_write_lock)
            owner = PersistentWriteSafetyOwner(
                execution_claim_store=claim_store,
                indeterminate_write_lock=lock,
            )
            device_calls = []
            provider = ProductionLibraryTransferRuntimeProvider(
                paths=paths,
                discover_device=lambda: device_calls.append("discover"),
                open_session=lambda *_args, **_kwargs: device_calls.append("open"),
                unix_time=lambda: 1,
            )
            with patch(
                "infocarry.library_transfer_runtime_provider.P17_003_REVIEWED_TEMPLATE_BLOB_SHA256",
                hashlib.sha256(template_bytes).hexdigest(),
            ):
                runtime = provider.create_runtime(write_safety_owner=owner)

            self.assertEqual(runtime.template.data, template_bytes)
            self.assertEqual(runtime.template_path, template_path)
            self.assertEqual(runtime.evidence_namespace, paths.evidence_root / "Library Transfer Operations")
            self.assertIs(runtime.execution_claim_store, claim_store)
            self.assertIs(runtime.indeterminate_write_lock, lock)
            self.assertEqual(device_calls, [])

    def test_factory_creation_is_inert_and_uses_shared_application_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = application_paths(
                home=Path(temporary),
                environ={},
                platform="win32",
                os_name="nt",
            )
            device_calls = []
            with patch(
                "infocarry.library_transfer_runtime_provider.application_paths",
                return_value=paths,
            ):
                facade = create_production_library_transfer_facade(
                    discover_device=lambda: device_calls.append("discover"),
                    open_session=lambda *_args, **_kwargs: device_calls.append("open"),
                )

            self.assertIsNone(facade.runtime)
            self.assertIsNone(facade.operation_binding)
            self.assertEqual(facade.runtime_provider.paths, paths)
            self.assertEqual(device_calls, [])
            self.assertFalse(paths.execution_claims_database.exists())
            self.assertFalse(paths.indeterminate_write_lock.exists())


if __name__ == "__main__":
    unittest.main()

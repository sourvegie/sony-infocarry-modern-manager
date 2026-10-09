"""Execute real ttk Delete callbacks with lightweight widgets and host fakes.

No display server or physical USB is required. The actual shared controller
runs workers and posts their results/progress back onto the test main thread.
"""
import ast
import inspect
import queue
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from infocarry import desktop_ttk
from infocarry.operation_controller import OperationController
try:
    import test_device_library_delete_execution as helpers
except ModuleNotFoundError:
    from tests import test_device_library_delete_execution as helpers


class Var:
    def __init__(self, value=''):
        self.value = value
    def set(self, value):
        self.value = value
    def get(self):
        return self.value


class Tree:
    def __init__(self):
        self.items = ['target']
    def selection(self):
        return tuple(self.items)
    def selection_remove(self, _items):
        self.items.clear()


def callback_harness(env):
    source = ast.parse(inspect.getsource(desktop_ttk.launch_ttk_desktop))
    functions = {node.name: node for node in source.body[0].body if isinstance(node, ast.FunctionDef)}
    assignments = [ast.Assign([ast.Name(key, ast.Store())],
                   ast.Subscript(ast.Name('env', ast.Load()), ast.Constant(key), ast.Load())) for key in env]
    # Use the actual callback bodies with their original lexical/nonlocal scopes.
    getter = ast.parse("def state():\n    return device_delete_active, library_device_change_in_progress, device_delete_evidence, loaded_backup_summary").body[0]
    body = assignments + [functions[name] for name in ('start_library_operation', 'device_delete_action', 'close_action')] + [getter]
    body += ast.parse('return device_delete_action, close_action, state').body
    wrapper = ast.FunctionDef('create', ast.arguments(posonlyargs=[], args=[ast.arg('env')], kwonlyargs=[], kw_defaults=[], defaults=[]), body, [], None)
    module = ast.fix_missing_locations(ast.Module([wrapper], []))
    globals_ = vars(desktop_ttk).copy()
    exec(compile(module, '<actual-ttk-delete-callbacks>', 'exec'), globals_)
    return globals_['create'](env)


class DeviceLibraryDeleteUITests(unittest.TestCase):
    def setup_ui(self, *, confirmed=True, options=None, reconnect=False):
        helper = helpers.DeviceLibraryDeleteExecutionTests('test_supported_selection_and_single_readable_review')
        self.addCleanup(helper.doCleanups)
        data = helper.setup_case(backend_options=options, reconnect=reconnect)
        case, model, selection, service = data
        original_prepare = service.prepare
        def prepare(*args, **kwargs):
            prepared = original_prepare(*args, **kwargs)
            case[2]['bundle'] = prepared.bundle
            return prepared
        service.prepare = prepare
        posted = queue.Queue()
        controller = OperationController(posted.put)
        self.addCleanup(controller.close)
        statuses = Var()
        main_status = Var()
        library_status = Var()
        tree = Tree()
        dialogs, refreshes, controls, notices = [], [], [], []
        refresh_failure = {'fail': False}
        root = SimpleNamespace(destroy=lambda: notices.append('closed'))
        def confirm(_root, message):
            dialogs.append(message)
            return confirmed() if callable(confirmed) else confirmed
        env = dict(
            model=model, tree=tree, tree_items={'target': selection.row.record_offset},
            worker=None, device_delete_active=False, device_delete_evidence=None,
            library_device_change_in_progress=False, library_operation_token=None,
            library_current_readiness=None, loaded_backup_summary=None,
            library_operation_controller=controller, device_delete_service=service,
            device_delete_status_var=statuses, status_var=main_status,
            library_status_var=library_status, library_operation_activity_var=Var(),
            library_cancel_button=SimpleNamespace(configure=lambda **kwargs: controls.append(kwargs)),
            library_report=None, root=root,
            confirm_device_library_delete=confirm,
            show_selection=lambda: statuses.set('Selection state'),
            show_library_selection=lambda: None,
            clear_library_review_for_input_change=lambda: None,
            refresh_tree=lambda: (_ for _ in ()).throw(OSError('disk')) if refresh_failure['fail'] else refreshes.append(tuple(r.display_name for r in model.rows())),
            update_device_home_display=lambda: None,
            set_library_operation_busy=lambda busy, **kwargs: controls.append(busy),
            library_selection_matches=lambda _revision: True,
            cancel_event=threading.Event(),
            messagebox=SimpleNamespace(showinfo=lambda *a, **kw: notices.append(a), askyesno=lambda *a, **kw: True),
        )
        action, close, state = callback_harness(env)
        def drain():
            # Each callback is delivered on this test's main thread, as with Tk.
            while controller.busy or not posted.empty():
                try:
                    callback = posted.get(timeout=3)
                except queue.Empty:
                    self.fail('Delete worker did not deliver a terminal callback')
                callback()
        return SimpleNamespace(data=data, action=action, close=close, state=state, controller=controller,
            drain=drain, dialogs=dialogs, refreshes=refreshes, controls=controls, notices=notices,
            tree=tree, statuses=statuses, main_status=main_status, posted=posted, refresh_failure=refresh_failure)

    def test_delete_confirm_verify_refresh_in_one_dialog(self):
        ui = self.setup_ui(reconnect=True)
        ui.action()
        ui.drain()
        self.assertEqual(len(ui.dialogs), 1)
        self.assertEqual(len(ui.refreshes), 1)
        self.assertIn('Delete complete', ui.statuses.get())
        self.assertEqual(ui.tree.items, [])
        self.assertEqual(ui.state()[:2], (False, False))
        self.assertEqual(ui.state()[2].audit['workflow']['sender_calls'], 1)
        self.assertIn({'state': 'disabled'}, ui.controls)
        self.assertNotIn(helpers.FIXTURE_PATH, ui.refreshes[0])

    def test_cancel_dialog_never_sends_or_refreshes(self):
        ui = self.setup_ui(confirmed=False)
        ui.action()
        ui.drain()
        self.assertEqual(len(ui.dialogs), 1)
        self.assertEqual(ui.refreshes, [])
        self.assertEqual(ui.data[0][3].calls, [])
        self.assertEqual(ui.state()[:2], (False, False))
        self.assertIn('cancelled', ui.statuses.get())
        self.assertTrue(ui.data[0][2]['closed'])

    def test_stale_selection_before_review_discards_without_dialog(self):
        ui = self.setup_ui()
        ui.action()
        ui.tree.items.clear()
        ui.drain()
        self.assertEqual(ui.dialogs, [])
        self.assertEqual(ui.data[0][3].calls, [])
        self.assertEqual(ui.state()[:2], (False, False))
        self.assertIn('Selection changed', ui.statuses.get())

    def test_selection_changed_during_dialog_never_sends(self):
        ui = self.setup_ui(confirmed=lambda: (ui.tree.items.clear() or True))
        ui.action()
        ui.drain()
        self.assertEqual(len(ui.dialogs), 1)
        self.assertEqual(ui.data[0][3].calls, [])
        self.assertEqual(ui.refreshes, [])
        self.assertEqual(ui.state()[:2], (False, False))

    def test_second_click_during_preparation_does_not_start_another_attempt(self):
        ui = self.setup_ui(confirmed=False)
        ui.action()
        ui.action()
        ui.drain()
        self.assertEqual(len(ui.dialogs), 1)
        self.assertEqual(ui.data[0][3].calls, [])

    def test_preparation_cancel_never_opens_confirmation(self):
        ui = self.setup_ui()
        ui.action()
        ui.controller.cancel()
        ui.drain()
        self.assertEqual(ui.dialogs, [])
        self.assertEqual(ui.data[0][3].calls, [])
        self.assertIn('cancelled before execution', ui.statuses.get())
        self.assertEqual(ui.state()[:2], (False, False))

    def test_backend_disconnect_error_survives_selection_control_refresh(self):
        ui = self.setup_ui(options={'fail_bulk_at': 2})
        ui.action()
        ui.drain()
        self.assertIn('uncertain', ui.statuses.get())
        self.assertIn('locked', ui.main_status.get())
        self.assertEqual(ui.refreshes, [])
        self.assertIsNotNone(ui.state()[2])
        self.assertEqual(ui.state()[:2], (False, False))
        self.assertEqual(sum(c[0]=='control_out' for c in ui.data[0][3].calls), 1)

    def test_nonzero_completion_has_no_success_or_refresh(self):
        ui = self.setup_ui(options={'completion': (2,)})
        ui.action()
        ui.drain()
        self.assertIn('transfer failed', ui.statuses.get())
        self.assertEqual(ui.refreshes, [])
        self.assertEqual(ui.state()[:2], (False, False))

    def test_refresh_error_is_not_hidden_as_success(self):
        ui = self.setup_ui()
        ui.refresh_failure['fail'] = True
        ui.action()
        ui.drain()
        self.assertIn('refresh failed', ui.statuses.get())
        self.assertNotIn('Delete complete', ui.statuses.get())
        self.assertEqual(ui.refreshes, [])

    def test_post_result_evidence_failure_is_not_reported_as_verified(self):
        ui = self.setup_ui()
        def corrupt_after(model, result):
            dynamic = result.after_backup.directory / result.after_backup.object_filename('0x8004:backup-blob')
            dynamic.write_bytes(dynamic.read_bytes() + b'x')
            return desktop_ttk.load_verified_delete_result(model, result)
        with patch.dict(ui.action.__globals__, load_verified_delete_result=corrupt_after):
            ui.action()
            ui.drain()
        self.assertIn('verification failed', ui.statuses.get())
        self.assertNotIn('Delete verified', ui.statuses.get())
        self.assertEqual(ui.refreshes, [])
        self.assertEqual(ui.state()[:2], (False, False))

    def test_close_during_execution_is_blocked(self):
        ui = self.setup_ui()
        ui.action()
        # Drain only until execution owns the UI; use an event to keep its first
        # progress callback pending long enough to inspect the close boundary.
        while not ui.state()[1]:
            ui.posted.get(timeout=3)()
        ui.close()
        self.assertNotIn('closed', ui.notices)
        self.assertTrue(ui.notices)
        ui.drain()
        self.assertIn('Delete complete', ui.statuses.get())

    def test_teardown_releases_prepared_review_without_late_dialog(self):
        ui = self.setup_ui()
        ui.action()
        ui.close()
        self.assertIn('closed', ui.notices)
        # Wait for the read-only worker to wind down; controller suppresses any
        # queued GUI result and service closes its pinned runtime itself.
        import time
        end = time.monotonic() + 3
        while not ui.data[0][2]['closed'] and time.monotonic() < end:
            time.sleep(0.01)
        self.assertEqual(ui.dialogs, [])
        self.assertEqual(ui.data[0][3].calls, [])


if __name__ == '__main__':
    unittest.main()

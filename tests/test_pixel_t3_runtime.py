import importlib.util
from pathlib import Path
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('runtime', Path(__file__).parents[1] / 'pixel-t3-runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class IdleTest(unittest.TestCase):
    def test_stops_only_after_five_minutes_of_verified_idle(self):
        sample = {'ok': True, 'busy': False, 'foreground': False, 'time': 1000}
        self.assertEqual((0, False), runtime.idle_elapsed(sample, 0, 299, 1000))
        self.assertEqual((0, True), runtime.idle_elapsed(sample, 0, 300, 1000))

    def test_unknown_stale_and_active_state_reset_idle_countdown(self):
        idle = {'ok': True, 'busy': False, 'foreground': False, 'time': 1000}
        for change in [{'ok': False}, {'busy': True}, {'time': 900},
                       {'time': 1100}, {'busy': None}]:
            with self.subTest(change=change):
                self.assertEqual((400, False), runtime.idle_elapsed({**idle, **change}, 0, 400, 1000))
        self.assertEqual((400, False), runtime.idle_elapsed({}, 0, 400, 1000))

    def test_visible_chat_without_input_can_sleep(self):
        sample = {'ok': True, 'busy': False, 'foreground': True, 'time': 1000}
        self.assertEqual((0, True), runtime.idle_elapsed(sample, 0, 300, 1000))

    def test_finished_task_gets_the_entire_idle_period(self):
        working = {'ok': True, 'busy': True, 'time': 1000}
        last_use, stopped = runtime.idle_elapsed(working, 0, 1200, 1000)
        self.assertFalse(stopped)
        idle = {**working, 'busy': False}
        self.assertEqual((1200, False), runtime.idle_elapsed(idle, last_use, 1499, 1000))
        self.assertEqual((1200, True), runtime.idle_elapsed(idle, last_use, 1500, 1000))


class StopTest(unittest.TestCase):
    def setUp(self):
        # The runtime targets Android/Linux; Windows has no SIGKILL constant.
        self.signal_patch = patch.object(runtime.signal, 'SIGKILL', 9, create=True)
        self.signal_patch.start()
        self.addCleanup(self.signal_patch.stop)

    def test_stale_pid_is_never_signalled(self):
        with patch.object(runtime, 'identity', return_value='new-process'), \
             patch.object(runtime.os, 'kill') as kill, \
             patch.object(runtime, 'descendants') as descendants:
            runtime.stop_processes([{'pid': 42, 'start': 'old-process'}])
        kill.assert_not_called()
        descendants.assert_not_called()

    def test_stop_includes_detached_children_but_no_unrelated_process(self):
        alive = {41: 'parent', 42: 'detached-child', 99: 'unrelated'}
        def kill(pid, sig):
            alive.pop(pid, None)
        with patch.object(runtime, 'identity', side_effect=lambda pid: alive.get(pid)), \
             patch.object(runtime, 'descendants', return_value={42}), \
             patch.object(runtime.os, 'kill', side_effect=kill) as killed:
            runtime.stop_processes([{'pid': 41, 'start': 'parent'}])
        self.assertEqual({41, 42}, {call.args[0] for call in killed.call_args_list})
        self.assertEqual({99: 'unrelated'}, alive)


class ProviderWorkTest(unittest.TestCase):
    def test_live_command_survives_a_settled_t3_turn(self):
        with patch.object(runtime, 'descendants', side_effect=lambda pid: {42} if pid == 41 else {43}), \
             patch.object(Path, 'read_bytes', return_value=b'opencode\0serve\0--port=42021\0'):
            self.assertTrue(runtime.provider_work(41))

    def test_an_idle_provider_server_does_not_prevent_sleep(self):
        with patch.object(runtime, 'descendants', side_effect=lambda pid: {42} if pid == 41 else set()), \
             patch.object(Path, 'read_bytes', return_value=b'opencode\0serve\0--port=42021\0'):
            self.assertFalse(runtime.provider_work(41))


class WirelessSleepTest(unittest.TestCase):
    def test_enabled_setting_is_restored_after_sleep(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'rish').touch()
            with patch.object(runtime, 'STATE', folder), patch.object(runtime, 'BIN', folder), \
                    patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='1\n')) as run:
                runtime.wireless_debugging(True)
                self.assertTrue((folder / 'wireless-debugging.json').exists())
                self.assertEqual('settings put global adb_wifi_enabled 0', run.call_args.args[0][-1])
                runtime.wireless_debugging(False)
                self.assertEqual('settings put global adb_wifi_enabled 1', run.call_args.args[0][-1])
                self.assertFalse((folder / 'wireless-debugging.json').exists())

    def test_user_disabled_setting_is_left_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'rish').touch()
            with patch.object(runtime, 'STATE', folder), patch.object(runtime, 'BIN', folder), \
                    patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='0\n')) as run:
                runtime.wireless_debugging(True)
                self.assertEqual(1, run.call_count)
                self.assertFalse((folder / 'wireless-debugging.json').exists())


if __name__ == '__main__':
    unittest.main()

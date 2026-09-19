import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('control', Path(__file__).parents[1] / 'pixel-app-control.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class AppControlTest(unittest.TestCase):
    def test_only_input_refreshes_idle_time(self):
        control.main(['status', 'visible'])
        self.assertFalse((self.state / 'use').exists())
        control.main(['status', 'active'])
        self.assertTrue((self.state / 'use').exists())

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        for target in (control, control.runtime):
            change = patch.object(target, 'STATE', self.state)
            change.start()
            self.addCleanup(change.stop)

    def test_idle_setting_persists_and_rejects_invalid_values(self):
        control.main(['settings', '15'])
        self.assertEqual(15, control.runtime.idle_minutes())
        with self.assertRaises(ValueError):
            control.main(['settings', '0'])
        self.assertEqual(15, control.runtime.idle_minutes())

    def test_missing_owner_is_reported_as_recoverable_stopped_service(self):
        control.runtime.write_state('ready')
        self.assertEqual('stopped', control.status()['phase'])

    def test_damaged_settings_use_the_default_without_affecting_other_files(self):
        (self.state / 'settings.json').write_text('bad json')
        project = self.state / 'project.txt'
        project.write_text('keep this')
        self.assertEqual(5, control.runtime.idle_minutes())
        control.main(['settings', '2'])
        self.assertEqual('keep this', project.read_text())

    def test_stop_during_restart_cancels_the_pending_start(self):
        def interrupted_stop(**kwargs):
            (self.state / 'cancel-start').touch()
        with patch.object(control, 'stop', side_effect=interrupted_stop), \
                patch.object(control, 'start') as start, \
                patch.object(control, 'recover_processes') as recover:
            control.main(['restart'])
            start.assert_not_called()
            recover.assert_not_called()

    def test_cancelled_queued_start_does_not_launch(self):
        (self.state / 'cancel-start').touch()
        with patch.dict('sys.modules', {'fcntl': MagicMock()}), \
                patch.object(control.subprocess, 'Popen') as spawn:
            control.start(expected_cancel=0)
            spawn.assert_not_called()

    def test_status_preserves_real_provider_work_and_reports_stale_heartbeat(self):
        control.runtime.write_state('ready',busy=True,updated_at=100)
        with patch.object(control,'running',return_value=True), \
                patch.object(control.runtime,'latest_activity',return_value={'busy':False}), \
                patch.object(control.time,'time',return_value=125):
            data=control.status()
        self.assertTrue(data['busy'])
        self.assertEqual(25,data['heartbeat_age'])

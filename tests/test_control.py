import os
import subprocess
import sys
import unittest
from unittest.mock import patch, Mock
import psutil
from seagreen.control import control_process, inspect_target


class ControlTests(unittest.TestCase):
    def child(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(90)'])
        self.addCleanup(lambda: self.cleanup(child))
        return child, psutil.Process(child.pid).create_time()

    @staticmethod
    def cleanup(child):
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)

    def test_self_ancestors_and_invalid_identity_blocked(self):
        for pid in (os.getpid(), os.getppid()):
            with self.assertRaises(ValueError):
                control_process(pid, psutil.Process(pid).create_time(), 'force')
        for pid, created in ((1, 1), (True, 1), (99, float('nan'))):
            with self.assertRaises(ValueError):
                inspect_target(pid, created)

    def test_stale_identity_never_kills_reused_pid(self):
        child, created = self.child()
        with self.assertRaises(ValueError):
            control_process(child.pid, created + 1, 'force')
        self.assertIsNone(child.poll())

    @unittest.skipIf(os.name == 'nt' or (hasattr(os, 'geteuid') and os.geteuid() == 0), 'SIGTERM is a Unix current-user operation')
    def test_quit_targets_only_selected_child(self):
        child, created = self.child()
        other, _ = self.child()
        control_process(child.pid, created, 'quit')
        child.wait(timeout=5)
        self.assertIsNone(other.poll())

    @unittest.skipIf(hasattr(os, 'geteuid') and os.geteuid() == 0, 'Root processes protected')
    def test_force_quit_and_unknown_mode(self):
        child, created = self.child()
        with self.assertRaises(ValueError):
            control_process(child.pid, created, 'anything')
        self.assertIsNone(child.poll())
        control_process(child.pid, created, 'force')
        child.wait(timeout=5)

    def test_windows_quit_never_uses_forceful_terminate(self):
        proc = Mock()
        with patch('seagreen.control.inspect_target', return_value=proc), patch('seagreen.control.os.name', 'nt'), patch('seagreen.control._windows_close') as close:
            control_process(1234, 1, 'quit')
            close.assert_called_once_with(proc)
            proc.kill.assert_not_called()
            proc.terminate.assert_not_called()

    def test_cli_cancellation_does_not_signal(self):
        from seagreen.__main__ import terminate_prompt
        child, created = self.child()
        with patch('seagreen.__main__.inspect_target', return_value=psutil.Process(child.pid)), patch('seagreen.__main__.sys.stdin.isatty', return_value=True), patch('seagreen.__main__.Confirm.ask', return_value=False), patch('seagreen.__main__.control_process') as control:
            terminate_prompt(child.pid, True)
            control.assert_not_called()
        self.assertIsNone(child.poll())

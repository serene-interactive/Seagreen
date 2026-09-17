import json
import math
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from seagreen.monitor import EnergyIntegrator, Monitor, counter_rate
from seagreen.jobs import JobManager


class MeasurementTests(unittest.TestCase):
    def test_units_and_trapezoid(self):
        energy = EnergyIntegrator()
        for second in range(0, 3601, 2):
            energy.add(second, {'watts': 10, 'key': 'device'})
        self.assertAlmostEqual(energy.wh, 10)
        self.assertAlmostEqual(energy.wh / 1000, .01)
        self.assertEqual(energy.covered_seconds, 3600)
        energy = EnergyIntegrator()
        energy.add(0, {'watts': 10, 'key': 'device'})
        energy.add(10, {'watts': 30, 'key': 'device'})
        self.assertAlmostEqual(energy.wh, 200 / 3600)

    def test_gaps_and_source_changes(self):
        energy = EnergyIntegrator()
        for timestamp, power in [(0, {'watts': 10, 'key': 'A'}), (2, None), (4, {'watts': 10, 'key': 'A'}),
                                 (500, {'watts': 10, 'key': 'A'}), (502, {'watts': 10, 'key': 'B'})]:
            energy.add(timestamp, power)
        self.assertEqual(energy.wh, 0)
        self.assertEqual(energy.covered_seconds, 0)

    def test_invalid_reading_breaks_integration(self):
        energy = EnergyIntegrator()
        for timestamp, value in [(0, 10), (2, float('nan')), (4, 10), (6, -1), (8, 10)]:
            energy.add(timestamp, {'watts': value, 'key': 'A'})
        self.assertEqual(energy.wh, 0)

    def test_counter_resets_and_multicore(self):
        self.assertEqual(counter_rate(1, 5, 2) * 100, 200)
        self.assertIsNone(counter_rate(10, 1, 2))
        self.assertIsNone(counter_rate(1, 2, 0))
        self.assertIsNone(counter_rate(1, 2, 30))

    def test_record_persistence_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = Monitor(Path(directory) / 'records')
            record = monitor.start_recording('Baseline', units=1)
            with self.assertRaises(ValueError):
                monitor.start_recording('duplicate')
            monitor.sample()
            finished = monitor.finish_recording()
            self.assertEqual(finished['id'], record['id'])
            self.assertEqual(len(monitor.recordings()), 1)
            self.assertEqual(len(finished['points']), 1)
            with self.assertRaises(ValueError):
                monitor.delete_recording('../outside')
            with self.assertRaises(ValueError):
                monitor.start_recording('Invalid', units=float('nan'))
            with self.assertRaises(ValueError):
                monitor.start_recording('Invalid', units=True)
            monitor.delete_recording(record['id'])
            self.assertEqual(monitor.recordings(), [])

    def test_live_counter_sampling(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = Monitor(Path(directory) / 'records')
            monitor.sample()
            self.assertIsNone(monitor.latest['cpu'])
            deadline = time.monotonic() + .2
            while time.monotonic() < deadline:
                pass
            monitor.sample()
            own = next(p for p in monitor.latest['processes'] if p['pid'] == os.getpid())
            self.assertGreater(own['cpu'], 10)
            self.assertGreater(own['memory'], 0)
            self.assertGreater(len(monitor.snapshot()['history']), 1)

    def test_only_explicit_job_and_literal_arguments(self):
        jobs = JobManager()
        with self.assertRaises(ValueError):
            jobs.launch('relative/path', [], True)
        marker = '$(echo should-not-run); & literal'
        jobs.launch(sys.executable, ['-c', 'import sys; print(sys.argv[1])', marker], False)
        deadline = time.monotonic() + 5
        while jobs.snapshot()['running'] and time.monotonic() < deadline:
            time.sleep(.02)
        # Drain completes just after process exit.
        for _ in range(100):
            if 'Exited' in jobs.snapshot()['status']:
                break
            time.sleep(.01)
        self.assertIn(marker, jobs.snapshot()['output'])
        self.assertIn('status 0', jobs.snapshot()['status'])

    def test_background_job_stops_only_launched_process(self):
        jobs = JobManager()
        jobs.launch(sys.executable, ['-c', 'import time; time.sleep(20)'], True)
        self.assertTrue(jobs.snapshot()['running'])
        with self.assertRaises(ValueError):
            jobs.launch(sys.executable, [], False)
        jobs.stop()
        jobs.process.wait(timeout=5)
        self.assertFalse(jobs.snapshot()['running'])


if __name__ == '__main__':
    unittest.main()

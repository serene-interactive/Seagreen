"""Local monitoring engine. Resource counters are observed; missing power stays missing."""
import copy
import json
import math
import os
import platform
import threading
import time
import uuid
from collections import deque
from pathlib import Path

import psutil


def counter_rate(previous, current, elapsed):
    if not 0 < elapsed <= 15 or current < previous:
        return None
    return (current - previous) / elapsed


class EnergyIntegrator:
    def __init__(self):
        self.wh = 0.0
        self.covered_seconds = 0.0
        self.previous = None

    def add(self, timestamp, power):
        if not power or not math.isfinite(power['watts']) or power['watts'] < 0:
            self.previous = None
            return
        if self.previous:
            old_time, old = self.previous
            delta = timestamp - old_time
            if 0 < delta <= 15 and old['key'] == power['key']:
                self.wh += (old['watts'] + power['watts']) / 2 * delta / 3600
                self.covered_seconds += delta
        self.previous = timestamp, power


class LinuxPackagePower:
    """Read top-level RAPL packages only, avoiding double-counted subdomains."""
    def __init__(self):
        self.previous = None

    def read(self, now):
        readings = {}
        for path in Path('/sys/class/powercap').glob('intel-rapl:*'):
            if path.name.count(':') != 1:
                continue
            try:
                if not (path / 'name').read_text().strip().startswith('package'):
                    continue
                readings[path.name] = (int((path / 'energy_uj').read_text()), int((path / 'max_energy_range_uj').read_text()))
            except (OSError, ValueError):
                continue
        old = self.previous
        self.previous = now, readings
        if not readings or not old or set(old[1]) != set(readings) or not 0 < now - old[0] <= 15:
            return None
        energy = 0
        for key, (value, maximum) in readings.items():
            before = old[1][key][0]
            # A decreasing counter is ambiguous (wrap or device reset); skip it.
            if maximum <= 0 or not 0 <= before <= value < maximum:
                return None
            energy += value - before
        watts = energy / 1_000_000 / (now - old[0])
        if not math.isfinite(watts) or not 0 <= watts <= 10000:
            return None
        return {'watts': watts, 'key': 'rapl:cpu-packages', 'source': 'Hardware energy counter',
                'scope': 'CPU packages · excludes the rest of the device'}


class Monitor:
    def __init__(self, directory=None, interval=2):
        if directory is None:
            base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) if os.name == 'nt' else Path.home() / '.local' / 'share'
            directory = base / 'Seagreen' / 'recordings'
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.interval = interval
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.previous = {}
        self.previous_time = None
        self.latest = None
        self.history = deque(maxlen=150)
        self.active = None
        self.energy = EnergyIntegrator()
        self.power_reader = LinuxPackagePower()
        self.error = None
        self.thread = None
        self.paused = False
        # Local random ID, not a hardware identifier; used only to prevent cross-machine comparisons.
        identity_file = self.directory.parent / 'device-id'
        if not identity_file.exists():
            try:
                with identity_file.open('x') as stream:
                    stream.write(str(uuid.uuid4()))
            except FileExistsError:
                pass
        self.device_id = identity_file.read_text().strip()

    def start(self):
        self.thread = threading.Thread(target=self._run, name='Seagreen-monitor', daemon=True)
        self.thread.start()

    def _run(self):
        psutil.cpu_percent(None)
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                if not self.paused:
                    self.sample()
            except Exception as error:
                with self.lock:
                    self.error = 'Monitoring interrupted: ' + str(error)
            self.stop_event.wait(max(0.1, self.interval - (time.monotonic() - started)))

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        with self.lock:
            if self.active:
                self.finish_recording()

    def sample(self):
        now = time.monotonic()
        elapsed = now - self.previous_time if self.previous_time is not None else 0
        processes, next_counters = [], {}
        inaccessible = 0
        for proc in psutil.process_iter():
            try:
                with proc.oneshot():
                    created = proc.create_time()
                    key = (proc.pid, created)
                    times = proc.cpu_times()
                    cpu_time = times.user + times.system
                    memory = proc.memory_info().rss
                    name = proc.name()
                    try:
                        io = proc.io_counters()
                        read, write = io.read_bytes, io.write_bytes
                    except (psutil.Error, AttributeError, NotImplementedError):
                        read = write = None
                    before = self.previous.get(key)
                    cpu = counter_rate(before[0], cpu_time, elapsed) if before else None
                    read_rate = counter_rate(before[1], read, elapsed) if before and before[1] is not None and read is not None else None
                    write_rate = counter_rate(before[2], write, elapsed) if before and before[2] is not None and write is not None else None
                    next_counters[key] = (cpu_time, read, write)
                    processes.append({'pid': proc.pid, 'created': created, 'name': name,
                                      'cpu': cpu * 100 if cpu is not None else None,
                                      'memory': memory, 'readRate': read_rate, 'writeRate': write_rate})
            except (psutil.Error, OSError):
                inaccessible += 1
        self.previous, self.previous_time = next_counters, now
        memory = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        cpu = psutil.cpu_percent(None) if 0 < elapsed <= 15 else None
        power = self.power_reader.read(now) if platform.system() == 'Linux' else None
        timestamp = time.time()
        point = {'date': timestamp, 'cpu': cpu, 'memoryGB': (memory.total - memory.available) / 1024**3,
                 'watts': power['watts'] if power else None, 'powerKey': power['key'] if power else None}
        sample = {'date': timestamp, 'cpu': cpu, 'memory': memory.total - memory.available,
                  'memoryTotal': memory.total, 'power': power,
                  'battery': {'percent': battery.percent, 'pluggedIn': battery.power_plugged} if battery else None,
                  'processes': sorted(processes, key=lambda p: p['cpu'] if p['cpu'] is not None else -1, reverse=True),
                  'inaccessible': inaccessible, 'platform': platform.system(), 'cores': psutil.cpu_count(),
                  'collectionMS': (time.monotonic() - now) * 1000}
        with self.lock:
            self.latest = sample
            self.history.append(point)
            self.error = None
            if self.active:
                self.energy.add(now, power)
                self.active['points'].append(point)
                self.active['ended'] = timestamp
                self.active['energyWh'] = self.energy.wh
                self.active['coveredSeconds'] = self.energy.covered_seconds
                if power and power['key'] not in self.active['powerKeys']:
                    self.active['powerKeys'].append(power['key'])
                if len(self.active['points']) % 15 == 0:
                    self._save(self.active)
                if timestamp - self.active['started'] >= 7200:
                    self.finish_recording()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({'sample': self.latest, 'history': list(self.history), 'active': self.active,
                                  'paused': self.paused, 'error': self.error})

    def start_recording(self, title, notes='', units=1, unit_name='task'):
        if not isinstance(title, str) or len(title) > 200 or not isinstance(notes, str) or len(notes) > 4000:
            raise ValueError('Use a name under 200 characters and notes under 4000 characters.')
        if not isinstance(unit_name, str) or not 1 <= len(unit_name) <= 50:
            raise ValueError('Enter a short unit name.')
        if isinstance(units, bool) or not isinstance(units, (int, float)) or not math.isfinite(units) or units <= 0:
            raise ValueError('Completed work must be a positive number.')
        with self.lock:
            if self.active:
                raise ValueError('A recording is already running.')
            self.paused = False
            self.energy = EnergyIntegrator()
            self.active = {'id': str(uuid.uuid4()), 'title': title.strip() or 'Untitled session', 'notes': notes,
                           'started': time.time(), 'ended': time.time(), 'points': [], 'energyWh': 0,
                           'coveredSeconds': 0, 'powerKeys': [], 'device': self.device_id,
                           'completedUnits': units, 'unitName': unit_name, 'version': 3}
            self._save(self.active)
            return copy.deepcopy(self.active)

    def _save(self, recording):
        path = self.directory / (recording['id'] + '.json')
        temp = path.with_suffix('.tmp')
        try:
            descriptor = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(recording, stream, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        except OSError as error:
            self.error = 'Recording could not be saved: ' + str(error)
            raise

    def finish_recording(self):
        with self.lock:
            if not self.active:
                raise ValueError('No recording is running.')
            self.active['ended'] = time.time()
            self._save(self.active)
            result = self.active
            self.active = None
            return result

    def recordings(self):
        with self.lock:
            result = []
            for path in self.directory.glob('*.json'):
                try:
                    if path.stat().st_size > 10_000_000:
                        continue
                    record = json.loads(path.read_text(encoding='utf-8'))
                    if not self.active or record['id'] != self.active['id']:
                        result.append(record)
                except (OSError, ValueError, KeyError):
                    continue
            return sorted(result, key=lambda record: record['started'], reverse=True)

    def delete_recording(self, identifier):
        identifier = str(uuid.UUID(identifier))
        with self.lock:
            if self.active and self.active['id'] == identifier:
                raise ValueError('Finish this recording first.')
            (self.directory / (identifier + '.json')).unlink()

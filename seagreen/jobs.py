"""Explicitly launched jobs only. No API for killing or throttling unrelated processes."""
import os
import platform
import subprocess
import threading
from pathlib import Path


def enable_windows_ecoqos(process):
    import ctypes
    from ctypes import wintypes
    class PowerThrottling(ctypes.Structure):
        _fields_ = [('Version', wintypes.ULONG), ('ControlMask', wintypes.ULONG), ('StateMask', wintypes.ULONG)]
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    api.SetProcessInformation.restype = wintypes.BOOL
    state = PowerThrottling(1, 1, 1)
    if not api.SetProcessInformation(wintypes.HANDLE(int(process._handle)), 4, ctypes.byref(state), ctypes.sizeof(state)):
        raise ctypes.WinError(ctypes.get_last_error())


class JobManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.process = None
        self.output = ''
        self.name = None
        self.status = 'No job running'
        self.policy = None

    def snapshot(self):
        with self.lock:
            return {'running': self.process is not None and self.process.poll() is None,
                    'name': self.name, 'status': self.status, 'output': self.output, 'policy': self.policy}

    def launch(self, executable, arguments, efficient):
        if not isinstance(executable, str) or not Path(executable).is_absolute():
            raise ValueError('Enter the absolute path to an executable.')
        if not isinstance(arguments, list) or len(arguments) > 100 or not all(isinstance(a, str) and len(a) < 4096 and '\x00' not in a for a in arguments):
            raise ValueError('Arguments must be a list of strings.')
        if not isinstance(efficient, bool):
            raise ValueError('Invalid scheduling selection.')
        if not Path(executable).is_file() or not os.access(executable, os.X_OK):
            raise ValueError('This executable does not exist or cannot be run.')
        # Windows batch files may invoke a shell even with shell=False. Require an executable/interpreter.
        if os.name == 'nt' and Path(executable).suffix.lower() in ('.bat', '.cmd'):
            raise ValueError('Choose an .exe interpreter rather than a batch file.')
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ValueError('A launched job is already running.')
            command = [executable] + arguments
            options = {}
            policy = 'Standard scheduling'
            if efficient and platform.system() == 'Darwin':
                command = ['/usr/sbin/taskpolicy', '-b'] + command
                policy = 'macOS background policy requested'
            elif efficient and os.name == 'nt':
                options['creationflags'] = subprocess.BELOW_NORMAL_PRIORITY_CLASS
                policy = 'Below-normal priority'
            elif efficient:
                command = ['/usr/bin/nice', '-n', '10'] + command
                policy = 'Lower scheduling priority requested'
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, shell=False, **options)
            if efficient and os.name == 'nt':
                try:
                    enable_windows_ecoqos(process)
                    policy += ' + EcoQoS applied'
                except (OSError, AttributeError) as error:
                    policy += ' · EcoQoS unavailable: ' + str(error)
            self.process = process
            self.name = Path(executable).name
            self.output = ''
            self.policy = policy
            self.status = 'Running · PID ' + str(process.pid)
            threading.Thread(target=self._drain, args=(process,), daemon=True).start()
            return self.snapshot()

    def _drain(self, process):
        import codecs
        decoder = codecs.getincrementaldecoder('utf-8')('replace')
        while True:
            data = process.stdout.read1(4096)
            if not data:
                break
            with self.lock:
                if self.process is process:
                    self.output = (self.output + decoder.decode(data))[-32768:]
        code = process.wait()
        process.stdout.close()
        with self.lock:
            if self.process is process:
                self.output = (self.output + decoder.decode(b'', final=True))[-32768:]
                self.status = 'Exited with status ' + str(code)

    def stop(self):
        with self.lock:
            if not self.process or self.process.poll() is not None:
                raise ValueError('No launched job is running.')
            self.process.terminate()
            self.status = 'Termination requested for the launched process'

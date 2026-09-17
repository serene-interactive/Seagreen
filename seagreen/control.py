"""Explicit, current-user process controls shared by the CLI and local dashboard."""
import math
import os
import sys
import psutil

PROTECTED = {'launchd', 'kernel_task', 'windowserver', 'loginwindow', 'system',
             'system idle process', 'registry', 'smss.exe', 'csrss.exe', 'wininit.exe',
             'winlogon.exe', 'services.exe', 'lsass.exe', 'svchost.exe', 'dwm.exe',
             'fontdrvhost.exe', 'sihost.exe', 'logind', 'systemd', 'seagreen'}


def inspect_target(pid, created):
    if type(pid) is not int or pid <= 1 or isinstance(created, bool) or not isinstance(created, (int, float)) or not math.isfinite(created):
        raise ValueError('Select a valid process from a fresh process list.')
    try:
        current = psutil.Process()
        protected_pids = {current.pid, *(p.pid for p in current.parents())}
        proc = psutil.Process(pid)
        if proc.create_time() != created or not proc.is_running():
            raise ValueError('This process has exited or changed. Refresh the process list.')
        if pid in protected_pids or proc.name().lower() in PROTECTED:
            raise ValueError('Seagreen and critical system/session processes are protected.')
        if os.name == 'nt':
            same_user = proc.username().casefold() == current.username().casefold()
        else:
            same_user = os.geteuid() != 0 and proc.uids().real == os.getuid() and proc.uids().effective == os.geteuid()
        if not same_user:
            raise ValueError('Only processes owned by your signed-in user can be controlled.')
        return proc
    except psutil.Error as error:
        raise ValueError('Process unavailable or permission denied. Refresh the process list.') from error


def _windows_close(proc):
    # SIGTERM/psutil.terminate on Windows is forceful. WM_CLOSE lets GUI apps save or cancel.
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    sent = []
    @callback_type
    def close_window(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == proc.pid:
            try:
                if proc.is_running():
                    sent.append(bool(user32.PostMessageW(hwnd, 0x0010, 0, 0)))
            except psutil.Error:
                pass
        return True
    user32.EnumWindows(close_window, 0)
    if not sent or not any(sent):
        raise ValueError('No closeable app window was found. Use the app’s own exit command, or explicitly choose Force quit.')


def control_process(pid, created, mode):
    if mode not in ('quit', 'force'):
        raise ValueError('Choose quit or force.')
    proc = inspect_target(pid, created)
    try:
        if mode == 'force':
            proc.kill()
            message = 'Force-quit request sent. The process list will update shortly.'
        elif os.name == 'nt':
            _windows_close(proc)
            message = 'Close requested. The app may ask you to save work or cancel.'
        else:
            proc.terminate()
            message = 'Termination requested (SIGTERM). The process may handle or ignore it.'
        return {'ok': True, 'message': message}
    except psutil.Error as error:
        raise ValueError('Process exited or permission was denied. Refresh the process list.') from error

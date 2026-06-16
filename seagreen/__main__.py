#!/usr/bin/env python3
"""
🌊 Seagreen - Live Process Energy Monitoring
Real-time energy & carbon tracking for any process
by Serene Interactive, Global

Commands:
  /list             - Show trackable processes
  /track <pid> [seconds]  - Monitor a process (legacy mode)
  /agent-track <pid> [seconds] - Monitor agent with real-time energy TUI
  /agents           - Detect and list agent processes
  /agent-monitor    - Live dashboard for all running agents
  /green <pid>      - Put a process in low-power green mode
  /ungreen <pid>    - Restore a process from green mode
  /green-list       - Show processes currently in green mode
  /kill <pid>       - Terminate a process
  /web or /gui      - Start and launch the Seagreen Web GUI Dashboard
  /help             - Show all commands
  /quit             - Exit Seagreen
"""

import sys
import time
import math
import random
import os
import webbrowser
import psutil
from typing import Optional, List, Dict

# Force UTF-8 so Unicode renders on Windows legacy terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.live import Live
from rich import box
from .tracker import SeagreenEnergyTracker, AgentEnergyReport, is_android

# Colors matching sereneinteractive.com
COLORS = {
    'primary': '#3d8b6f',
    'secondary': '#4a9b6e',
    'accent': '#5ab88a',
    'dark': '#1a2e28',
    'ocean': '#2d6b5d',
    'leaf': '#6bc99a',
    'success': '#2ecc71',
    'warning': '#f1c40f',
    'error': '#e74c3c',
    'info': '#3498db',
}

console = Console()

# Green mode tracking: pid -> {orig_nice, orig_affinity, orig_name}
green_processes: Dict[int, dict] = {}

# Cache for process display names: pid -> (name, start_time)
_display_name_cache: Dict[int, tuple] = {}


def _get_window_title(pid: int) -> Optional[str]:
    """Get the window title for a process (Windows only)."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        result = []

        def enum_callback(hwnd, _):
            lpdw_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
            if lpdw_pid.value == pid:
                length = user32.GetWindowTextLengthW(hwnd) + 1
                if length > 1:
                    buf = ctypes.create_unicode_buffer(length)
                    user32.GetWindowTextW(hwnd, buf, length)
                    title = buf.value.strip()
                    if title and len(title) > 2:
                        result.append(title)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
        return result[0] if result else None
    except Exception:
        return None


def get_process_display_name(pid: int) -> str:
    """Get a human-readable application name for a process.
    Tries: window title -> executable description -> script name -> process name
    """
    # Validate cache: check if PID still refers to the same process
    if pid in _display_name_cache:
        cached_name, cached_time = _display_name_cache[pid]
        try:
            proc = psutil.Process(pid)
            if proc.create_time() == cached_time:
                return cached_name
            else:
                del _display_name_cache[pid]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            del _display_name_cache[pid]

    try:
        proc = psutil.Process(pid)
        name = proc.name()
        try:
            cmdline = proc.cmdline() or []
        except (psutil.AccessDenied, psutil.ZombieProcess):
            cmdline = []
        try:
            create_time = proc.create_time()
        except (psutil.AccessDenied, psutil.ZombieProcess):
            create_time = 0
    except psutil.NoSuchProcess:
        return "?"

    # For Python: show the script / module name
    full_cmd = ' '.join(cmdline)
    if 'python' in name.lower() or 'python' in full_cmd.lower():
        for i, arg in enumerate(cmdline):
            if arg == '-m' and i + 1 < len(cmdline):
                _display_name_cache[pid] = (f"Python: {cmdline[i+1]}", create_time)
                return f"Python: {cmdline[i+1]}"
        if '-c' in cmdline:
            _display_name_cache[pid] = ("Python (interpreter)", create_time)
            return "Python (interpreter)"
        for arg in cmdline:
            if arg.endswith('.py') and os.path.exists(arg):
                script = os.path.basename(arg)
                _display_name_cache[pid] = (f"Python: {script}", create_time)
                return f"Python: {script}"
        _display_name_cache[pid] = ("Python", create_time)
        return "Python"

    # For Node: show the script name
    if 'node' in name.lower():
        for arg in cmdline[1:]:
            if arg.endswith('.js') or arg.endswith('.mjs'):
                script = os.path.basename(arg)
                _display_name_cache[pid] = (f"Node: {script}", create_time)
                return f"Node: {script}"

    # Try window title first (most user-friendly for GUI apps)
    win_title = _get_window_title(pid)
    if win_title:
        _display_name_cache[pid] = (win_title, create_time)
        return win_title

    # Try executable description from version info (Windows)
    try:
        exe_path = proc.exe()
        if os.path.exists(exe_path):
            import ctypes
            ctypes.windll.version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
            ctypes.windll.version.GetFileVersionInfoSizeW.restype = ctypes.c_int
            ctypes.windll.version.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
            ctypes.windll.version.GetFileVersionInfoW.restype = ctypes.c_int
            ctypes.windll.version.VerQueryValueW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint)]
            ctypes.windll.version.VerQueryValueW.restype = ctypes.c_int

            size = ctypes.windll.version.GetFileVersionInfoSizeW(exe_path, None)
            if size > 0:
                buf = ctypes.create_string_buffer(size)
                if ctypes.windll.version.GetFileVersionInfoW(exe_path, 0, size, buf):
                    ptr = ctypes.c_void_p()
                    length = ctypes.c_uint()
                    for sub in (r"\StringFileInfo\040904b0\FileDescription",
                                r"\StringFileInfo\040904E4\FileDescription"):
                        if ctypes.windll.version.VerQueryValueW(buf, sub, ctypes.byref(ptr), ctypes.byref(length)):
                            desc = ctypes.cast(ptr, ctypes.c_wchar_p).value
                            if desc:
                                _display_name_cache[pid] = (desc, create_time)
                                return desc
    except Exception:
        pass

    # Fallback: process executable name
    _display_name_cache[pid] = (name, create_time)
    return name


BANNER_ART = [
    " ███████╗███████╗ █████╗  ██████╗ ██████╗ ███████╗███████╗███╗   ██╗",
    " ██╔════╝██╔════╝██╔══██╗██╔════╝ ██╔══██╗██╔════╝██╔════╝████╗  ██║",
    " ███████╗█████╗  ███████║██║  ███╗██████╔╝█████╗  █████╗  ██╔██╗ ██║",
    " ╚════██║██╔══╝  ██╔══██║██║   ██║██╔══██╗██╔══╝  ██╔══╝  ██║╚██╗██║",
    " ███████║███████╗██║  ██║╚██████╔╝██║  ██║███████╗███████╗██║ ╚████║",
    " ╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝",
]

WAVE_CHARS = ["~", "≈", "~", "∽", "≈", "~", "∿", "≈"]
LEAF_CHARS = ["🌿", "🍃", "╲", "╱", "·"]

WAVE_WIDTH = 70
WAVE_ROWS = 3
LEAF_FIELD_ROWS = 4
ANIM_DURATION = 3.0
ANIM_FPS = 8


def _generate_wave_line(tick: int, row: int, width: int) -> str:
    """Generate a single animated wave line."""
    line = []
    for col in range(width):
        phase = (col * 0.3) + (tick * 0.6) + (row * 1.2)
        idx = int((math.sin(phase) + 1) * 3.5) % len(WAVE_CHARS)
        line.append(WAVE_CHARS[idx])
    return "".join(line)


def _generate_leaf_line(tick: int, row: int, width: int, seed: int) -> str:
    """Generate a line with sparse drifting leaves."""
    rng = random.Random(seed + tick * 7 + row * 31)
    line = list(" " * width)
    num_leaves = rng.randint(1, 3)
    for _ in range(num_leaves):
        col = (rng.randint(0, width - 2) + tick * 2 + row) % (width - 1)
        char = rng.choice(LEAF_CHARS)
        line[col] = char
    return "".join(line)


def _build_frame(tick: int) -> str:
    """Build one full animation frame as a Rich-markup string."""
    lines = []

    for row in range(LEAF_FIELD_ROWS):
        leaf_line = _generate_leaf_line(tick, row, WAVE_WIDTH, seed=42)
        lines.append(f"[{COLORS['leaf']}]{leaf_line}[/{COLORS['leaf']}]")

    for art_line in BANNER_ART:
        lines.append(f"[bold {COLORS['primary']}]{art_line}[/bold {COLORS['primary']}]")

    for row in range(WAVE_ROWS):
        wave_line = _generate_wave_line(tick, row, WAVE_WIDTH)
        lines.append(f"[{COLORS['ocean']}]{wave_line}[/{COLORS['ocean']}]")

    lines.append("")
    lines.append(f"[bold {COLORS['leaf']}]🌊  Seagreen - Live Process Energy Monitor  🌿[/bold {COLORS['leaf']}]")
    lines.append(f"[dim {COLORS['secondary']}]by Serene Interactive, Global[/dim {COLORS['secondary']}]")
    lines.append("")
    lines.append(f"[dim {COLORS['ocean']}]Type /help for commands[/dim {COLORS['ocean']}]")

    centered = "\n".join(lines)
    return centered


def print_banner():
    """Animated startup banner with ocean waves and drifting leaves."""
    total_frames = int(ANIM_DURATION * ANIM_FPS)
    frame_delay = 1.0 / ANIM_FPS

    console.print()
    try:
        with Live(
            Align.center(Text.from_markup(_build_frame(0))),
            console=console,
            refresh_per_second=ANIM_FPS,
            transient=True,
        ) as live:
            for tick in range(total_frames):
                live.update(Align.center(Text.from_markup(_build_frame(tick))))
                time.sleep(frame_delay)
    except KeyboardInterrupt:
        pass

    console.print(Align.center(Text.from_markup(_build_frame(total_frames))))
    console.print()


# Agent detection patterns
AGENT_PATTERNS = {
    'hermes': ['hermes', 'hermes-agent'],
    'openclaw': ['openclaw', 'openclaw gateway', 'openclaw-agent'],
    'langchain': ['langchain'],
    'crewai': ['crewai'],
    'autogen': ['autogen'],
}


def list_python_processes(filter_text: str = ""):
    """Show all trackable processes, optionally filtered by name/cmdline"""
    if is_android():
        console.print(f"[bold {COLORS['warning']}]Running in sandboxed Android environment. System-wide process monitoring is disabled unless running with root. Displaying Termux-only processes.[/bold {COLORS['warning']}]")
    processes = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            name = proc.info['name']

            # Skip kernel processes and Seagreen itself
            if pid := proc.info['pid']:
                if pid == psutil.Process().pid:
                    continue
                if name in ['System', 'Registry', 'smss.exe']:  # Windows
                    continue

            # Check if it's an agent or common dev process
            is_agent = any(
                pattern in (name.lower() + ' ' + cmdline.lower())
                for patterns in AGENT_PATTERNS.values()
                for pattern in patterns
            )

            is_dev_process = (
                'python' in name.lower() or
                'node' in name.lower() or
                'java' in name.lower() or
                'dotnet' in name.lower() or
                'go' in name.lower() or
                'rust' in name.lower() or
                'docker' in name.lower()
            )

            if is_agent or is_dev_process:
                # Apply filter if provided
                if filter_text:
                    full_text = (name + ' ' + cmdline).lower()
                    if filter_text.lower() not in full_text:
                        continue

                app_name = get_process_display_name(proc.info['pid'])
                processes.append({
                    'pid': proc.info['pid'],
                    'name': name,
                    'app_name': app_name,
                    'cmdline': cmdline[:60] + '...' if len(cmdline) > 60 else cmdline,
                    'is_agent': is_agent
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not processes:
        msg = f"No trackable processes found matching '{filter_text}'." if filter_text else "No trackable processes found."
        console.print(f"[bold {COLORS['secondary']}]{msg}[/bold {COLORS['secondary']}]")
        return

    table = Table(
        show_header=True,
        header_style=f"bold {COLORS['dark']}",
        border_style=COLORS['accent'],
        box=box.SIMPLE
    )
    table.add_column("PID", style=f"bold {COLORS['primary']}", width=8)
    table.add_column("Application", style=COLORS['dark'], width=28)
    table.add_column("Type", style=COLORS['leaf'], width=7)
    table.add_column("Command", style=COLORS['secondary'], width=40)

    for proc in processes[:40]:
        proc_type = "AGENT" if proc['is_agent'] else "DEV"
        table.add_row(
            str(proc['pid']),
            proc['app_name'],
            proc_type,
            proc['cmdline']
        )

    console.print(table)
    if filter_text:
        console.print(f"\n[dim]Filtered by: {filter_text}[/dim]")
    console.print(f"[dim]Use: /agent-track <pid> for real-time agent monitoring[/dim]\n")


def detect_agents():
    """Detect and list known agent processes"""
    agents = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            name = proc.info['name'].lower()
            cmdline = ' '.join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ''
            full_text = name + ' ' + cmdline
            
            detected_agents = []
            for agent_type, patterns in AGENT_PATTERNS.items():
                if any(pattern in full_text for pattern in patterns):
                    detected_agents.append(agent_type)
            
            if detected_agents:
                uptime = time.time() - proc.info['create_time']
                hours, remainder = divmod(uptime, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                app_name = get_process_display_name(proc.info['pid'])

                agents.append({
                    'pid': proc.info['pid'],
                    'name': app_name or proc.info['name'],
                    'types': detected_agents,
                    'uptime': uptime_str,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not agents:
        console.print(f"[bold {COLORS['secondary']}]No agent processes detected.[/bold {COLORS['secondary']}]")
        console.print(f"[dim]Known agent types: {', '.join(AGENT_PATTERNS.keys())}[/dim]")
        return

    table = Table(
        show_header=True,
        header_style=f"bold {COLORS['dark']}",
        border_style=COLORS['accent'],
        box=box.SIMPLE
    )
    table.add_column("PID", style=f"bold {COLORS['primary']}", width=8)
    table.add_column("Application", style=COLORS['dark'], width=24)
    table.add_column("Type", style=COLORS['leaf'], width=15)
    table.add_column("Uptime", style=COLORS['secondary'], width=10)
    
    for agent in agents:
        types_str = ', '.join(agent['types'])
        table.add_row(
            str(agent['pid']),
            agent['name'],
            types_str,
            agent['uptime'],
        )

    console.print(table)
    console.print(f"\n[dim]Use: /agent-track <pid> to monitor a specific agent[/dim]\n")


def track_agent_pid(pid: Optional[int] = None, duration: Optional[float] = None):
    """Monitor a specific PID with real-time energy TUI"""
    if pid is None:
        pid = pick_process("Select an agent to monitor", agent_only=False)
        if pid is None:
            return

    try:
        tracker = SeagreenEnergyTracker(pid)
    except psutil.NoSuchProcess:
        console.print(f"[bold red]Process {pid} not found. Use /agents to see detected agents.[/bold red]")
        return
    except psutil.AccessDenied:
        console.print(f"[bold red]Permission denied for process {pid}. Try a process you own.[/bold red]")
        return
    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        return
    
    console.print(f"\n[bold {COLORS['primary']}]Starting real-time energy monitoring for PID {pid}...[/bold {COLORS['primary']}]")
    console.print(f"[dim]Press Ctrl+C to stop early[/dim]\n")
    
    # Start monitoring
    tracker.start_monitoring()
    
    # Real-time TUI
    start_time = time.time()
    try:
        with Live(
            console=console,
            refresh_per_second=2,
            transient=True,
        ) as live:
            while duration is None or (time.time() - start_time) < duration:
                # Take snapshot
                tracker.take_snapshot()
                
                # Generate report
                report = tracker.generate_report()
                
                # Create display
                display = create_agent_display(report)
                live.update(Panel(display, title="[bold]~~ Seagreen Process Energy Monitor[/bold]", border_style=COLORS['primary']))
                
                time.sleep(0.5)  # Update twice per second
    except KeyboardInterrupt:
        console.print(f"\n[bold {COLORS['secondary']}]Monitoring stopped.[/bold {COLORS['secondary']}]")
    
    # Final report
    try:
        final_report = tracker.generate_report()
        print_agent_report(final_report)
    except Exception as e:
        console.print(f"[bold red]Error generating final report: {e}[/bold red]")


def agent_monitor_dashboard():
    """Live dashboard for all running agents"""
    console.print(f"\n[bold {COLORS['primary']}]Starting live agent dashboard...[/bold {COLORS['primary']}]")
    console.print(f"[dim]Press Ctrl+C to exit[/dim]\n")
    
    try:
        with Live(
            console=console,
            refresh_per_second=2,
            transient=True,
        ) as live:
            while True:
                # Get current agents
                agents = []
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        name = proc.info['name'].lower()
                        cmdline = ' '.join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ''
                        full_text = name + ' ' + cmdline
                        
                        agent_types = []
                        for agent_type, patterns in AGENT_PATTERNS.items():
                            if any(pattern in full_text for pattern in patterns):
                                agent_types.append(agent_type)
                        
                        if agent_types:
                            agents.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'types': agent_types
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                if not agents:
                    live.update(Panel(
                        "[yellow]No agent processes detected[/yellow]\n\n"
                        f"[dim]Known agent types: {', '.join(AGENT_PATTERNS.keys())}[/dim]",
                        title="[bold]~~ Seagreen Process Dashboard[/bold]",
                        border_style=COLORS['warning']
                    ))
                else:
                    # Create multi-agent display
                    display = create_multiagent_display(agents)
                    live.update(Panel(display, title="[bold]~~ Seagreen Process Dashboard[/bold]", border_style=COLORS['primary']))
                
                time.sleep(1)  # Update once per second
    except KeyboardInterrupt:
        console.print(f"\n[bold {COLORS['secondary']}]Dashboard exited.[/bold {COLORS['secondary']}]")


def create_agent_display(report: AgentEnergyReport) -> str:
    """Create the real-time agent energy display"""
    lines = []
    
    # Header
    app_name = get_process_display_name(report.pid)
    runtime_str = f"{report.runtime} ({' '.join(report.agent_types)})" if report.agent_types else report.runtime
    lines.append(f"App:        {app_name}")
    lines.append(f"Runtime:    {runtime_str}")
    lines.append(f"PID:        {report.pid}")
    lines.append(f"Uptime:     {report.uptime_str}")
    lines.append("")
    
    # Current stats
    lines.append(f"Current:    {report.current_watts:.1f}W")
    lines.append(f"Session:    {report.session_kwh:.3f} kWh")
    lines.append(f"CO2 est:    {report.session_co2_g:.1f}g")
    lines.append(f"Grid:       {report.grid_region} -- {report.grid_intensity:.0f}g CO2/kWh")
    lines.append("")
    
    # Green Score with visual bar
    score = report.green_score
    filled = int(score / 10)  # 10 blocks for 0-100 score
    empty = 10 - filled
    bar = "#" * filled + "." * empty
    score_color = COLORS['success'] if score >= 80 else COLORS['warning'] if score >= 60 else COLORS['error']
    lines.append(f"Green Score: [{score_color}]{bar}[/{score_color}]  {score}/100")
    lines.append("")
    
    # Breakdown
    lines.append("Breakdown:")
    if report.component_breakdown:
        for component, percentage in report.component_breakdown.items():
            bar_length = int(percentage / 5)  # Scale to 20 chars max
            bar = "#" * bar_length + "." * (20 - bar_length)
            lines.append(f"    {component:<18} {bar}  {percentage:>3}%")
    else:
        lines.append("    Component breakdown not available")
    lines.append("")
    
    # Top consumers
    lines.append("Top consumers:")
    if report.top_consumers:
        for i, (name, watts) in enumerate(report.top_consumers[:3], 1):
            lines.append(f"    {i}. {name:<20} {watts:>4.1f}W")
    else:
        lines.append("    No consumer data available")
    
    return "\n".join(lines)


def create_multiagent_display(agents: list) -> str:
    """Create multi-agent dashboard display"""
    if not agents:
        return "[yellow]No agent processes detected[/yellow]"
    
    lines = []
    total_power = 0.0
    total_energy = 0.0
    total_co2 = 0.0
    
    for agent in agents[:10]:  # Show max 10 agents
        try:
            tracker = SeagreenEnergyTracker(agent['pid'])
            tracker.start_monitoring()
            tracker.take_snapshot()  # Get current reading
            report = tracker.generate_report()
            
            agent_name = f"{report.runtime} ({'/'.join(report.agent_types)})" if report.agent_types else report.runtime
            lines.append(f"Agent: {agent_name} (PID {report.pid})")
            lines.append(f"    CPU: {report.avg_cpu:.1f}% | RAM: {report.avg_memory_mb:.0f} MB | Power: {report.current_watts:.1f}W")
            lines.append(f"    Session energy: {report.session_kwh:.3f} kWh | Carbon: {report.session_co2_g:.0f}g CO2")
            lines.append("")
            
            total_power += report.current_watts
            total_energy += report.session_kwh
            total_co2 += report.session_co2_g
        except Exception:
            # Skip if we can't read the process
            continue
    
    lines.append(f"Total: {total_power:.1f}W | {total_energy:.3f} kWh | {total_co2:.0f}g CO2")
    lines.append(f"   Trend: -- vs yesterday")  # Placeholder for historical comparison
    
    return "\n".join(lines)


def print_agent_report(report: AgentEnergyReport):
    """Print detailed agent energy report"""
    console.print("\n")
    
    # Header
    title = f"Seagreen Process Energy Report"
    if report.agent_types:
        title += f" ({'/'.join(report.agent_types)})"
    console.print(f"[bold {COLORS['primary']}]{title}[/bold {COLORS['primary']}]")
    console.print("=" * 50)
    
    # Basic info
    table = Table(show_header=False, border_style=COLORS['accent'], box=box.SIMPLE)
    table.add_column("Metric", style=f"bold {COLORS['secondary']}")
    table.add_column("Value", style=COLORS['primary'])
    
    table.add_row("Process", get_process_display_name(report.pid))
    table.add_row("PID", str(report.pid))
    table.add_row("Runtime", report.runtime)
    if report.agent_types:
        table.add_row("Agent Types", ", ".join(report.agent_types))
    table.add_row("Duration", f"{report.duration_seconds:.1f}s")
    table.add_row("Uptime", report.uptime_str)
    
    console.print(table)
    
    # Energy stats
    energy_table = Table(show_header=False, border_style=COLORS['accent'], box=box.SIMPLE)
    energy_table.add_column("Metric", style=f"bold {COLORS['secondary']}")
    energy_table.add_column("Value", style=COLORS['primary'])
    
    energy_table.add_row("Current Power", f"{report.current_watts:.2f} W")
    energy_table.add_row("Session Energy", f"{report.session_kwh:.3f} kWh")
    energy_table.add_row("Carbon Estimate", f"{report.session_co2_g:.1f} g CO2")
    energy_table.add_row("Grid Intensity", f"{report.grid_intensity:.0f} g CO2/kWh ({report.grid_region})")
    energy_table.add_row("CPU Seconds", f"{report.cpu_seconds:.2f}")
    
    console.print(f"\n[bold {COLORS['primary']}]Energy Consumption:[/bold {COLORS['primary']}]")
    console.print(energy_table)
    
    # Efficiency stats
    eff_table = Table(show_header=False, border_style=COLORS['accent'], box=box.SIMPLE)
    eff_table.add_column("Metric", style=f"bold {COLORS['secondary']}")
    eff_table.add_column("Value", style=COLORS['primary'])
    
    eff_table.add_row("Average CPU", f"{report.avg_cpu:.1f}%")
    eff_table.add_row("Peak CPU", f"{report.peak_cpu:.1f}%")
    eff_table.add_row("Average Memory", f"{report.avg_memory_mb:.1f} MB")
    eff_table.add_row("Peak Memory", f"{report.peak_memory_mb:.1f} MB")
    eff_table.add_row("Green Score", f"{report.green_score}/100")
    eff_table.add_row("Rating", report.seagreen_rating)
    
    console.print(f"\n[bold {COLORS['primary']}]Efficiency Metrics:[/bold {COLORS['primary']}]")
    console.print(eff_table)

    # Breakdown
    if report.component_breakdown:
        console.print(f"\n[bold {COLORS['primary']}]Energy Breakdown:[/bold {COLORS['primary']}]")
        breakdown_table = Table(show_header=False, border_style=COLORS['accent'], box=box.SIMPLE)
        breakdown_table.add_column("Component", style=COLORS['secondary'])
        breakdown_table.add_column("Percentage", style=COLORS['primary'])
        breakdown_table.add_column("Visual", style=COLORS['info'])
        
        for component, percentage in report.component_breakdown.items():
            bar_length = int(percentage / 5)  # Scale to 20 chars
            bar = "#" * bar_length + "." * (20 - bar_length)
            breakdown_table.add_row(component, f"{percentage}%", bar)
        
        console.print(breakdown_table)
    
    # Top consumers
    if report.top_consumers:
        console.print(f"\n[bold {COLORS['primary']}]Top Energy Consumers:[/bold {COLORS['primary']}]")
        consumer_table = Table(show_header=False, border_style=COLORS['accent'], box=box.SIMPLE)
        consumer_table.add_column("#", style=COLORS['secondary'], width=3)
        consumer_table.add_column("Process", style=COLORS['primary'])
        consumer_table.add_column("Power (W)", style=COLORS['primary'], justify="right")
        
        for i, (name, watts) in enumerate(report.top_consumers, 1):
            consumer_table.add_row(str(i), name, f"{watts:.1f}")
        
        console.print(consumer_table)
    
    # Relatable equivalents
    console.print(f"\n[bold {COLORS['primary']}]Relatable Equivalents:[/bold {COLORS['primary']}]")
    equiv_table = Table(show_header=False, border_style=COLORS['accent'], box=box.SIMPLE)
    equiv_table.add_column("Equivalent", style=COLORS['secondary'])
    equiv_table.add_column("Amount", style=COLORS['primary'])
    
    equiv_table.add_row("Smartphone charges", f"{report.session_kwh * 100:.0f}")
    equiv_table.add_row("Google searches", f"{report.session_kwh / 0.0003:.0f}")
    equiv_table.add_row("Streaming minutes", f"{report.session_kwh / 0.00036:.0f}")
    equiv_table.add_row("Driving miles", f"{report.session_co2_g / 404:.2f}")
    equiv_table.add_row("Tree absorption days", f"{report.session_co2_g / 21.77:.1f}")
    
    console.print(equiv_table)
    console.print()


def print_help():
    """Show available commands"""
    help_text = f"""
[bold {COLORS['primary']}]Seagreen Commands:[/bold {COLORS['primary']}]

  [bold]/list [filter][/bold]          - Show trackable processes (optional name filter)
  [bold]/track [pid] [time][/bold]  - Monitor a process (or pick interactively)
  [bold]/agent-track [pid] [time][/bold] - Monitor agent with real-time energy TUI (or pick)
  [bold]/agents[/bold]              - Detect and list agent processes
  [bold]/agent-monitor[/bold]       - Live dashboard for all running agents
  [bold]/green [pid][/bold]         - Put process in low-power green mode (or pick)
  [bold]/ungreen <pid>[/bold]       - Restore process from green mode
  [bold]/green-list[/bold]          - Show processes in green mode
  [bold]/kill [pid][/bold]          - Terminate a process (or pick interactively)
  [bold]/web[/bold] or [bold]/gui[/bold]          - Launch Seagreen Web GUI Dashboard
  [bold]/help[/bold]                - Show this help message
  [bold]/quit[/bold]                - Exit Seagreen

[bold {COLORS['secondary']}]Examples:[/bold {COLORS['secondary']}]
  /list                  See what's running
  /list chrome           Filter processes by name
  /track                 Pick a process interactively
  /track 1234           Monitor PID 1234 directly
  /agent-track           Pick an agent to monitor
  /agent-monitor        Live dashboard for all agents
  /green                 Pick a process for green mode
  /green 1234           Enable green on PID 1234 directly
  /kill                  Pick a process to kill
  /kill 1234            Kill PID 1234 directly
    """
    console.print(help_text)


def main():
    print_banner()
    web_server = None
    
    while True:
        try:
            # Get user input
            user_input = console.input(f"[bold {COLORS['primary']}]🌊 > [/bold {COLORS['primary']}]").strip()
            
            if not user_input:
                continue
            
            # Parse command
            parts = user_input.split()
            command = parts[0].lower()
            args = parts[1:]
            
            if command in ['/quit', '/exit', 'quit', 'exit']:
                console.print(f"[bold {COLORS['leaf']}]Goodbye! 🌊[/bold {COLORS['leaf']}]")
                break
                
            elif command == '/help':
                print_help()
                
            elif command == '/list':
                filter_text = ' '.join(args) if args else ""
                list_python_processes(filter_text)
                
            elif command == '/track':
                pid = None
                duration = None
                if len(args) >= 1:
                    try:
                        pid = int(args[0])
                        duration = float(args[1]) if len(args) > 1 else None
                    except ValueError:
                        console.print(f"[bold red]PID must be a number. Example: /track 1234[/bold red]")
                        continue
                track_process_legacy(pid, duration)

            elif command == '/agent-track':
                pid = None
                duration = None
                if len(args) >= 1:
                    try:
                        pid = int(args[0])
                        duration = float(args[1]) if len(args) > 1 else None
                    except ValueError:
                        console.print(f"[bold red]PID must be a number. Example: /agent-track 1234[/bold red]")
                        continue
                track_agent_pid(pid, duration)
                    
            elif command == '/agents':
                detect_agents()
                
            elif command == '/agent-monitor':
                agent_monitor_dashboard()

            elif command == '/kill':
                pid = None
                if len(args) >= 1:
                    try:
                        pid = int(args[0])
                    except ValueError:
                        console.print(f"[bold red]PID must be a number. Example: /kill 1234[/bold red]")
                        continue
                kill_process(pid)

            elif command == '/green':
                pid = None
                if len(args) >= 1:
                    try:
                        pid = int(args[0])
                    except ValueError:
                        console.print(f"[bold red]PID must be a number. Example: /green 1234[/bold red]")
                        continue
                green_mode_enable(pid)

            elif command == '/ungreen':
                if len(args) < 1:
                    console.print(f"[bold red]Usage: /ungreen <pid>[/bold red]")
                    continue
                try:
                    green_mode_disable(int(args[0]))
                except ValueError:
                    console.print(f"[bold red]PID must be a number. Example: /ungreen 1234[/bold red]")

            elif command in ['/web', '/gui']:
                if web_server is None:
                    from .server import start_web_server
                    # Try to start server on 8080, fallback up to 8090
                    for port in range(8080, 8091):
                        web_server = start_web_server(port)
                        if web_server is not None:
                            console.print(f"[bold {COLORS['leaf']}]Started Seagreen Web Dashboard on http://localhost:{port} 🌊[/bold {COLORS['leaf']}]")
                            webbrowser.open(f"http://localhost:{port}")
                            break
                    else:
                        console.print(f"[bold red]Failed to start web server. Ports 8080-8090 were unavailable.[/bold red]")
                else:
                    port = web_server.server_address[1]
                    console.print(f"[bold {COLORS['primary']}]Web server is already running on http://localhost:{port}[/bold {COLORS['primary']}]")
                    webbrowser.open(f"http://localhost:{port}")

            elif command == '/green-list':
                list_green_processes()

            else:
                console.print(f"[bold red]Unknown command: {command}. Type /help for commands.[/bold red]")
                
        except KeyboardInterrupt:
            console.print(f"\n[bold {COLORS['leaf']}]Goodbye! 🌊[/bold {COLORS['leaf']}]")
            break
        except EOFError:
            break


def scan_trackable_processes(agent_only: bool = False, filter_text: str = "", filter_type: str = None) -> list:
    """Scan for processes with hierarchical filtering: agents, dev, apps, all"""
    results = []
    
    # Resolve filter_type if not explicitly set
    if not filter_type:
        filter_type = "agents" if agent_only else "dev"
        
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            pid = proc.info['pid']
            if pid == psutil.Process().pid:
                continue
            name = proc.info['name'] or ''
            cmdline = proc.info['cmdline'] or []
            cmdline_str = ' '.join(cmdline)[:60]

            # Skip Windows kernel processes
            if name in ['System', 'Registry', 'smss.exe', 'Idle']:
                continue

            full_text = (name + ' ' + cmdline_str).lower()
            is_agent = any(
                pattern in full_text
                for patterns in AGENT_PATTERNS.values()
                for pattern in patterns
            )
            is_dev = 'python' in name.lower() or 'node' in name.lower() or \
                     'java' in name.lower() or 'dotnet' in name.lower() or \
                     'go' in name.lower() or 'rust' in name.lower() or \
                     'docker' in name.lower()

            has_window = _get_window_title(pid) is not None

            # Apply filter type conditions
            if filter_type == "agents":
                if not is_agent:
                    continue
            elif filter_type == "dev":
                if not is_agent and not is_dev:
                    continue
            elif filter_type == "apps":
                if not is_agent and not is_dev and not has_window:
                    continue
            # "all" does not apply any exclusions beyond system idle/registry

            if filter_text and filter_text not in full_text:
                continue

            results.append({
                'pid': pid,
                'name': name,
                'app_name': get_process_display_name(pid),
                'cmdline': cmdline_str,
                'is_agent': is_agent,
                'has_window': has_window,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


def pick_process(
    prompt_text: str = "Select a process",
    agent_only: bool = False,
    allow_cancel: bool = True,
) -> Optional[int]:
    """Interactive process picker. Returns pid or None if cancelled."""
    if is_android():
        console.print(f"[bold {COLORS['warning']}]Running in sandboxed Android environment. System-wide process monitoring is disabled unless running with root. Displaying Termux-only processes.[/bold {COLORS['warning']}]")
    processes = scan_trackable_processes(agent_only=agent_only)
    if not processes:
        console.print(f"[bold yellow]No {'agent ' if agent_only else ''}processes found.[/bold yellow]")
        return None

    while True:
        processes = scan_trackable_processes(agent_only=agent_only)

        # Show header
        console.print(f"\n[bold {COLORS['primary']}]{prompt_text}:[/bold {COLORS['primary']}]")

        # Build table
        table = Table(
            show_header=True,
            header_style=f"bold {COLORS['dark']}",
            border_style=COLORS['accent'],
            box=box.SIMPLE,
        )
        table.add_column("#", style=f"bold {COLORS['primary']}", width=4)
        table.add_column("PID", style=COLORS['primary'], width=8)
        table.add_column("Application", style=COLORS['dark'], width=26)
        table.add_column("Type", style=COLORS['leaf'], width=7)

        for i, proc in enumerate(processes, 1):
            proc_type = "AGENT" if proc['is_agent'] else "DEV"
            table.add_row(str(i), str(proc['pid']), proc['app_name'], proc_type)

        console.print(table)

        # Prompt
        hint = f"Enter #, PID, or name fragment (or 'q' to cancel): "
        choice = console.input(f"[bold {COLORS['ocean']}]{hint}[/bold {COLORS['ocean']}]").strip().lower()
        if not choice:
            continue

        # Cancel
        if allow_cancel and choice in ('q', 'quit', 'cancel', 'exit', 'c'):
            console.print("[dim]Cancelled.[/dim]")
            return None

        # Number selection
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(processes):
                return processes[num - 1]['pid']

            # Could be a direct PID
            for proc in processes:
                if proc['pid'] == num:
                    return proc['pid']

        # Name / filter
        matches = [p for p in processes if choice in p['name'].lower() or choice in p['cmdline'].lower()]
        if len(matches) == 1:
            return matches[0]['pid']
        elif len(matches) > 1:
            console.print(f"[dim]{len(matches)} matches -- showing only matching processes[/dim]")
            # Re-filter by showing only these
            processes = matches
            continue
        else:
            console.print(f"[bold red]No match for '{choice}'[/bold red]")
            continue


def kill_process(pid: Optional[int] = None):
    """Kill a process with confirmation"""
    if pid is None:
        pid = pick_process("Select a process to kill")
        if pid is None:
            return

    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except psutil.NoSuchProcess:
        console.print(f"[bold red]Process {pid} not found.[/bold red]")
        return
    except psutil.AccessDenied:
        console.print(f"[bold red]Permission denied for PID {pid}.[/bold red]")
        return

    confirm = console.input(
        f"[bold yellow]Kill {name} (PID {pid})? Type 'yes' to confirm: [/bold yellow]"
    ).strip().lower()
    if confirm != 'yes':
        console.print("[dim]Kill cancelled.[/dim]")
        return

    try:
        proc.terminate()
        console.print(f"[bold {COLORS['leaf']}]Process {name} (PID {pid}) terminated.[/bold {COLORS['leaf']}]")
    except psutil.AccessDenied:
        console.print(f"[bold red]Permission denied -- try running as administrator.[/bold red]")
    except psutil.NoSuchProcess:
        console.print(f"[dim]Process {pid} already exited.[/dim]")


def green_mode_enable(pid: Optional[int] = None):
    """Put a process in low-power green mode: idle priority + single-core affinity"""
    if pid is None:
        pid = pick_process("Select a process for green mode")
        if pid is None:
            return

    if pid in green_processes:
        console.print(f"[bold yellow]PID {pid} is already in green mode. Use /ungreen {pid} to restore.[/bold yellow]")
        return

    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except psutil.NoSuchProcess:
        console.print(f"[bold red]Process {pid} not found.[/bold red]")
        return
    except psutil.AccessDenied:
        console.print(f"[bold red]Permission denied for PID {pid}.[/bold red]")
        return

    orig = {'name': name, 'nice': None, 'affinity': None}

    # Set idle priority (lowest)
    try:
        if hasattr(psutil, 'IDLE_PRIORITY_CLASS'):
            orig['nice'] = proc.nice()
            proc.nice(psutil.IDLE_PRIORITY_CLASS)
    except (psutil.AccessDenied, AttributeError):
        try:
            orig['nice'] = proc.nice()
            proc.nice(19)  # POSIX lowest priority
        except (psutil.AccessDenied, AttributeError):
            pass

    # Pin to a single CPU core -- lowest-index physical core
    try:
        current_affinity = proc.cpu_affinity()
        if current_affinity and len(current_affinity) > 1:
            orig['affinity'] = current_affinity
            proc.cpu_affinity([current_affinity[0]])
    except (psutil.AccessDenied, AttributeError):
        pass

    green_processes[pid] = orig
    console.print(f"[bold {COLORS['leaf']}]Green mode enabled for {name} (PID {pid}) 🌿[/bold {COLORS['leaf']}]")
    console.print(f"    Priority lowered to idle -- single core pinned")
    console.print(f"    Use /ungreen {pid} to restore or /green-list to see all green processes")


def green_mode_disable(pid: int):
    """Restore a process from green mode"""
    if pid not in green_processes:
        console.print(f"[bold yellow]PID {pid} is not in green mode.[/bold yellow]")
        return

    saved = green_processes[pid]
    try:
        proc = psutil.Process(pid)
        name = proc.name()

        # Restore priority
        if saved['nice'] is not None:
            try:
                proc.nice(saved['nice'])
            except (psutil.AccessDenied, AttributeError):
                pass

        # Restore CPU affinity
        if saved['affinity'] is not None:
            try:
                proc.cpu_affinity(saved['affinity'])
            except (psutil.AccessDenied, AttributeError):
                pass

        del green_processes[pid]
        console.print(f"[bold {COLORS['primary']}]Green mode disabled for {name} (PID {pid})[/bold {COLORS['primary']}]")
    except psutil.NoSuchProcess:
        del green_processes[pid]
        console.print(f"[dim]Process {pid} no longer exists -- removed from green list.[/dim]")


def list_green_processes():
    """Show all processes in green mode"""
    if not green_processes:
        console.print("[bold yellow]No processes in green mode. Use /green <pid> to add one.[/bold yellow]")
        return

    table = Table(
        show_header=True,
        header_style=f"bold {COLORS['dark']}",
        border_style=COLORS['accent'],
        box=box.SIMPLE,
    )
    table.add_column("PID", style=f"bold {COLORS['primary']}", width=8)
    table.add_column("Process", style=COLORS['dark'], width=20)

    for pid, saved in sorted(green_processes.items()):
        try:
            proc = psutil.Process(pid)
            still_alive = proc.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            still_alive = False

        label = saved['name'] if still_alive else f"[dim]{saved['name']} (gone)[/dim]"
        table.add_row(str(pid), label)

    console.print("\n[bold {COLORS['leaf']}]🌿 Green Mode Processes[/bold {COLORS['leaf']}]")
    console.print(table)
    console.print()


def track_process_legacy(pid: Optional[int] = None, duration: Optional[float] = None):
    """Legacy tracking mode for backward compatibility"""
    if pid is None:
        pid = pick_process("Select a process to track")
        if pid is None:
            return

    try:
        tracker = SeagreenEnergyTracker(pid)
    except psutil.NoSuchProcess:
        console.print(f"[bold red]Process {pid} not found. Use /list to see available processes.[/bold red]")
        return
    except psutil.AccessDenied:
        console.print(f"[bold red]Permission denied for process {pid}. Try a process you own.[/bold red]")
        return
    
    console.print(f"\n[bold {COLORS['primary']}]Monitoring PID {pid} for {duration or 'indefinite'}s...[/bold {COLORS['primary']}]")
    console.print(f"[dim]Press Ctrl+C to stop early[/dim]\n")
    
    tracker.start_monitoring()
    
    # Simple progress display
    start_time = time.time()
    try:
        with console.status(f"[bold {COLORS['ocean']}]Tracking...", spinner="dots") as status:
            while duration is None or (time.time() - start_time) < duration:
                tracker.take_snapshot()
                elapsed = time.time() - start_time
                status.update(f"[bold {COLORS['ocean']}]{elapsed:.1f}s / {duration or '∞'}s elapsed...")
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print(f"\n[bold {COLORS['secondary']}]Stopped early.[/bold {COLORS['secondary']}]")
    
    # Generate report
    try:
        report = tracker.generate_report()
        print_agent_report(report)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")


if __name__ == "__main__":
    main()
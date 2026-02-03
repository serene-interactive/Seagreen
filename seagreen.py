#!/usr/bin/env python3
"""
🌊 Seagreen - Interactive process tracking for developers.
by Serene Interactive, Global

Commands:
  /list     - Show Python processes you can track
  /track <pid> [seconds] - Monitor a process (default: 10s)
  /help     - Show all commands
  /quit     - Exit Seagreen
"""

import sys
import time
import psutil
from typing import Optional, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box

from tracker import SeagreenTracker, SeagreenReport

# Colors matching sereneinteractive.com
COLORS = {
    'primary': '#3d8b6f',
    'secondary': '#4a9b6e',
    'accent': '#5ab88a',
    'dark': '#1a2e28',
    'ocean': '#2d6b5d',
    'leaf': '#6bc99a',
}

console = Console()


def print_banner():
    """Clean centered banner using Rich alignment"""
    # ASCII art for SEAGREEN (narrower to fit better)
    ascii_art = f"""[bold {COLORS['primary']}]
 ███████╗███████╗███████╗ ██████╗ ███████╗███████╗███╗   ██╗
 ██╔════╝██╔════╝██╔════╝██╔════╝ ██╔════╝██╔════╝████╗  ██║
 ███████╗█████╗  █████╗  ██║  ███╗█████╗  █████╗  ██╔██╗ ██║
 ╚════██║██╔══╝  ██╔══╝  ██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║
 ███████║███████╗███████╗╚██████╔╝███████╗███████╗██║ ╚████║
 ╚══════╝╚══════╝╚══════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝[/bold {COLORS['primary']}]
"""
    
    subtitle = f"[bold {COLORS['leaf']}]🌊  Process Efficiency Monitor  🌿[/bold {COLORS['leaf']}]"
    company = f"[dim {COLORS['secondary']}]by Serene Interactive, Global[/dim {COLORS['secondary']}]"
    hint = f"[dim {COLORS['ocean']}]Type /help for commands[/dim {COLORS['ocean']}]"
    
    console.print()
    console.print(Align.center(ascii_art))
    console.print(Align.center(subtitle))
    console.print(Align.center(company))
    console.print()
    console.print(Align.center(hint))
    console.print()


def list_python_processes():
    """Show all Python processes the user might want to track"""
    python_procs = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
        try:
            # Check if it's a Python process
            if 'python' in proc.info['name'].lower():
                cmd = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else '[unknown]'
                # Skip Seagreen itself
                if 'seagreen' in cmd.lower():
                    continue
                python_procs.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmd': cmd[:60] + '...' if len(cmd) > 60 else cmd,
                    'cpu': proc.info['cpu_percent'] or 0,
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not python_procs:
        console.print(f"[bold {COLORS['secondary']}]No Python processes found. Start a Python script first![/bold {COLORS['secondary']}]")
        return
    
    table = Table(
        show_header=True,
        header_style=f"bold {COLORS['dark']}",
        border_style=COLORS['accent'],
        box=box.SIMPLE
    )
    table.add_column("PID", style=f"bold {COLORS['primary']}", width=8)
    table.add_column("Process", style=COLORS['dark'], width=12)
    table.add_column("Command", style=COLORS['secondary'])
    
    for proc in python_procs[:20]:  # Show max 20
        table.add_row(
            str(proc['pid']),
            proc['name'],
            proc['cmd']
        )
    
    console.print(table)
    console.print(f"\n[dim]Use: /track <pid> to monitor one[/dim]\n")


def track_process(pid: int, duration: float = 10.0):
    """Monitor a specific process"""
    try:
        tracker = SeagreenTracker(pid)
    except psutil.NoSuchProcess:
        console.print(f"[bold red]Process {pid} not found. Use /list to see available processes.[/bold red]")
        return
    except psutil.AccessDenied:
        console.print(f"[bold red]Permission denied for process {pid}. Try a process you own.[/bold red]")
        return
    
    console.print(f"\n[bold {COLORS['primary']}]Monitoring PID {pid} for {duration}s...[/bold {COLORS['primary']}]")
    console.print(f"[dim]Press Ctrl+C to stop early[/dim]\n")
    
    tracker.start_monitoring()
    
    # Simple progress display
    start_time = time.time()
    try:
        with console.status(f"[bold {COLORS['ocean']}]Tracking...", spinner="dots") as status:
            while time.time() - start_time < duration:
                tracker.take_snapshot()
                elapsed = time.time() - start_time
                status.update(f"[bold {COLORS['ocean']}]{elapsed:.1f}s / {duration}s elapsed...")
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print(f"\n[bold {COLORS['secondary']}]Stopped early.[/bold {COLORS['secondary']}]")
    
    # Generate report
    try:
        report = tracker.generate_report()
        print_report(report)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")


def print_report(report: SeagreenReport):
    """Display the efficiency report"""
    console.print("\n")
    
    # Results
    table = Table(
        show_header=False,
        border_style=COLORS['accent'],
        box=box.SIMPLE
    )
    table.add_column("Metric", style=f"bold {COLORS['secondary']}")
    table.add_column("Value", style=COLORS['primary'])
    
    table.add_row("Process", report.process_name)
    table.add_row("Duration", f"{report.duration_seconds:.1f}s")
    table.add_row("Avg CPU", f"{report.avg_cpu:.1f}%")
    table.add_row("Peak CPU", f"{report.peak_cpu:.1f}%")
    table.add_row("Avg Memory", f"{report.avg_memory_mb:.1f} MB")
    table.add_row("CPU-Seconds", f"{report.cpu_seconds:.2f}")
    
    console.print(table)
    
    # Rating
    console.print(f"\n[bold {COLORS['primary']}]Efficiency: {report.efficiency_score:.0f}/100[/bold {COLORS['primary']}]")
    console.print(f"[bold {COLORS['leaf']}]Rating: {report.seagreen_rating}[/bold {COLORS['leaf']}]")
    console.print()


def print_help():
    """Show available commands"""
    help_text = f"""
[bold {COLORS['primary']}]Seagreen Commands:[/bold {COLORS['primary']}]

  [bold]/list[/bold]              - Show Python processes you can track
  [bold]/track <pid> [time][/bold] - Monitor a process (default 10s)
  [bold]/help[/bold]              - Show this help message
  [bold]/quit[/bold]              - Exit Seagreen

[bold {COLORS['secondary']}]Examples:[/bold {COLORS['secondary']}]
  /list                  See what's running
  /track 1234           Monitor PID 1234 for 10 seconds
  /track 1234 30        Monitor PID 1234 for 30 seconds
    """
    console.print(help_text)


def main():
    print_banner()
    
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
                list_python_processes()
                
            elif command == '/track':
                if len(args) < 1:
                    console.print(f"[bold red]Usage: /track <pid> [seconds][/bold red]")
                    continue
                
                try:
                    pid = int(args[0])
                    duration = float(args[1]) if len(args) > 1 else 10.0
                    track_process(pid, duration)
                except ValueError:
                    console.print(f"[bold red]PID must be a number. Example: /track 1234[/bold red]")
                    
            else:
                console.print(f"[bold red]Unknown command: {command}. Type /help for commands.[/bold red]")
                
        except KeyboardInterrupt:
            console.print(f"\n[bold {COLORS['leaf']}]Goodbye! 🌊[/bold {COLORS['leaf']}]")
            break
        except EOFError:
            break


if __name__ == "__main__":
    main()

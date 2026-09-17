"""Seagreen v3.0.0 — terminal entry point and local web launcher."""
import argparse
import shlex
import sys
import time
import webbrowser
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text
import psutil
from .control import inspect_target, control_process
from .monitor import Monitor

console = Console()


def process_table(sample, name='', pid=None):
    table = Table(title='Seagreen · observed process counters', border_style='#4a8060')
    for title in ['PID', 'Process', 'CPU / core', 'Resident memory', 'Disk I/O']:
        table.add_column(title, justify='left' if title == 'Process' else 'right')
    if not sample:
        table.caption = 'Collecting the first sample… Run /list again in a moment.'
        return table
    for process in sample['processes']:
        if name and name.lower() not in process['name'].lower():
            continue
        if pid is not None and process['pid'] != pid:
            continue
        cpu = '—' if process['cpu'] is None else f"{process['cpu']:.1f}%"
        io = '—' if process['readRate'] is None and process['writeRate'] is None else f"{((process['readRate'] or 0) + (process['writeRate'] or 0)) / 1024:.0f} KB/s"
        table.add_row(str(process['pid']), Text(process['name']), cpu, f"{process['memory'] / 1024**2:.1f} MB", io)
        if table.row_count >= 30:
            break
    table.caption = '100% CPU = one logical core. Power is never inferred from CPU percentage.'
    return table


def live_monitor(monitor, pid=None, seconds=None):
    started = time.monotonic()
    try:
        with Live(console=console, refresh_per_second=1) as display:
            while seconds is None or time.monotonic() - started < seconds:
                state = monitor.snapshot()
                display.update(process_table(state['sample'], pid=pid))
                time.sleep(1)
    except KeyboardInterrupt:
        pass


def terminate_prompt(pid, force=False):
    try:
        created = psutil.Process(pid).create_time()
        proc = inspect_target(pid, created)
        name = proc.name()
    except psutil.Error as error:
        raise ValueError('Process unavailable. Refresh the process list.') from error
    mode = 'Force quit' if force else 'Request quit'
    detail = 'Unsaved work will be lost.' if force else 'The app may handle or ignore this request. Save work first.'
    console.print(Panel(Text(f'{name} · PID {pid}\n{detail}\nOnly this process is targeted; children may remain.'), title=mode, border_style='#4a8060'))
    if not sys.stdin.isatty():
        raise ValueError('An interactive terminal is required to confirm process control.')
    if Confirm.ask('Continue?', default=False):
        console.print(control_process(pid, created, 'force' if force else 'quit')['message'], markup=False)
    else:
        console.print('[dim]Cancelled. Nothing was changed.[/dim]')


def show_help():
    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column(style='#79ab8b'); table.add_column()
    for command, detail in [('/list [name]', 'Browse resource usage'), ('/track [pid] [seconds]', 'Live monitoring · Ctrl+C returns here'), ('/stop <pid>', 'Request a process to quit'), ('/kill <pid>', 'Force quit · confirmation required'), ('/web or /gui', 'Open the local dashboard'), ('/agents [runtime]', 'Filter by runtime name'), ('/quit', 'Exit Seagreen')]:
        table.add_row(Text(command), Text(detail))
    console.print(Panel(table, title='Your workspace', border_style='#4a8060'))
    console.print('[dim]Recordings, exports and background scheduling are available in /web.[/dim]')


def interactive():
    console.print(Panel('[bold #79ab8b]SEAGREEN 3.0.0[/bold #79ab8b]  ·  BY SERENE INTERACTIVE\n\nA lighter footprint. A clearer picture.\n[dim]Local monitoring · no account · no telemetry[/dim]', border_style='#4a8060', padding=(1, 2)))
    show_help()
    monitor = Monitor()
    monitor.start()
    web = None
    try:
        while True:
            try:
                command = shlex.split(console.input('[#397956]seagreen > [/#397956]'))
                if not command:
                    continue
                name, args = command[0].lstrip('/'), command[1:]
                if name in ('quit', 'exit'):
                    break
                if name in ('web', 'gui'):
                    from .server import start_web_server
                    if web is None:
                        for port in range(8080, 8091):
                            web = start_web_server(port)
                            if web:
                                break
                    if web:
                        console.print('Opening your private local dashboard. Keep this terminal running.')
                        webbrowser.open(web.launch_url)
                    else:
                        console.print('Local ports 8080–8090 are busy.')
                elif name == 'list':
                    console.print(process_table(monitor.snapshot()['sample'], name=' '.join(args)))
                elif name in ('track', 'agent-track', 'monitor', 'agent-monitor'):
                    pid = int(args[0]) if args else None
                    seconds = float(args[1]) if len(args) > 1 else None
                    live_monitor(monitor, pid, seconds)
                elif name == 'agents':
                    console.print('Runtime name filtering is not proof that a process is an AI agent.')
                    console.print(process_table(monitor.snapshot()['sample'], name=args[0] if args else 'python'))
                elif name in ('stop', 'kill'):
                    if len(args) != 1:
                        raise ValueError('Usage: /' + name + ' <pid>')
                    terminate_prompt(int(args[0]), force=name == 'kill')
                elif name in ('green', 'ungreen', 'green-list'):
                    console.print('Use /web → Efficiency to launch an explicitly selected background job. Use /stop <pid> or /kill <pid> for confirmed process control.')
                elif name == 'help':
                    show_help()
                else:
                    console.print('Unknown command. Type /help.')
            except (ValueError, OSError) as error:
                console.print(str(error), markup=False)
            except (EOFError, KeyboardInterrupt):
                break
    finally:
        monitor.stop()
        if web:
            web.shutdown(); web.server_close()


def main():
    if len(sys.argv) == 1:
        interactive()
        return
    if sys.argv[1] in ('web', '--web', 'gui'):
        from .server import main as web_main
        del sys.argv[1]
        web_main()
        return
    parser = argparse.ArgumentParser(description='Seagreen v3.0.0 — local monitoring')
    sub = parser.add_subparsers(dest='command', required=True)
    listing = sub.add_parser('list', help='List observed processes')
    listing.add_argument('name', nargs='?', default='')
    tracking = sub.add_parser('monitor', help='Live process resource counters')
    tracking.add_argument('--pid', type=int)
    tracking.add_argument('--duration', type=float)
    sub.add_parser('web', help='Open the local web UI')
    for name, description in [('stop', 'Request a process to quit'), ('kill', 'Force quit a process')]:
        control = sub.add_parser(name, help=description + ' (confirmation required)')
        control.add_argument('pid', type=int)
    args = parser.parse_args()
    if args.command in ('stop', 'kill'):
        try:
            terminate_prompt(args.pid, force=args.command == 'kill')
        except (ValueError, OSError) as error:
            parser.exit(1, str(error) + '\n')
        except (KeyboardInterrupt, EOFError):
            parser.exit(1, 'Cancelled.\n')
        return
    monitor = Monitor()
    monitor.start()
    try:
        time.sleep(2.1)
        if args.command == 'list':
            console.print(process_table(monitor.snapshot()['sample'], name=args.name))
        elif args.command == 'monitor':
            live_monitor(monitor, args.pid, args.duration)
    finally:
        monitor.stop()


if __name__ == '__main__':
    main()

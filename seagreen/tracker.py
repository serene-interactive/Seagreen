"""
[Sea] Seagreen Tracker Module -- Process Energy Monitoring
Energy estimation, carbon tracking, and Green Score for any process
"""

import psutil
import time
import os
import platform
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class ResourceSnapshot:
    """A single snapshot of resource usage"""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    watts_estimated: float = 0.0


@dataclass
class AgentEnergyReport:
    """Energy report for a monitored agent or process"""
    process_name: str
    pid: int
    runtime: str  # "python", "node", "system", etc.
    agent_types: List[str]
    duration_seconds: float
    uptime_str: str
    current_watts: float
    session_kwh: float
    session_co2_g: float
    grid_intensity: float
    grid_region: str
    avg_cpu: float
    peak_cpu: float
    avg_memory_mb: float
    peak_memory_mb: float
    cpu_seconds: float
    green_score: float
    green_grade: str
    seagreen_rating: str
    component_breakdown: dict
    top_consumers: List[Tuple[str, float]]


# Grid carbon intensity data (g CO₂/kWh)
# Sources: EPA eGRID, European Environment Agency, various government data
GRID_INTENSITY = {
    'texas': 410,      # ERCOT (Texas)
    'california': 220, # CAISO (California)
    'pjm': 380,        # PJM (Mid-Atlantic)
    'miso': 520,       # MISO (Midwest)
    'spp': 450,        # SPP (Great Plains)
    'nysio': 250,      # NYISO (New York)
    'iso_ne': 280,     # ISO New England
    'uk': 280,         # UK
    'germany': 360,    # Germany
    'france': 60,      # France (nuclear heavy)
    'australia': 700,  # Australia (coal heavy)
    'japan': 450,      # Japan
    'china': 550,      # China (coal heavy)
    'global_avg': 475, # Global average
}

# Default platform-specific TDP values (watts)
# These are estimates -- users can override via calibration
PLATFORM_TDP = {
    'Linux': {'idle': 5, 'max': 65},      # General Linux desktop/server
    'Darwin': {'idle': 3, 'max': 30},     # Mac Mini M-series
    'Windows': {'idle': 8, 'max': 70},    # Windows desktop
}

# Agent detection signatures
AGENT_SIGNATURES = {
    'hermes': {
        'patterns': ['hermes', 'hermes-agent'],
        'runtimes': ['python', 'python3', 'node', 'nodejs'],
    },
    'openclaw': {
        'patterns': ['openclaw', 'openclaw gateway', 'openclaw-agent'],
        'runtimes': ['node', 'nodejs'],
    },
    'langchain': {
        'patterns': ['langchain'],
        'runtimes': ['python', 'python3', 'node', 'nodejs'],
    },
    'crewai': {
        'patterns': ['crewai'],
        'runtimes': ['python', 'python3'],
    },
    'autogen': {
        'patterns': ['autogen', 'autogen-agent'],
        'runtimes': ['python', 'python3'],
    },
}


def detect_runtime(name: str, cmdline: str) -> str:
    """Detect the runtime type (python, node, system, etc.)"""
    full = (name + ' ' + cmdline).lower()
    if 'python' in full:
        return 'python'
    elif 'node' in full or 'nodejs' in full:
        return 'node'
    elif 'java' in full or 'jvm' in full:
        return 'java'
    elif 'dotnet' in full or 'dotnet' in full:
        return 'dotnet'
    elif 'docker' in full or 'containerd' in full:
        return 'docker'
    elif 'go' in full or 'golang' in full:
        return 'go'
    elif 'rust' in full or 'cargo' in full:
        return 'rust'
    else:
        return 'system'


def detect_agent_type(name: str, cmdline: str) -> List[str]:
    """Detect if this is a known agent type"""
    full = (name + ' ' + cmdline).lower()
    detected = []
    for agent_type, signature in AGENT_SIGNATURES.items():
        if any(pattern in full for pattern in signature['patterns']):
            detected.append(agent_type)
    return detected


def get_grid_region() -> Tuple[str, float]:
    """Auto-detect grid region from timezone"""
    try:
        # Try to get timezone name
        import datetime
        tz = datetime.datetime.now().astimezone().tzinfo
        tz_name = str(tz) if tz else ''
    except Exception:
        tz_name = ''

    if 'US/Central' in tz_name or 'America/Chicago' in tz_name:
        return ('Texas (ERCOT)', GRID_INTENSITY['texas'])
    elif 'US/Pacific' in tz_name or 'America/Los_Angeles' in tz_name:
        return ('California (CAISO)', GRID_INTENSITY['california'])
    elif 'US/Eastern' in tz_name or 'America/New_York' in tz_name:
        return ('PJM', GRID_INTENSITY['pjm'])
    elif 'Europe/London' in tz_name or 'Europe/Paris' in tz_name:
        return ('UK', GRID_INTENSITY['uk'])
    elif 'Europe' in tz_name:
        return ('Germany (EU avg)', GRID_INTENSITY['germany'])
    elif 'Asia/Shanghai' in tz_name or 'Asia/Beijing' in tz_name:
        return ('China', GRID_INTENSITY['china'])
    elif 'Japan' in tz_name or 'Asia/Tokyo' in tz_name:
        return ('Japan', GRID_INTENSITY['japan'])
    elif 'Australia' in tz_name:
        return ('Australia', GRID_INTENSITY['australia'])
    else:
        return ('Global Average', GRID_INTENSITY['global_avg'])


def format_uptime(seconds: float) -> str:
    """Format uptime in human-readable string"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    else:
        return f"{minutes}m {secs:02d}s"


def compute_green_score(
    watts: float,
    cpu_percent: float,
    memory_mb: float,
    duration: float,
    tdp_idle: float,
    tdp_max: float,
) -> float:
    """Compute a 0-100 Green Score based on efficiency"""
    if tdp_max <= tdp_idle:
        return 50.0  # Neutral score if no valid TDP

    # Energy efficiency: how much of max TDP we're using
    power_ratio = watts / tdp_max if tdp_max > 0 else 1.0
    power_penalty = max(0, power_ratio - 0.1) * 100  # Penalty for using >10% of max TDP

    # CPU efficiency: lower is better (idle = good)
    cpu_penalty = max(0, (cpu_percent - 20) * 0.5)  # Penalty starts at >20% CPU

    # Memory waste: if memory is very high, penalize slightly
    mem_penalty = max(0, (memory_mb - 1000) / 100) if memory_mb > 1000 else 0

    raw_score = max(0, 100 - power_penalty - cpu_penalty - mem_penalty)
    return min(raw_score, 100)


def compute_green_grade(score: float) -> str:
    """Convert Green Score to letter grade"""
    if score >= 95:
        return 'A+'
    elif score >= 85:
        return 'A'
    elif score >= 75:
        return 'B+'
    elif score >= 65:
        return 'B'
    elif score >= 55:
        return 'C'
    elif score >= 45:
        return 'D'
    else:
        return 'F'


def compute_seagreen_rating(score: float) -> str:
    """Convert score to leaf rating"""
    if score >= 80:
        return "[Leaf][Leaf][Leaf] Excellent"
    elif score >= 60:
        return "[Leaf][Leaf] Good"
    elif score >= 40:
        return "[Leaf] Fair"
    else:
        return "[LeafFall] Needs Improvement"


def compute_component_breakdown(process_tree: List[dict]) -> dict:
    """Estimate energy breakdown by component type for agent monitoring"""
    breakdown = {'LLM inference': 0, 'Sub-agents': 0, 'Tool execution': 0, 'Other': 0}

    if not process_tree:
        breakdown['Other'] = 100
        return breakdown

    total_watts = sum(p['watts'] for p in process_tree)
    if total_watts <= 0:
        return breakdown

    # Heuristic: label processes based on names and cmdline
    for proc in process_tree:
        name = proc.get('name', '')
        cmdline = proc.get('cmdline', '')
        watts = proc['watts']
        pct = (watts / total_watts) * 100

        full = (name + ' ' + cmdline).lower()

        if any(x in full for x in ['llm', 'inference', 'model', 'generate',
                                    'transformers', 'torch', 'tensor',
                                    'api', 'completion']):
            breakdown['LLM inference'] += pct
        elif any(x in full for x in ['subprocess', 'spawn', 'child',
                                      'agent-loop', 'task-runner',
                                      'hermes', 'openclaw-agent']):
            breakdown['Sub-agents'] += pct
        elif any(x in full for x in ['tool', 'bash', 'shell', 'exec',
                                      'plugin', 'skill', 'command',
                                      'github', 'discord', 'slack']):
            breakdown['Tool execution'] += pct
        else:
            breakdown['Other'] += pct

    # Normalize to 100%
    total = sum(breakdown.values())
    if total > 0:
        for k in breakdown:
            breakdown[k] = round(breakdown[k] * 100 / total)
    return breakdown


class SeagreenEnergyTracker:
    """
    Seagreen Energy Tracker -- tracks process trees, estimates energy,
    computes carbon footprint, and generates Green Scores.
    Supports both single PID and PID tree tracking.
    """

    def __init__(self, pid: int):
        self.pid = pid
        try:
            self.process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            raise

        self.process_name = self.process.name()
        try:
            cmdline_list = self.process.cmdline()
            self.cmdline = ' '.join(cmdline_list) if cmdline_list else ''
        except (psutil.AccessDenied, psutil.ZombieProcess):
            self.cmdline = ''

        # Process info
        self.runtime = detect_runtime(self.process_name, self.cmdline)
        self.agent_types = detect_agent_type(self.process_name, self.cmdline)

        # Platform TDP defaults
        system = platform.system()
        tdp_defaults = PLATFORM_TDP.get(system, {'idle': 5, 'max': 65})
        self.tdp_idle = tdp_defaults['idle']
        self.tdp_max = tdp_defaults['max']

        # Grid carbon intensity
        self.grid_region, self.grid_intensity = get_grid_region()

        # Monitoring state
        self.snapshots: List[ResourceSnapshot] = []
        self.child_processes: List[dict] = []
        self.start_time: Optional[float] = None
        self.start_timestamp: Optional[float] = None

        # Track highest power consumers
        self.top_consumer_snapshots: List[Tuple[str, float, float]] = []  # (name, watts, timestamp)

        # System idle baseline (measured at start)
        self.system_idle_watts: Optional[float] = None

    def _measure_system_idle(self) -> float:
        """Take a quick baseline reading of the system's idle power draw."""
        # Sample system-wide CPU for a brief moment to estimate idle
        idle_cpu = psutil.cpu_percent(interval=0.1)
        return self.tdp_idle + (self.tdp_max - self.tdp_idle) * (idle_cpu / 100)

    def start_monitoring(self):
        """Begin tracking"""
        now = time.time()
        self.start_time = now
        self.start_timestamp = now
        # Measure system idle baseline to subtract from process watts
        self.system_idle_watts = self._measure_system_idle()

    def take_snapshot(self) -> ResourceSnapshot:
        """Capture current resource usage including energy estimate"""
        # Main process snapshot
        try:
            with self.process.oneshot():
                cpu = self.process.cpu_percent(interval=0)
                mem_info = self.process.memory_info()
                mem_mb = mem_info.rss / 1024 / 1024 if hasattr(mem_info, 'rss') else 0
                mem_percent = self.process.memory_percent() if hasattr(self.process, 'memory_percent') else 0
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            cpu = 0
            mem_mb = 0
            mem_percent = 0

        # Estimate watts
        watts = self._estimate_watts(cpu)

        snapshot = ResourceSnapshot(
            timestamp=time.time(),
            cpu_percent=cpu,
            memory_mb=mem_mb,
            memory_percent=mem_percent,
            watts_estimated=watts,
        )
        self.snapshots.append(snapshot)

        # Track child processes
        self._update_child_processes()

        return snapshot

    def _estimate_watts(self, cpu_percent: float) -> float:
        """Estimate power consumption from CPU utilization.
        Uses a linear model between idle and max TDP.
        For low-CPU processes (<5%), subtracts the system idle baseline
        to avoid attributing system power to an idle process.
        """
        # Full system power estimate
        full_watts = self.tdp_idle + (self.tdp_max - self.tdp_idle) * (cpu_percent / 100)

        if cpu_percent < 5.0 and self.system_idle_watts is not None:
            # For nearly idle processes, attribute only the power above idle
            # This prevents inflating energy for processes doing almost nothing
            process_watts = max(0, full_watts - self.system_idle_watts)
            return process_watts
        else:
            return full_watts

    def _update_child_processes(self):
        """Discover and update child processes"""
        try:
            children = self.process.children(recursive=True)
            self.child_processes = []
            for child in children:
                try:
                    with child.oneshot():
                        child_cpu = child.cpu_percent(interval=0)
                        child_mem = child.memory_info()
                        child_mem_mb = child_mem.rss / 1024 / 1024 if hasattr(child_mem, 'rss') else 0
                        child_watts = self._estimate_watts(child_cpu)
                        child_name = child.name() or child.cmdline()[:1] if child.cmdline() else 'unknown'

                        self.child_processes.append({
                            'pid': child.pid,
                            'name': child.name(),
                            'cmdline': ' '.join(child.cmdline())[:80] if child.cmdline() else '',
                            'cpu': child_cpu,
                            'memory_mb': child_mem_mb,
                            'watts': child_watts,
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def generate_report(self) -> AgentEnergyReport:
        """Generate energy report from collected data"""
        if not self.snapshots or self.start_time is None:
            raise ValueError("No monitoring data collected!")

        now = time.time()
        duration = now - self.start_time

        # Calculate averages and peaks
        cpu_values = [s.cpu_percent for s in self.snapshots]
        mem_values = [s.memory_mb for s in self.snapshots]
        watts_values = [s.watts_estimated for s in self.snapshots]

        avg_cpu = sum(cpu_values) / len(cpu_values)
        peak_cpu = max(cpu_values)
        avg_memory = sum(mem_values) / len(mem_values)
        peak_memory = max(mem_values)
        avg_watts = sum(watts_values) / len(watts_values)

        # Also calculate process-only watts (excluding system idle baseline)
        if self.system_idle_watts is not None:
            process_watts = [max(0, w - self.system_idle_watts) if s.cpu_percent < 5 else w
                           for w, s in zip(watts_values, self.snapshots)]
            avg_process_watts = sum(process_watts) / len(process_watts) if process_watts else avg_watts
        else:
            avg_process_watts = avg_watts

        # CPU-seconds: total CPU time consumed
        cpu_seconds = (avg_cpu / 100) * duration

        # Energy: use process-attributable watts for session energy
        # This avoids inflating energy with system idle baseline
        session_kwh = avg_process_watts * (duration / 3600)

        # Carbon: kWh × grid intensity (g CO₂/kWh) / 1000 = g CO₂
        session_co2_g = session_kwh * self.grid_intensity

        # Green Score
        green_score = compute_green_score(
            watts=avg_process_watts,
            cpu_percent=avg_cpu,
            memory_mb=avg_memory,
            duration=duration,
            tdp_idle=self.tdp_idle,
            tdp_max=self.tdp_max,
        )
        green_grade = compute_green_grade(green_score)

        # Component breakdown
        component_breakdown = compute_component_breakdown(self.child_processes)

        # Top consumers (by watts)
        top_consumers = sorted(
            [(p['name'], p['watts']) for p in self.child_processes],
            key=lambda x: x[1],
            reverse=True,
        )
        # Add main process (use process-attributable watts)
        top_consumers.insert(0, (self.process_name, avg_process_watts))
        top_consumers = top_consumers[:10]  # Keep top 10

        # Process uptime
        try:
            create_time = self.process.create_time()
            uptime_seconds = now - create_time
            uptime_str = format_uptime(uptime_seconds)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            uptime_str = format_uptime(duration)

        return AgentEnergyReport(
            process_name=self.process_name,
            pid=self.pid,
            runtime=self.runtime,
            agent_types=self.agent_types,
            duration_seconds=duration,
            uptime_str=uptime_str,
            current_watts=watts_values[-1] if watts_values else 0,
            session_kwh=session_kwh,
            session_co2_g=session_co2_g,
            grid_intensity=self.grid_intensity,
            grid_region=self.grid_region,
            avg_cpu=avg_cpu,
            peak_cpu=peak_cpu,
            avg_memory_mb=avg_memory,
            peak_memory_mb=peak_memory,
            cpu_seconds=cpu_seconds,
            green_score=green_score,
            green_grade=green_grade,
            seagreen_rating=compute_seagreen_rating(green_score),
            component_breakdown=component_breakdown,
            top_consumers=top_consumers,
        )

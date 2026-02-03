"""
🌿 Seagreen Tracker Module
Measures computational efficiency with eco-friendly metrics
"""

import psutil
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class ResourceSnapshot:
    """A single snapshot of resource usage"""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float


@dataclass
class SeagreenReport:
    """Final report after monitoring session"""
    process_name: str
    duration_seconds: float
    avg_cpu: float
    peak_cpu: float
    avg_memory_mb: float
    peak_memory_mb: float
    cpu_seconds: float  # Total CPU time consumed
    efficiency_score: float  # 0-100 scale
    seagreen_rating: str  # 🌿🍃🌱 rating


class SeagreenTracker:
    """
    🌊 Tracks process resource usage and calculates efficiency
    """
    
    # Serene Interactive color palette (matching the website)
    COLORS = {
        'serene_green': '#3d8b6f',
        'light_green': '#4a9b6e',
        'dark_green': '#1a2e28',
        'soft_green': '#5ab88a',
        'ocean': '#2d6b5d',
        'leaf': '#6bc99a',
    }
    
    def __init__(self, pid: int):
        self.pid = pid
        self.process = psutil.Process(pid)
        self.snapshots: list[ResourceSnapshot] = []
        self.start_time: Optional[float] = None
        
    def start_monitoring(self):
        """Begin tracking the process"""
        self.start_time = time.time()
        
    def take_snapshot(self) -> ResourceSnapshot:
        """Capture current resource usage"""
        with self.process.oneshot():
            cpu = self.process.cpu_percent(interval=0.1)
            mem_info = self.process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024  # Convert to MB
            mem_percent = self.process.memory_percent()
            
        snapshot = ResourceSnapshot(
            timestamp=time.time(),
            cpu_percent=cpu,
            memory_mb=mem_mb,
            memory_percent=mem_percent
        )
        self.snapshots.append(snapshot)
        return snapshot
    
    def generate_report(self) -> SeagreenReport:
        """Generate the final efficiency report"""
        if not self.snapshots or self.start_time is None:
            raise ValueError("No monitoring data collected!")
            
        duration = time.time() - self.start_time
        
        # Calculate averages and peaks
        cpu_values = [s.cpu_percent for s in self.snapshots]
        mem_values = [s.memory_mb for s in self.snapshots]
        
        avg_cpu = sum(cpu_values) / len(cpu_values)
        peak_cpu = max(cpu_values)
        avg_memory = sum(mem_values) / len(mem_values)
        peak_memory = max(mem_values)
        
        # CPU-seconds: how much CPU time was actually consumed
        cpu_seconds = (avg_cpu / 100) * duration
        
        # Efficiency score calculation
        # Lower CPU usage over shorter time = higher efficiency
        # Scale: 0-100 where 100 is perfectly efficient
        if duration > 0:
            # Base efficiency on CPU utilization vs time
            # Goal: accomplish task with minimal CPU% × time
            efficiency = max(0, min(100, 100 - (avg_cpu * (duration / 60))))
        else:
            efficiency = 0
            
        # Cute leaf rating system
        if efficiency >= 80:
            rating = "🌿🌿🌿 Excellent!"
        elif efficiency >= 60:
            rating = "🌿🌿 Good"
        elif efficiency >= 40:
            rating = "🌿 Fair"
        else:
            rating = "🍂 Needs Improvement"
            
        return SeagreenReport(
            process_name=self.process.name(),
            duration_seconds=duration,
            avg_cpu=avg_cpu,
            peak_cpu=peak_cpu,
            avg_memory_mb=avg_memory,
            peak_memory_mb=peak_memory,
            cpu_seconds=cpu_seconds,
            efficiency_score=efficiency,
            seagreen_rating=rating
        )

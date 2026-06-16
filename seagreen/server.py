import http.server
import socketserver
import threading
import json
import webbrowser
import os
import sys
import psutil
from urllib.parse import urlparse, parse_qs
from typing import Optional
from .tracker import SeagreenEnergyTracker, is_android
from .__main__ import (
    scan_trackable_processes,
    green_mode_enable,
    green_mode_disable,
    green_processes,
    get_process_display_name,
)

# Shared tracker instance for active web monitoring
_active_tracker: Optional[SeagreenEnergyTracker] = None
_active_tracker_lock = threading.Lock()

class SeagreenHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging in console to keep Seagreen TUI neat
        pass

    def do_GET(self):
        global _active_tracker
        
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        # Route: Static Assets
        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
            return
            
        elif path == '/api/processes':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            filter_type = query_params.get('type', ['apps'])[0]
            procs = scan_trackable_processes(filter_type=filter_type)
            # Mark which ones are in green mode
            for p in procs:
                p['is_green'] = p['pid'] in green_processes
            self.wfile.write(json.dumps(procs).encode('utf-8'))
            return
            
        elif path == '/api/system':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                cpu_usage = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                ram_percent = ram.percent
                total_procs = len(psutil.pids())
                
                battery = psutil.sensors_battery()
                battery_percent = battery.percent if battery else None
                power_plugged = battery.power_plugged if battery else None
            except Exception:
                cpu_usage = 0.0
                ram_percent = 0.0
                total_procs = 0
                battery_percent = None
                power_plugged = None
                
            system_data = {
                "cpu_percent": cpu_usage,
                "ram_percent": ram_percent,
                "total_processes": total_procs,
                "green_count": len(green_processes),
                "battery_percent": battery_percent,
                "power_plugged": power_plugged,
                "platform": sys.platform,
            }
            self.wfile.write(json.dumps(system_data).encode('utf-8'))
            return
            
        elif path.startswith('/api/track/'):
            try:
                pid = int(path.split('/')[-1])
            except ValueError:
                self.send_error(400, "Invalid PID")
                return
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            report_data = {}
            with _active_tracker_lock:
                if _active_tracker is None or _active_tracker.pid != pid:
                    try:
                        _active_tracker = SeagreenEnergyTracker(pid)
                        _active_tracker.start_monitoring()
                    except Exception as e:
                        self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                        return
                
                try:
                    _active_tracker.take_snapshot()
                    report = _active_tracker.generate_report()
                    current_cpu = _active_tracker.snapshots[-1].cpu_percent if _active_tracker.snapshots else 0.0
                    report_data = {
                        "pid": report.pid,
                        "process_name": report.process_name,
                        "app_name": get_process_display_name(report.pid),
                        "runtime": report.runtime,
                        "agent_types": report.agent_types,
                        "duration_seconds": report.duration_seconds,
                        "uptime_str": report.uptime_str,
                        "current_watts": report.current_watts,
                        "session_kwh": report.session_kwh,
                        "session_co2_g": report.session_co2_g,
                        "grid_intensity": report.grid_intensity,
                        "grid_region": report.grid_region,
                        "avg_cpu": report.avg_cpu,
                        "peak_cpu": report.peak_cpu,
                        "avg_memory_mb": report.avg_memory_mb,
                        "peak_memory_mb": report.peak_memory_mb,
                        "green_score": report.green_score,
                        "green_grade": report.green_grade,
                        "seagreen_rating": report.seagreen_rating,
                        "component_breakdown": report.component_breakdown,
                        "top_consumers": report.top_consumers,
                        "is_green": report.pid in green_processes,
                        "cpu_usage_pct": current_cpu
                    }
                except Exception as e:
                    report_data = {"error": str(e)}
            
            self.wfile.write(json.dumps(report_data).encode('utf-8'))
            return
            
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        if self.path.startswith('/api/green/'):
            try:
                pid = int(self.path.split('/')[-1])
                green_mode_enable(pid)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "pid": pid, "is_green": True}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))
            return
            
        elif self.path.startswith('/api/ungreen/'):
            try:
                pid = int(self.path.split('/')[-1])
                green_mode_disable(pid)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "pid": pid, "is_green": False}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))
            return
            
        elif self.path.startswith('/api/kill/'):
            try:
                pid = int(self.path.split('/')[-1])
                proc = psutil.Process(pid)
                proc.terminate()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "pid": pid}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))
            return
            
        else:
            self.send_error(404, "Endpoint Not Found")

# Beautiful, light-themed luxury editorial layout matching Serene Interactive
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Seagreen by Serene Interactive | Energy & Carbon Intelligence</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #f4f7f6;
            --panel-bg: rgba(255, 255, 255, 0.75);
            --border-color: rgba(61, 139, 111, 0.12);
            --border-hover: rgba(61, 139, 111, 0.28);
            --accent-green: #3d8b6f;
            --leaf-green: #2e7d5c;
            --text-color: #12271f;
            --text-dim: #5c756b;
            --danger: #d32f2f;
            --transition: all 0.35s cubic-bezier(0.25, 0.8, 0.25, 1);
            --font-outfit: 'Outfit', sans-serif;
            --font-inter: 'Inter', sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--font-inter);
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(circle at 50% 30%, rgba(107, 201, 154, 0.12) 0%, transparent 60%);
            color: var(--text-color);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
        }

        header {
            padding: 1.1rem 2rem;
            backdrop-filter: blur(20px);
            background: rgba(255, 255, 255, 0.8);
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
        }

        .logo-section {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            transition: var(--transition);
        }
        
        .logo-section:hover {
            opacity: 0.85;
        }

        .brand-text {
            display: flex;
            flex-direction: column;
        }

        .brand-title {
            font-family: var(--font-outfit);
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--text-color);
            letter-spacing: -0.4px;
        }

        .brand-subtitle {
            font-size: 0.72rem;
            color: var(--text-dim);
            font-weight: 500;
            letter-spacing: 0.2px;
        }

        /* System Overview Welcome Screen */
        .system-overview {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            animation: fadeIn 0.4s ease-out;
        }
        
        .overview-header {
            margin-bottom: 0.5rem;
        }
        
        .overview-title {
            font-family: var(--font-outfit);
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-color);
            margin-bottom: 0.3rem;
        }
        
        .overview-subtitle {
            font-size: 0.88rem;
            color: var(--text-dim);
            line-height: 1.45;
        }
        
        .overview-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1.2rem;
        }
        
        @media (max-width: 768px) {
            .overview-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .overview-card {
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            transition: var(--transition);
        }
        
        .overview-card:hover {
            border-color: var(--border-hover);
            box-shadow: 0 6px 18px rgba(61, 139, 111, 0.04);
            transform: translateY(-2px);
        }
        
        .overview-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .overview-card-value {
            font-family: var(--font-outfit);
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-color);
        }
        
        .overview-card-desc {
            font-size: 0.78rem;
            color: var(--text-dim);
        }
        
        .guide-box {
            background: rgba(61, 139, 111, 0.03);
            border: 1px solid rgba(61, 139, 111, 0.1);
            border-radius: 16px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .guide-title {
            font-family: var(--font-outfit);
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--accent-green);
        }
        
        .guide-text {
            font-size: 0.82rem;
            color: var(--text-dim);
            line-height: 1.5;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.65; }
            50% { transform: scale(1.15); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.65; }
        }

        .main-container {
            display: grid;
            grid-template-columns: 360px 1fr;
            gap: 2rem;
            padding: 2rem;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
            flex-grow: 1;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 1.5rem;
            backdrop-filter: blur(24px);
            box-shadow: 0 10px 30px rgba(18, 39, 31, 0.03);
            transition: var(--transition);
        }

        .panel:hover {
            border-color: var(--border-hover);
            box-shadow: 0 12px 36px rgba(18, 39, 31, 0.06);
        }

        .panel-title {
            font-family: var(--font-outfit);
            font-size: 1.15rem;
            font-weight: 600;
            color: var(--text-color);
            margin-bottom: 1.2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(61, 139, 111, 0.08);
            padding-bottom: 0.6rem;
        }

        /* Process Selector List */
        .process-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            max-height: calc(100vh - 270px);
            overflow-y: auto;
            padding-right: 0.2rem;
        }

        .process-list::-webkit-scrollbar {
            width: 4px;
        }
        .process-list::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 2px;
        }

        .process-card {
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 0.85rem 1.1rem;
            cursor: pointer;
            transition: var(--transition);
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 6px rgba(18, 39, 31, 0.01);
        }

        .process-card:hover, .process-card.active {
            background: linear-gradient(135deg, rgba(61, 139, 111, 0.08) 0%, rgba(107, 201, 154, 0.04) 100%);
            border-color: var(--accent-green);
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(61, 139, 111, 0.06);
        }

        .proc-info {
            display: flex;
            flex-direction: column;
            gap: 0.2rem;
            max-width: 70%;
        }

        .proc-name {
            font-weight: 600;
            font-size: 0.9rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-color);
        }

        .proc-pid-cmd {
            font-size: 0.75rem;
            color: var(--text-dim);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .proc-badge {
            font-size: 0.7rem;
            padding: 0.15rem 0.5rem;
            border-radius: 12px;
            font-weight: 600;
            background: #f0f7f3;
            border: 1px solid var(--border-color);
            color: var(--accent-green);
        }

        .proc-badge.green {
            background: #e8f8f0;
            border-color: #2ecc71;
            color: #27ae60;
        }

        /* Dashboard Details */
        .dashboard-grid {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .dashboard-grid.three-col {
            grid-template-columns: 1fr 1fr 1fr;
        }

        /* Metric Cards */
        .metric-card {
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 1.2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 12px rgba(18, 39, 31, 0.01);
        }

        .metric-label {
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--text-dim);
        }

        .metric-value {
            font-family: var(--font-outfit);
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--text-color);
        }

        .metric-value.highlight {
            color: var(--accent-green);
        }

        /* Green Score Dial */
        .green-score-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 1.5rem;
            background: linear-gradient(135deg, rgba(61, 139, 111, 0.04) 0%, rgba(255, 255, 255, 0.8) 100%);
            border-radius: 16px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 15px rgba(18, 39, 31, 0.01);
        }

        .score-circle {
            position: relative;
            width: 140px;
            height: 140px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.8rem;
        }

        .score-circle svg {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            transform: rotate(-90deg);
        }

        .score-circle circle {
            fill: none;
            stroke-width: 8;
            stroke-linecap: round;
        }

        .score-circle .bg {
            stroke: rgba(61, 139, 111, 0.08);
        }

        .score-circle .progress {
            stroke: var(--accent-green);
            stroke-dasharray: 440;
            stroke-dashoffset: 440;
            transition: stroke-dashoffset 1s ease-out;
        }

        .score-value {
            font-family: var(--font-outfit);
            font-size: 2.4rem;
            font-weight: 700;
            color: var(--text-color);
        }

        .rating-stars-container {
            display: flex;
            align-items: center;
            margin-top: 0.4rem;
            margin-bottom: 0.3rem;
        }

        .rating-text {
            font-weight: 600;
            font-size: 0.95rem;
            color: var(--accent-green);
        }

        /* Chart Panel */
        .chart-container {
            height: 240px;
            position: relative;
            width: 100%;
            margin-top: 0.5rem;
        }

        /* Breakdown Progress Bars */
        .progress-group {
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }

        .progress-item {
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--text-dim);
        }

        .progress-bar-bg {
            background: rgba(18, 39, 31, 0.05);
            height: 6px;
            border-radius: 3px;
            overflow: hidden;
        }

        .progress-bar {
            background: var(--accent-green);
            height: 100%;
            width: 0%;
            border-radius: 3px;
            transition: width 0.5s ease-out;
        }

        /* Action Buttons */
        .action-row {
            display: flex;
            gap: 1rem;
            margin-top: 1.5rem;
        }

        .btn {
            flex-grow: 1;
            padding: 0.75rem 1.5rem;
            border-radius: 20px;
            border: 1px solid var(--accent-green);
            background: transparent;
            color: var(--accent-green);
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            transition: var(--transition);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            font-family: inherit;
        }

        .btn:hover {
            background: var(--accent-green);
            color: white;
            box-shadow: 0 4px 12px rgba(61, 139, 111, 0.15);
        }

        .btn.btn-green {
            border-color: var(--accent-green);
            color: var(--accent-green);
        }
        .btn.btn-green:hover {
            background: var(--accent-green);
            color: white;
        }

        .btn.btn-danger {
            border-color: var(--danger);
            color: var(--danger);
        }
        .btn.btn-danger:hover {
            background: var(--danger);
            color: white;
            box-shadow: 0 4px 12px rgba(211, 47, 47, 0.2);
        }

        .placeholder-text {
            color: var(--text-dim);
            text-align: center;
            padding: 3rem;
            font-size: 0.9rem;
        }

        /* Search input */
        .search-bar {
            width: 100%;
            padding: 0.75rem 1.25rem;
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 24px;
            color: var(--text-color);
            font-family: inherit;
            font-size: 0.85rem;
            margin-bottom: 1.2rem;
            outline: none;
            transition: var(--transition);
            box-shadow: 0 2px 8px rgba(0,0,0,0.01);
        }

        .search-bar:focus {
            border-color: var(--accent-green);
            box-shadow: 0 0 10px rgba(61, 139, 111, 0.08);
        }

        /* Segment control for filters */
        .filter-segments {
            display: flex;
            background: rgba(0, 0, 0, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 2px;
            margin-bottom: 1rem;
        }

        .filter-segment {
            flex: 1;
            text-align: center;
            padding: 0.45rem 0;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            border-radius: 20px;
            color: var(--text-dim);
            transition: var(--transition);
        }

        .filter-segment.active {
            background: var(--accent-green);
            color: white;
            box-shadow: 0 3px 10px rgba(61, 139, 111, 0.15);
        }

        .filter-segment:hover:not(.active) {
            color: var(--text-color);
            background: rgba(0, 0, 0, 0.02);
        }

        /* Badge Generator Card */
        .badge-builder {
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(18, 39, 31, 0.01);
        }

        .badge-preview {
            display: flex;
            justify-content: center;
            align-items: center;
            background: #f8faf9;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            min-height: 50px;
        }

        .badge-input-group {
            display: flex;
            gap: 0.5rem;
        }

        .badge-input {
            flex-grow: 1;
            padding: 0.5rem;
            background: #f8faf9;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-color);
            font-family: inherit;
            font-size: 0.8rem;
            outline: none;
        }

        .badge-copy-btn {
            padding: 0.5rem 1rem;
            border-radius: 6px;
            background: var(--accent-green);
            border: none;
            color: white;
            font-weight: 600;
            font-size: 0.8rem;
            cursor: pointer;
            transition: var(--transition);
        }

        .badge-copy-btn:hover {
            background: var(--leaf-green);
        }

        /* Eco equivalents list */
        .eco-equivalents-list {
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
        }

        .eco-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
            padding: 0.5rem 0.75rem;
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-color);
        }

        .eco-label {
            display: flex;
            align-items: center;
            color: var(--text-dim);
            font-weight: 500;
        }

        .eco-val {
            font-weight: 700;
            color: var(--accent-green);
        }
    </style>
</head>
<body>
    <header>
        <div class="header-container">
            <div class="logo-section" style="cursor: pointer;" onclick="resetToSystemOverview()">
                <!-- Seagreen Custom Wave & Leaf Logo (resembling the 🌊 wave emoji cleanly) -->
                <svg class="sig-logo" viewBox="0 0 40 40" width="32" height="32" style="border-radius: 10px; background: linear-gradient(135deg, #e8f5ee 0%, #d2ebd9 100%); padding: 5px; box-shadow: 0 4px 12px rgba(61, 139, 111, 0.1);">
                    <path d="M6 26 C 14 26, 16 14, 22 14 C 27 14, 30 18, 34 18" fill="none" stroke="#2e7d5c" stroke-width="2.5" stroke-linecap="round"/>
                    <path d="M6 31 C 12 31, 15 20, 21 20 C 26 20, 29 24, 34 24" fill="none" stroke="#3d8b6f" stroke-width="2.5" stroke-linecap="round"/>
                    <circle cx="21" cy="9" r="1.5" fill="#3d8b6f"/>
                    <circle cx="25" cy="11" r="1" fill="#2e7d5c"/>
                </svg>
                <div class="brand-text">
                    <span class="brand-title">Seagreen</span>
                    <span class="brand-subtitle">Energy & Carbon Telemetry</span>
                </div>
            </div>
            
            <div class="header-status" style="display: flex; align-items: center; gap: 1rem;">
                <div class="status-indicator" style="display: flex; align-items: center; gap: 0.5rem; background: #e8f5f1; padding: 0.35rem 0.85rem; border-radius: 20px; border: 1px solid rgba(61, 139, 111, 0.15);">
                    <span style="width: 8px; height: 8px; background-color: #2ecc71; border-radius: 50%; display: inline-block; box-shadow: 0 0 8px #2ecc71; animation: pulse 2s infinite;"></span>
                    <span style="font-size: 0.8rem; font-weight: 600; color: #1e6b50;">Live Telemetry</span>
                </div>
                <div class="platform-badge" id="platformBadge" style="font-size: 0.75rem; font-weight: 600; color: var(--text-dim); background: rgba(0, 0, 0, 0.04); padding: 0.35rem 0.85rem; border-radius: 20px; border: 1px solid var(--border-color);">
                    System Host
                </div>
            </div>
        </div>
    </header>

    <div class="main-container">
        <!-- Sidebar -->
        <div class="panel">
            <div class="panel-title">Trackable Processes</div>
            <div class="filter-segments">
                <div class="filter-segment active" data-type="apps" onclick="setFilterType('apps')">Apps</div>
                <div class="filter-segment" data-type="dev" onclick="setFilterType('dev')">Dev</div>
                <div class="filter-segment" data-type="agents" onclick="setFilterType('agents')">Agents</div>
                <div class="filter-segment" data-type="all" onclick="setFilterType('all')">All</div>
            </div>
            <input type="text" id="search" class="search-bar" placeholder="Search processes..." oninput="renderProcessList()">
            <div class="process-list" id="processList">
                <div class="placeholder-text">Loading processes...</div>
            </div>
        </div>

        <!-- Detail Section -->
        <div class="panel" id="detailPanel">
            <div class="system-overview">
                <div class="overview-header">
                    <h2 class="overview-title">System Diagnostics</h2>
                    <p class="overview-subtitle">Real-time host monitoring. Select any active application, daemon, or developer tool from the sidebar to inspect granular energy telemetry and configure Green Mode throttling.</p>
                </div>
                
                <div class="overview-grid">
                    <div class="overview-card">
                        <div class="overview-card-header">
                            <span>Host CPU Utilization</span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-green);"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="15" x2="23" y2="15"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="15" x2="4" y2="15"></line></svg>
                        </div>
                        <div class="overview-card-value" id="sysCpuVal">-- %</div>
                        <div class="overview-card-desc">Average across all logical processors</div>
                    </div>
                    
                    <div class="overview-card">
                        <div class="overview-card-header">
                            <span>System Memory Load</span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #2980b9;"><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h2"></path><path d="M12 9V3"></path><path d="M18 18h2a2 2 0 0 0 2-2v-5a2 2 0 0 0-2-2h-2"></path><path d="M12 15V21"></path><path d="M6 9v6h12V9H6z"></path></svg>
                        </div>
                        <div class="overview-card-value" id="sysRamVal">-- %</div>
                        <div class="overview-card-desc">Physical virtual memory utilization</div>
                    </div>
                    
                    <div class="overview-card">
                        <div class="overview-card-header">
                            <span>Trackable Processes</span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-dim);"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>
                        </div>
                        <div class="overview-card-value" id="sysProcsVal">--</div>
                        <div class="overview-card-desc">Active tasks scanned on system host</div>
                    </div>
                    
                    <div class="overview-card">
                        <div class="overview-card-header">
                            <span>Green Optimizations</span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #27ae60;"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                        </div>
                        <div class="overview-card-value" id="sysGreenVal" style="color: #27ae60;">--</div>
                        <div class="overview-card-desc">Processes running in throttled Green Mode</div>
                    </div>
                </div>
                
                <div class="guide-box">
                    <span class="guide-title">How to monitor and optimize:</span>
                    <p class="guide-text">Select any process card in the left sidebar. Seagreen will hook into the process's runtime telemetry to graph power draw, compute active carbon footprints using local grid multipliers, and generate embedding badges. Clicking "Enable Green Mode" will apply dynamic task suspension thresholds to reduce active SoC power draw.</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let processes = [];
        let activePid = null;
        let updateInterval = null;
        let wattageHistory = [];
        let cpuHistory = [];
        let labelsHistory = [];
        let myChart = null;
        let activeFilterType = 'apps';

        async function fetchProcesses() {
            try {
                const res = await fetch(`/api/processes?type=${activeFilterType}`);
                processes = await res.json();
                renderProcessList();
            } catch (err) {
                console.error("Error fetching processes:", err);
            }
        }

        function setFilterType(type) {
            activeFilterType = type;
            document.querySelectorAll('.filter-segment').forEach(el => {
                if (el.dataset.type === type) {
                    el.classList.add('active');
                } else {
                    el.classList.remove('active');
                }
            });
            fetchProcesses();
        }

        function renderProcessList() {
            const list = document.getElementById('processList');
            const searchVal = document.getElementById('search').value.toLowerCase();
            list.innerHTML = '';

            const filtered = processes.filter(p => 
                p.name.toLowerCase().includes(searchVal) || 
                p.app_name.toLowerCase().includes(searchVal) ||
                p.pid.toString().includes(searchVal)
            );

            if (filtered.length === 0) {
                list.innerHTML = '<div class="placeholder-text">No processes found</div>';
                return;
            }

            filtered.forEach(p => {
                const isSelected = p.pid === activePid;
                const card = document.createElement('div');
                card.className = `process-card ${isSelected ? 'active' : ''}`;
                card.onclick = () => selectProcess(p.pid);

                // Add small badge if process is green-mode active
                let badgeHtml = '';
                if (p.is_green) {
                    badgeHtml = `<span class="proc-badge green">GREEN</span>`;
                } else if (p.is_agent) {
                    badgeHtml = `<span class="proc-badge">AGENT</span>`;
                }

                card.innerHTML = `
                    <div class="proc-info">
                        <span class="proc-name" title="${p.app_name}">${p.app_name}</span>
                        <span class="proc-pid-cmd">PID: ${p.pid} | ${p.name}</span>
                    </div>
                    ${badgeHtml}
                `;
                list.appendChild(card);
            });
        }

        function selectProcess(pid) {
            if (activePid === pid) return;
            activePid = pid;
            
            // Reset state
            wattageHistory = [];
            cpuHistory = [];
            labelsHistory = [];
            myChart = null;

            // Highlight selected in sidebar list
            document.querySelectorAll('.process-card').forEach(card => {
                card.classList.remove('active');
            });
            
            renderProcessList();

            // Clear previous interval if any
            if (updateInterval) clearInterval(updateInterval);

            // Fetch immediately, then setup interval
            fetchTrackData();
            updateInterval = setInterval(fetchTrackData, 1500);
        }

        async function fetchTrackData() {
            if (!activePid) return;
            try {
                const res = await fetch(`/api/track/${activePid}`);
                const data = await res.json();
                if (data.error) {
                    console.error("Tracking error:", data.error);
                    if (updateInterval) clearInterval(updateInterval);
                    renderErrorPanel(data.error, activePid);
                    return;
                }
                
                // Add telemetry history
                const now = new Date();
                const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                
                labelsHistory.push(timeStr);
                wattageHistory.push(data.current_watts);
                cpuHistory.push(data.cpu_usage_pct);

                // Keep only last 25 entries
                if (labelsHistory.length > 25) {
                    labelsHistory.shift();
                    wattageHistory.shift();
                    cpuHistory.shift();
                }

                renderDashboard(data);
                updateChart();
            } catch (err) {
                console.error("Error fetching tracker data:", err);
            }
        }

        function renderErrorPanel(error, pid) {
            const panel = document.getElementById('detailPanel');
            let resolution = "Try selecting a user-space application from the sidebar, or search for a specific process you launched.";
            if (error.toLowerCase().includes("access is denied") || error.toLowerCase().includes("accessdenied") || error.toLowerCase().includes("winerror 5")) {
                resolution = "This is a protected system process. To monitor it, please restart the Seagreen terminal daemon as an Administrator (or root on Linux).";
            } else if (error.toLowerCase().includes("no such process") || error.toLowerCase().includes("nosuchprocess")) {
                resolution = "The process has terminated or was closed before monitoring could attach. Please select another active process.";
            }
            
            panel.innerHTML = `
                <div class="system-overview" style="max-width: 600px; margin: 4rem auto; text-align: center;">
                    <div style="background: #fff5f5; border: 1px solid #ffcccc; border-radius: 16px; padding: 2.5rem; display: flex; flex-direction: column; align-items: center; gap: 1.2rem; box-shadow: 0 4px 12px rgba(211, 47, 47, 0.05);">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#d32f2f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                        </svg>
                        <h2 class="overview-title" style="color: #d32f2f; margin: 0;">Monitoring Restricted</h2>
                        <p style="font-size: 0.88rem; color: var(--text-dim); line-height: 1.5; margin: 0;">
                            Could not attach energy telemetry hook to <strong>PID ${pid}</strong>.
                        </p>
                        <div style="background: rgba(0, 0, 0, 0.03); padding: 0.75rem 1rem; border-radius: 8px; font-family: monospace; font-size: 0.8rem; color: #555; text-align: left; width: 100%; word-break: break-all;">
                            ${error}
                        </div>
                        <p style="font-size: 0.85rem; color: var(--text-color); font-weight: 500; line-height: 1.4; margin-top: 0.5rem;">
                            💡 ${resolution}
                        </p>
                        <button class="btn btn-secondary" onclick="resetToSystemOverview()" style="margin-top: 0.5rem; padding: 0.5rem 1.5rem; border-radius: 20px; font-weight: 600; cursor: pointer;">
                            Return to System Overview
                        </button>
                    </div>
                </div>
            `;
        }

        function updateChart() {
            const canvas = document.getElementById('wattageChart');
            if (!canvas) return;

            if (!myChart) {
                const ctx = canvas.getContext('2d');
                
                // Gradients
                const wattGrad = ctx.createLinearGradient(0, 0, 0, 200);
                wattGrad.addColorStop(0, 'rgba(61, 139, 111, 0.22)');
                wattGrad.addColorStop(1, 'rgba(61, 139, 111, 0.00)');
                
                const cpuGrad = ctx.createLinearGradient(0, 0, 0, 200);
                cpuGrad.addColorStop(0, 'rgba(41, 128, 185, 0.12)');
                cpuGrad.addColorStop(1, 'rgba(41, 128, 185, 0.00)');

                myChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labelsHistory,
                        datasets: [
                            {
                                label: 'Power Draw (Watts)',
                                data: wattageHistory,
                                borderColor: '#3d8b6f',
                                backgroundColor: wattGrad,
                                fill: true,
                                tension: 0.4,
                                borderWidth: 2.5,
                                pointRadius: 0,
                                pointHoverRadius: 4
                            },
                            {
                                label: 'CPU Usage (%)',
                                data: cpuHistory,
                                borderColor: '#2980b9',
                                backgroundColor: cpuGrad,
                                fill: true,
                                tension: 0.4,
                                borderWidth: 1.5,
                                borderDash: [4, 4],
                                pointRadius: 0,
                                pointHoverRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                grid: {
                                    color: 'rgba(18, 39, 31, 0.04)'
                                },
                                ticks: {
                                    color: '#5c756b',
                                    font: {
                                        family: 'Outfit'
                                    }
                                }
                            },
                            x: {
                                grid: {
                                    color: 'rgba(18, 39, 31, 0.04)'
                                },
                                ticks: {
                                    color: '#5c756b',
                                    font: {
                                        family: 'Outfit'
                                    }
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#12271f',
                                    font: {
                                        family: 'Inter',
                                        weight: 500
                                    }
                                }
                            }
                        }
                    }
                });
            } else {
                myChart.data.labels = labelsHistory;
                myChart.data.datasets[0].data = wattageHistory;
                myChart.data.datasets[1].data = cpuHistory;
                myChart.update('none'); // silent update
            }
        }

        function renderDashboard(data) {
            const panel = document.getElementById('detailPanel');
            
            // Build dynamic lists/breakdowns
            let breakdownHtml = '';
            if (data.component_breakdown) {
                Object.entries(data.component_breakdown).forEach(([k, v]) => {
                    breakdownHtml += `
                        <div class="progress-item">
                            <div class="progress-header">
                                <span>${k}</span>
                                <span>${v}%</span>
                            </div>
                            <div class="progress-bar-bg">
                                <div class="progress-bar" style="width: ${v}%"></div>
                            </div>
                        </div>
                    `;
                });
            }

            // Equivalents
            const charges = (data.session_co2_g / 8.3).toFixed(1);
            const driving = (data.session_co2_g / 404).toFixed(3);
            const treeHours = (data.session_co2_g / 0.907).toFixed(1);

            const greenModeText = data.is_green ? 'Disable Green Mode' : 'Enable Green Mode';
            const greenModeAction = data.is_green ? `toggleGreen(${data.pid}, false)` : `toggleGreen(${data.pid}, true)`;

            // Compute badge properties
            let badgeColor = 'orange';
            if (data.green_score >= 85) badgeColor = 'brightgreen';
            else if (data.green_score >= 70) badgeColor = 'green';
            else if (data.green_score >= 50) badgeColor = 'yellowgreen';
            else if (data.green_score >= 35) badgeColor = 'yellow';
            
            const badgeMarkdown = `[![Seagreen Rating](https://img.shields.io/badge/Seagreen%20Rating-${data.green_grade}%20(${Math.round(data.green_score)}%25)-${badgeColor})](https://github.com/serene-interactive/Seagreen)`;
            const badgeImageSrc = `https://img.shields.io/badge/Seagreen%20Rating-${data.green_grade}%20(${Math.round(data.green_score)}%25)-${badgeColor}`;

            // Clean rating (removing emojis for web GUI representation)
            const cleanRating = data.seagreen_rating.replace(/[🌱🍂]/g, '').trim();
            const ratingLower = cleanRating.toLowerCase();
            let leafCount = 0;
            if (ratingLower.includes('excellent')) leafCount = 3;
            else if (ratingLower.includes('good')) leafCount = 2;
            else if (ratingLower.includes('fair')) leafCount = 1;

            let leavesSvg = '';
            for (let i = 0; i < 3; i++) {
                const filled = i < leafCount;
                const fillClr = filled ? '#3d8b6f' : 'transparent';
                leavesSvg += `
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="${fillClr}" stroke="#3d8b6f" stroke-width="2" style="margin: 0 2px;">
                        <path d="M17 8C8 10 9 21 9 21s11-1 12-10c.5-4.5-2.5-4.5-4-3zm-8 4c0-2.5 1.5-4.5 4-5.5-2.5 0-5 1.5-5 4 0 1 .5 1.5 1 1.5z"/>
                    </svg>
                `;
            }

            // We render the structure only if not already initialized
            const needsStructure = !document.getElementById('wattageChart');
            if (needsStructure) {
                panel.innerHTML = `
                    <div class="panel-title">
                        <span id="headerTitle">Monitoring: ${data.app_name} (PID ${data.pid})</span>
                        <span id="headerRuntime" style="font-size: 0.85rem; font-weight: 500; color: var(--text-dim); text-transform: uppercase;">${data.runtime}</span>
                    </div>

                    <div class="dashboard-grid">
                        <!-- Column 1: Core Metrics -->
                        <div style="display: flex; flex-direction: column; gap: 1rem;">
                            <div class="metric-card">
                                <span class="metric-label">Current Power Draw</span>
                                <span class="metric-value highlight" id="valWatts">${data.current_watts.toFixed(2)} W</span>
                            </div>
                            <div class="metric-card">
                                <span class="metric-label">Session Energy</span>
                                <span class="metric-value" id="valKwh">${data.session_kwh.toFixed(3)} kWh</span>
                            </div>
                            <div class="metric-card">
                                <span class="metric-label">Carbon Footprint</span>
                                <span class="metric-value" style="color: #e67e22;" id="valCo2">${data.session_co2_g.toFixed(1)} g CO2</span>
                            </div>
                            <div class="metric-card">
                                <span class="metric-label">Grid Region</span>
                                <span class="metric-value" style="font-size: 1.1rem; text-align: right;" id="valGrid">${data.grid_region}</span>
                            </div>
                        </div>

                        <!-- Column 2: Green Score & Performance -->
                        <div class="green-score-container">
                            <div class="score-circle">
                                <svg>
                                    <circle class="bg" cx="70" cy="70" r="60"></circle>
                                    <circle class="progress" id="progressCircle" cx="70" cy="70" r="60"></circle>
                                </svg>
                                <div class="score-value" id="valScore">${Math.round(data.green_score)}</div>
                            </div>
                            <div class="rating-stars-container" id="valStars">
                                ${leavesSvg}
                            </div>
                            <div class="rating-text" id="valRating">${cleanRating}</div>
                            <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 0.3rem;" id="valUptime">Uptime: ${data.uptime_str}</div>
                        </div>
                    </div>

                    <!-- Real-Time Chart Row -->
                    <div class="panel" style="margin-bottom: 1.5rem; background: #ffffff; border-color: var(--border-color); box-shadow: none;">
                        <div class="panel-title" style="font-size: 0.95rem; margin-bottom: 0.5rem; border: none; padding: 0;">Real-Time Resource Metrics</div>
                        <div class="chart-container">
                            <canvas id="wattageChart"></canvas>
                        </div>
                    </div>

                    <div class="dashboard-grid three-col">
                        <!-- Column 1: Component Breakdown -->
                        <div class="panel" style="background: #ffffff; border-color: var(--border-color); box-shadow: none;">
                            <div class="panel-title" style="font-size: 0.95rem; margin-bottom: 0.8rem; border: none; padding: 0;">Energy Breakdown</div>
                            <div class="progress-group" id="containerBreakdown">
                                ${breakdownHtml || '<div class="placeholder-text">No breakdown available</div>'}
                            </div>
                        </div>

                        <!-- Column 2: Environmental Impact -->
                        <div class="panel" style="background: #ffffff; border-color: var(--border-color); box-shadow: none;">
                            <div class="panel-title" style="font-size: 0.95rem; margin-bottom: 0.8rem; border: none; padding: 0;">Eco-Equivalents</div>
                            <div class="eco-equivalents-list">
                                <div class="eco-item">
                                    <span class="eco-label">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect><line x1="12" y1="18" x2="12.01" y2="18"></line></svg>
                                        Smartphone Charges
                                    </span>
                                    <span class="eco-val" id="valCharges">${charges}</span>
                                </div>
                                <div class="eco-item">
                                    <span class="eco-label">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"></path><circle cx="7" cy="17" r="2"></circle><path d="M9 17h6"></path><circle cx="17" cy="17" r="2"></circle></svg>
                                        Miles Driven (gas car)
                                    </span>
                                    <span class="eco-val" id="valDriving">${driving}</span>
                                </div>
                                <div class="eco-item">
                                    <span class="eco-label">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M12 2L3 9h18L12 2z"></path><path d="M12 8L5 14h14L12 8z"></path><path d="M12 14L7 20h10L12 14z"></path><path d="M12 20v2"></path></svg>
                                        Tree Absorption Hours
                                    </span>
                                    <span class="eco-val" id="valTreeHours">${treeHours} hrs</span>
                                </div>
                            </div>
                        </div>

                        <!-- Column 3: Badge Builder -->
                        <div class="panel" style="background: #ffffff; border-color: var(--border-color); box-shadow: none;">
                            <div class="panel-title" style="font-size: 0.95rem; margin-bottom: 0.8rem; border: none; padding: 0;">README Carbon Badge</div>
                            <div class="badge-builder">
                                <div class="badge-preview">
                                    <img id="badgeImage" src="${badgeImageSrc}" alt="Badge Preview">
                                </div>
                                <div class="badge-input-group">
                                    <input type="text" id="badgeMarkdownText" class="badge-input" readOnly value="${badgeMarkdown}">
                                    <button class="badge-copy-btn" onclick="copyBadgeMarkdown()">Copy</button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Control Buttons -->
                    <div class="action-row" id="containerActions">
                        <button class="btn btn-green" id="btnToggleGreen" onclick="${greenModeAction}">${greenModeText}</button>
                        <button class="btn btn-danger" onclick="killProcess(${data.pid})">Kill Process</button>
                    </div>
                `;
            } else {
                // Update only mutable fields
                document.getElementById('headerTitle').innerText = `Monitoring: ${data.app_name} (PID ${data.pid})`;
                document.getElementById('headerRuntime').innerText = data.runtime;
                document.getElementById('valWatts').innerText = `${data.current_watts.toFixed(2)} W`;
                document.getElementById('valKwh').innerText = `${data.session_kwh.toFixed(3)} kWh`;
                document.getElementById('valCo2').innerText = `${data.session_co2_g.toFixed(1)} g CO2`;
                document.getElementById('valGrid').innerText = data.grid_region;
                document.getElementById('valScore').innerText = Math.round(data.green_score);
                document.getElementById('valRating').innerText = cleanRating;
                document.getElementById('valStars').innerHTML = leavesSvg;
                document.getElementById('valUptime').innerText = `Uptime: ${data.uptime_str}`;
                
                // Circle Progress
                const circle = document.getElementById('progressCircle');
                if (circle) {
                    // Radius = 60, circumference = 2 * PI * 60 = 377
                    circle.style.strokeDashoffset = 377 - (377 * data.green_score / 100);
                }

                // Breakdown list
                document.getElementById('containerBreakdown').innerHTML = breakdownHtml || '<div class="placeholder-text">No breakdown available</div>';
                
                // Equivalents
                document.getElementById('valCharges').innerText = charges;
                document.getElementById('valDriving').innerText = driving;
                document.getElementById('valTreeHours').innerText = `${treeHours} hrs`;

                // Badge Builder
                document.getElementById('badgeImage').src = badgeImageSrc;
                document.getElementById('badgeMarkdownText').value = badgeMarkdown;

                // Action buttons
                const btn = document.getElementById('btnToggleGreen');
                btn.innerText = greenModeText;
                btn.setAttribute('onclick', greenModeAction);
            }
        }

        function copyBadgeMarkdown() {
            const copyText = document.getElementById("badgeMarkdownText");
            copyText.select();
            copyText.setSelectionRange(0, 99999); // For mobile devices
            navigator.clipboard.writeText(copyText.value);
            alert("Markdown copied to clipboard! Paste into your README.md");
        }

        async function toggleGreen(pid, enable) {
            const endpoint = enable ? `/api/green/${pid}` : `/api/ungreen/${pid}`;
            try {
                const res = await fetch(endpoint, { method: 'POST' });
                const result = await res.json();
                if (result.success) {
                    fetchProcesses(); // Refresh sidebar green status
                    fetchTrackData(); // Refresh current display
                }
            } catch (err) {
                console.error("Error toggling green mode:", err);
            }
        }

        async function killProcess(pid) {
            if (!confirm(`Are you sure you want to terminate process ${pid}?`)) return;
            try {
                const res = await fetch(`/api/kill/${pid}`, { method: 'POST' });
                const result = await res.json();
                if (result.success) {
                    alert(`Process ${pid} terminated.`);
                    resetToSystemOverview();
                    fetchProcesses();
                }
            } catch (err) {
                console.error("Error killing process:", err);
            }
        }

        async function fetchSystemStats() {
            if (activePid) return;
            try {
                const res = await fetch('/api/system');
                const data = await res.json();
                
                const cpuEl = document.getElementById('sysCpuVal');
                const ramEl = document.getElementById('sysRamVal');
                const procsEl = document.getElementById('sysProcsVal');
                const greenEl = document.getElementById('sysGreenVal');
                const platformEl = document.getElementById('platformBadge');
                
                if (cpuEl) cpuEl.innerText = `${data.cpu_percent.toFixed(1)} %`;
                if (ramEl) ramEl.innerText = `${data.ram_percent.toFixed(1)} %`;
                if (procsEl) procsEl.innerText = data.total_processes;
                if (greenEl) greenEl.innerText = data.green_count;
                if (platformEl && data.platform) {
                    const platformName = data.platform.charAt(0).toUpperCase() + data.platform.slice(1);
                    platformEl.innerText = `${platformName} Host`;
                }
            } catch (err) {
                console.error("Error fetching system stats:", err);
            }
        }

        function resetToSystemOverview() {
            activePid = null;
            if (updateInterval) clearInterval(updateInterval);
            
            // Remove active classes in sidebar
            document.querySelectorAll('.process-card').forEach(card => card.classList.remove('active'));
            
            const panel = document.getElementById('detailPanel');
            panel.innerHTML = `
                <div class="system-overview">
                    <div class="overview-header">
                        <h2 class="overview-title">System Diagnostics</h2>
                        <p class="overview-subtitle">Real-time host monitoring. Select any active application, daemon, or developer tool from the sidebar to inspect granular energy telemetry and configure Green Mode throttling.</p>
                    </div>
                    
                    <div class="overview-grid">
                        <div class="overview-card">
                            <div class="overview-card-header">
                                <span>Host CPU Utilization</span>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-green);"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="15" x2="23" y2="15"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="15" x2="4" y2="15"></line></svg>
                            </div>
                            <div class="overview-card-value" id="sysCpuVal">-- %</div>
                            <div class="overview-card-desc">Average across all logical processors</div>
                        </div>
                        
                        <div class="overview-card">
                            <div class="overview-card-header">
                                <span>System Memory Load</span>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #2980b9;"><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h2"></path><path d="M12 9V3"></path><path d="M18 18h2a2 2 0 0 0 2-2v-5a2 2 0 0 0-2-2h-2"></path><path d="M12 15V21"></path><path d="M6 9v6h12V9H6z"></path></svg>
                            </div>
                            <div class="overview-card-value" id="sysRamVal">-- %</div>
                            <div class="overview-card-desc">Physical virtual memory utilization</div>
                        </div>
                        
                        <div class="overview-card">
                            <div class="overview-card-header">
                                <span>Trackable Processes</span>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-dim);"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>
                            </div>
                            <div class="overview-card-value" id="sysProcsVal">--</div>
                            <div class="overview-card-desc">Active tasks scanned on system host</div>
                        </div>
                        
                        <div class="overview-card">
                            <div class="overview-card-header">
                                <span>Green Optimizations</span>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #27ae60;"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                            </div>
                            <div class="overview-card-value" id="sysGreenVal" style="color: #27ae60;">--</div>
                            <div class="overview-card-desc">Processes running in throttled Green Mode</div>
                        </div>
                    </div>
                    
                    <div class="guide-box">
                        <span class="guide-title">How to monitor and optimize:</span>
                        <p class="guide-text">Select any process card in the left sidebar. Seagreen will hook into the process's runtime telemetry to graph power draw, compute active carbon footprints using local grid multipliers, and generate embedding badges. Clicking "Enable Green Mode" will apply dynamic task suspension thresholds to reduce active SoC power draw.</p>
                    </div>
                </div>
            `;
            fetchSystemStats();
        }

        // Initial setup
        fetchProcesses();
        fetchSystemStats();
        setInterval(fetchProcesses, 5000); // Poll process list
        setInterval(fetchSystemStats, 2000); // Poll system stats
    </script>
</body>
</html>
"""


def start_web_server(port: int = 8080):
    """Start the Seagreen Web Dashboard server on a background thread"""
    server_address = ('', port)
    
    # Allow port reuse to prevent Address Already in Use errors during rapid restarts
    class ReusableTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        
    try:
        httpd = ReusableTCPServer(server_address, SeagreenHTTPRequestHandler)
    except Exception as e:
        print(f"Error starting web server on port {port}: {e}")
        return None
        
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    return httpd

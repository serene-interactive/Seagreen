# 🌊 Seagreen

**Live process energy & carbon monitoring for developers.**

[![Made by Serene Interactive, Global](https://img.shields.io/badge/Made%20by-Serene%20Interactive-3d8b6f?style=for-the-badge)](https://sereneinteractive.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-4a9b6e?style=for-the-badge)](LICENSE)

A real-time Python process monitor that tracks energy consumption, carbon footprint, and efficiency. Built with 💚 by [Serene Interactive, Global](https://sereneinteractive.com).


## 🌿 Features

- 🖥️ **Interactive Terminal UI** - Slash commands in your terminal (`/list`, `/track`, `/help`)
- 🌊 **Real-time Monitoring** - Track CPU, memory, and energy usage with live updates
- ⚡ **Energy Tracking** - Estimate power consumption and CO2 emissions per process
- 🍃 **Green Score** - Get a 0-100 efficiency rating with eco equivalents
- 🔍 **Window Titles** - Shows actual app names (not just process names) for easy identification
- 📋 **Command Line Filtering** - `/list chrome` filters processes instantly
- 🎨 **Beautiful Design** - Soothing ocean-green colors matching sereneinteractive.com
- 🔒 **Privacy First** - All local processing, no data leaves your machine

## 🚀 Installation

```bash
git clone https://github.com/serene-interactive/seagreen.git
cd seagreen
pip install .
```

For development (editable install):

```bash
pip install -e .
```

## 🖥️ Usage

Launch Seagreen and use slash commands to interact:

```bash
seagreen
```

### Commands

| Command | Description |
|---------|-------------|
| `/list [filter]` | Show trackable processes (optional name filter) |
| `/track <pid> [seconds]` | Monitor a process |
| `/agent-track <pid> [seconds]` | Monitor with real-time energy TUI |
| `/agents` | Detect and list agent processes |
| `/agent-monitor` | Live dashboard for all running agents |
| `/green <pid>` | Put process in low-power green mode |
| `/ungreen <pid>` | Restore process from green mode |
| `/green-list` | Show processes in green mode |
| `/kill <pid>` | Terminate a process |
| `/help` | Show all available commands |
| `/quit` | Exit Seagreen |

### Quick Start

```
$ seagreen

🌊 Seagreen - Live Process Energy Monitor

Type /help for commands

seagreen> /list
  PID    Application                Type    Command
 ────────────────────────────────────────────────────
  1234   Python: myapp.py           DEV     python myapp.py
  5678   Python: server.py          DEV     python server.py

seagreen> /track 1234 30
Monitoring PID 1234 for 30s...

Seagreen Process Energy Report
==================================================
  Process    Python: myapp.py
  PID        1234
  Runtime    python
  Duration   30.0s

Energy Consumption:
  Current Power     2.50 W
  Session Energy    0.021 kWh
  Carbon Estimate   9.9 g CO2

Efficiency Metrics:
  Average CPU      8.2%
  Peak CPU         15.0%
  Average Memory   45.2 MB
  Green Score      92/100
  Rating           🌿🌿🌿 Excellent
```

## 🌊 How It Works

Seagreen monitors your process and calculates:

- **Energy Consumption**: Power draw estimated from CPU utilization (watts → kWh)
- **Carbon Footprint**: CO2 emissions based on your regional grid intensity
- **Green Score**: 0-100 efficiency rating combining power, CPU, and memory
- **Eco Rating**: 🌿🌿🌿 Excellent | 🌿🌿 Good | 🌿 Fair | 🍂 Needs Work
- **Relatable Equivalents**: Smartphone charges, Google searches, streaming minutes, etc.

### Energy Estimation

```
Watts = idle_power + (max_power - idle_power) × (cpu_percent / 100)
kWh = watts × (duration_seconds / 3600)
CO2 = kWh × grid_intensity (g CO2/kWh)
```

## 🎨 The Seagreen Palette

Our colors match the [Serene Interactive website](https://sereneinteractive.com):

| Color | Hex | Usage |
|-------|-----|-------|
| Serene Green | `#3d8b6f` | Primary brand |
| Ocean | `#2d6b5d` | Headers |
| Leaf | `#6bc99a` | Accents |
| Mist | `#e8f5f0` | Backgrounds |

## 🌍 Why Seagreen?

At Serene Interactive, we believe that the most powerful code is also the most efficient. Seagreen helps developers visualize "Computational Waste" and promotes a greener digital ecosystem.

> *"The greenest code is efficient code."* 🌿

## 📋 Requirements

- Python 3.8+
- psutil
- rich

## 🤝 Contributing

We welcome contributions! This is our first open-source project, and we're excited to grow it with the community.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/cool-thing`)
3. Commit your changes (`git commit -m 'Add cool thing'`)
4. Push to the branch (`git push origin feature/cool-thing`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🌊 About Serene Interactive

**Serene Interactive, Global (SiG)** is an interactive media and technology company supporting digital creators and communities. We believe smart technology should never come at the cost of your privacy or the future.

- 🌐 [sereneinteractive.com](https://sereneinteractive.com)
- 💬 [Discord](https://discord.gg/rosy)

---

<p align="center">
  <strong>🌊 Built with 💚 by Serene Interactive, Global 🌿</strong>
</p>

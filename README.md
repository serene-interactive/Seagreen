# 🌊 Seagreen

**Interactive process tracking for developers.**

[![Made by Serene Interactive, Global](https://img.shields.io/badge/Made%20by-Serene%20Interactive-3d8b6f?style=for-the-badge)](https://sereneinteractive.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-4a9b6e?style=for-the-badge)](LICENSE)

An interactive Python process monitor with a beautiful terminal UI. Built with 💚 by [Serene Interactive, Global](https://sereneinteractive.com).


## 🌿 Features

- 🖥️ **Interactive Terminal UI** - Slash commands in your terminal (`/list`, `/track`, `/help`)
- 🌊 **Real-time Monitoring** - Track CPU and memory usage with live updates
- 🍃 **Efficiency Scoring** - Get a Seagreen Rating (🌿🌿🌿 to 🍂) based on resource usage
- 🎨 **Beautiful Design** - Soothing ocean-green colors matching sereneinteractive.com
- ⚡ **Lightweight** - Minimal overhead, zero AI dependencies
- 🔒 **Privacy First** - All local processing, no data leaves your machine

## 🚀 Installation

```bash
git clone https://github.com/serene-interactive/seagreen.git
cd seagreen
pip install -r requirements.txt
```

## 🖥️ Usage

Launch Seagreen and use slash commands to interact:

```bash
python seagreen.py
```

### Commands

| Command | Description |
|---------|-------------|
| `/list` | Show Python processes you can track |
| `/track <pid> [seconds]` | Monitor a process (default: 10s) |
| `/help` | Show all available commands |
| `/quit` | Exit Seagreen |

### Quick Start

```
$ python seagreen.py

🌊 Seagreen - Interactive Process Monitor

Type /help for commands or /list to see processes

seagreen> /list
┌────────┬─────────────────┬────────┐
│ PID    │ Name            │ Memory │
├────────┼─────────────────┼────────┤
│ 12345  │ python3 myapp   │ 45 MB  │
│ 12346  │ python3 server  │ 128 MB │
└────────┴─────────────────┴────────┘

seagreen> /track 12345 30
🔍 Tracking process 12345 for 30 seconds...

📊 Seagreen Report
━━━━━━━━━━━━━━━━
Duration: 30.0s
Avg CPU:  12.5%
Avg RAM:  45.2 MB
Efficiency Score: 87/100 🌿🌿🌿
```

## 🌊 How It Works

Seagreen monitors your process and calculates:

- **CPU-Seconds**: Total CPU time consumed
- **Memory Efficiency**: Average vs peak usage
- **Seagreen Score**: 0-100 efficiency rating
- **Eco Rating**: 🌿🌿🌿 Excellent | 🌿🌿 Good | 🌿 Fair | 🍂 Needs Work

### The Formula

```
Efficiency Score = 100 - (avg_cpu% × duration_minutes)
```

Lower CPU usage over shorter time = higher efficiency!

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

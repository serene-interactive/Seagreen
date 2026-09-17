# Measurement

## Sources

| Data | Source | Scope |
| --- | --- | --- |
| Native Mac CPU | `proc_pidinfo`, converted from Mach ticks; host CPU tick deltas | Process or all cores |
| Web CPU | psutil cumulative user/system CPU time deltas | Process; 100% per logical core |
| Memory | Resident process counters | Shared pages may be counted more than once |
| Native system memory | Active + wired + compressed pages | Not Activity Monitor memory pressure |
| Web system memory | Total minus available memory | OS-specific definition |
| Disk I/O | OS process byte counters | May be unavailable on protected processes |
| Mac battery power | Optional AppleSmartBattery voltage and signed discharge current | Whole-device battery discharge; unplugged only |
| Apple power file | Known `processor.combined_power` or `cpu_power` fields, mW | CPU/GPU/ANE combined or CPU only; Apple estimate |
| Linux power | Top-level RAPL package energy counters | CPU packages, not wall-socket power |

The interfaces never convert CPU percentage into watts. Per-process CPU, memory, and I/O are diagnostics, not direct energy attribution. Remote inference energy cannot be measured locally.

## Energy and comparisons

Energy is the trapezoidal integral of adjacent power readings, in Wh. Divide Wh by 1,000 for kWh. Gaps over 15 seconds, missing samples, counter decreases, and source changes add no energy. Coverage is recorded separately; incomplete energy totals are not extrapolated to fill missing time.

Comparisons require the same local device identifier, one matching power-source scope, matching completed-work units, and at least 90% coverage. Energy per unit is recorded Wh divided by completed work. Repeat baseline and changed workloads under similar conditions; an observed difference is not proof of causation. Lower instantaneous power may take longer and consume more total energy.

Sessions stop after two hours and auto-save approximately every 30 seconds. A crash may lose the most recent unsaved samples. History is local and can be deleted or exported explicitly.

## Optional Mac power file

The app does not run itself as root. On supported Apple silicon hardware, a user can run Apple's tool in Terminal:

```bash
sudo /usr/bin/powermetrics --samplers cpu_power,gpu_power -i 2000 -f plist -o /tmp/seagreen-power.plist
```

Use **Measurement → Connect power file** to select the output. Stop the Terminal sampler with Control-C when finished. Sampler availability and schemas vary by hardware and OS; unknown schemas are rejected. Files older than 10 seconds are ignored, and supported battery readings become the fallback. Only the most recent 1 MiB is read. Power files are never uploaded.

Apple describes powermetrics power as estimates, useful for optimization on the same device, not comparisons across different Macs. CPU/GPU/ANE readings exclude the display and other components. Battery sensor fields are optional and need validation on each supported MacBook family.

## Controls and privacy

The launcher starts a user-selected executable with literal arguments, without a shell. Windows requests below-normal priority and EcoQoS; errors are shown. macOS uses `/usr/sbin/taskpolicy -b`. Linux uses `nice -n 10`. Scheduling changes can affect performance and do not guarantee energy savings.

The Efficiency stop button targets only the launched process. Applications and the CLI also offer explicit quit and force-quit controls for current-user processes, with confirmation and PID/start-time validation. Native Mac apps receive their normal Quit request; Windows GUI processes receive WM_CLOSE; other processes receive SIGTERM. Force Quit sends SIGKILL on Unix or uses Windows process termination. Unsaved work can be lost. Seagreen, its ancestors, and known critical system/session processes are blocked. Children may continue independently; use a workload's own shutdown mechanism where available. Closing a browser tab does not stop the server or a job. Stopping the web server requests termination of its launched process. The Mac app prompts before quitting with a running job. No process is terminated automatically, and no process tree is killed recursively.

The web UI requires a per-launch bearer token for every API request. It binds only to IPv4 loopback and rejects foreign Host/Origin headers. Static assets are bundled; there are no third-party network requests. Exported recordings contain measurements and user-entered notes, so review them before sharing.

import SwiftUI
import AppKit

struct EfficiencyView: View {
    @EnvironmentObject var model: AppModel
    @State private var executable: URL?
    @State private var arguments = ""
    @State private var efficient = true
    @State private var confirmLaunch = false
    @State private var confirmStop = false
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Eyebrow(text: "Make room for what matters")
            Text("Put background work in its place.").font(.system(size: 32, design: .serif))
            Text("Launch a command-line task with macOS background scheduling. Useful for work that can yield to your foreground apps.").font(.system(size: 12)).foregroundStyle(Palette.muted)
        }
        Panel(title: "Efficiency launcher") {
            HStack {
                Image(systemName: "terminal").font(.system(size: 24, weight: .light)).foregroundStyle(Palette.green)
                VStack(alignment: .leading, spacing: 5) {
                    Text(executable?.lastPathComponent ?? "Choose a command-line executable").font(.system(size: 13, weight: .medium))
                    Text(executable?.path ?? "For scripts, select their interpreter and add the script as an argument.").font(.system(size: 11)).foregroundStyle(Palette.muted).textSelection(.enabled)
                }
                Spacer()
                Button("Choose file") {
                    let panel = NSOpenPanel(); panel.canChooseDirectories = false; panel.allowsMultipleSelection = false
                    if panel.runModal() == .OK { executable = panel.url }
                }.buttonStyle(SecondaryButton()).disabled(model.jobRunning)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Arguments · one per line, without shell quotes").font(.system(size: 11, weight: .medium))
                TextEditor(text: $arguments).font(.system(size: 12, design: .monospaced)).frame(height: 80).padding(8).background(Palette.paper, in: RoundedRectangle(cornerRadius: 8))
            }
            Toggle("Request background CPU and I/O scheduling", isOn: $efficient).toggleStyle(.switch).controlSize(.small)
            Text("macOS taskpolicy applies the policy to this job and its children. The job may take longer. Record standard and background runs to determine whether energy per completed task improves. No savings percentage is assumed.").font(.system(size: 12)).foregroundStyle(Palette.muted).lineSpacing(4)
            HStack {
                Tag(text: "No administrator access")
                Spacer()
                Button("Review & launch") { confirmLaunch = true }.buttonStyle(PrimaryButton()).disabled(executable == nil || model.jobRunning)
            }
        }
        Panel(title: "Job activity") {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text(model.jobName ?? "Ready when you are").font(.system(size: 15, weight: .medium))
                    Text(model.jobStatus).font(.system(size: 11)).foregroundStyle(Palette.muted)
                }
                Spacer()
                if model.jobRunning { Button("Stop launched process", role: .destructive) { confirmStop = true } }
            }
            if !model.jobOutput.isEmpty {
                ScrollView { Text(model.jobOutput).font(.system(size: 11, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }.frame(maxHeight: 180)
                Text("Most recent 32K characters of output. Jobs requiring interactive input are not supported.").font(.system(size: 10)).foregroundStyle(Palette.muted)
            }
        }
        Panel(title: "System power settings") {
            HStack {
                Text(model.sample?.lowPowerMode == true ? "macOS Low Power Mode is enabled." : "macOS Low Power Mode is not enabled.").font(.system(size: 12))
                Spacer()
                Button("Open Energy settings") { NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.battery")!) }.buttonStyle(SecondaryButton())
            }
            Text("Available settings depend on your Mac. Change system-wide policies in System Settings, where macOS shows the supported options.").font(.system(size: 11)).foregroundStyle(Palette.muted)
        }
        .confirmationDialog("Launch \(executable?.lastPathComponent ?? "this executable")?", isPresented: $confirmLaunch, titleVisibility: .visible) {
            Button("Launch job") {
                if let executable { model.launch(executable: executable, arguments: arguments.components(separatedBy: .newlines).filter { !$0.isEmpty }, efficient: efficient) }
            }
        } message: { Text("Runs the selected executable with your user permissions. Arguments are passed directly, without a shell. Only run programs you trust.") }
        .confirmationDialog("Stop the launched process?", isPresented: $confirmStop, titleVisibility: .visible) {
            Button("Request termination", role: .destructive) { model.stopJob() }
        } message: { Text("This requests termination of the process Seagreen launched. Independently running child processes may continue; use the job’s own shutdown mechanism when available.") }
    }
}

struct MeasurementView: View {
    @EnvironmentObject var model: AppModel
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Eyebrow(text: "Know what a number means")
            Text("Transparent by design.").font(.system(size: 33, design: .serif))
            Text("Sources, scope, and limitations stay attached to your data.").font(.system(size: 12)).foregroundStyle(Palette.muted)
        }
        Panel(title: "Power source") {
            HStack {
                VStack(alignment: .leading, spacing: 8) {
                    Text(model.sample?.power?.source.rawValue ?? "No live power source").font(.system(size: 19, design: .serif))
                    Text(model.sample?.power?.scope ?? model.sample?.battery.detail ?? "Waiting for a reading").font(.system(size: 12)).foregroundStyle(Palette.muted)
                    if let name = model.powerFileName { Text("Watching \(name)").font(.caption).foregroundStyle(Palette.muted) }
                }
                Spacer()
                Button("Connect power file") { model.choosePowerFile() }.buttonStyle(SecondaryButton()).disabled(model.active != nil)
                if model.powerFileName != nil { Button("Disconnect") { model.disconnectPowerFile() }.disabled(model.active != nil) }
            }
            Divider()
            Text("On supported MacBooks, battery voltage and discharge current provide whole-device battery power while unplugged. This is not wall-socket power or per-app energy. Desktop Macs and plugged-in laptops may have no battery power reading.").font(.system(size: 12)).foregroundStyle(Palette.muted).lineSpacing(4)
            Text("Optional: connect a live Apple powermetrics plist file. Seagreen recognizes Apple silicon CPU power or combined CPU/GPU/ANE power in milliwatts. Apple describes these values as estimates; they exclude other device components and are not comparable across different Macs.").font(.system(size: 12)).foregroundStyle(Palette.muted).lineSpacing(4)
            Text("To create a live file, run this yourself in Terminal (requires your administrator password):").font(.system(size: 11))
            Text("sudo /usr/bin/powermetrics --samplers cpu_power,gpu_power -i 2000 -f plist -o /tmp/seagreen-power.plist")
                .font(.system(size: 11, design: .monospaced)).textSelection(.enabled).padding(12).frame(maxWidth: .infinity, alignment: .leading).background(Palette.paper, in: RoundedRectangle(cornerRadius: 9))
            Text("Then connect /tmp/seagreen-power.plist above. Stop the Terminal command with Control-C when finished. Sampler availability varies by hardware. Files older than 10 seconds and unknown schemas are rejected; battery readings are used as a fallback when available.").font(.system(size: 11)).foregroundStyle(Palette.muted)
        }
        Panel(title: "What Seagreen measures") {
            description("CPU", "Counter differences over monotonic elapsed time. System CPU is normalized across all cores; application CPU uses 100% per logical core.")
            description("Memory & disk", "Resident memory and process disk-byte counters where macOS permits access. Working system memory is active + wired + compressed; this is not memory pressure.")
            description("Energy", "Adjacent power samples integrated into Wh. Sleep gaps, unavailable data, and source changes are excluded. Coverage is shown for every recording.")
            description("Privacy", "Monitoring and recordings remain on this Mac. No remote assets, analytics, account, or listening web server. Exporting is always explicit.")
        }
        Panel(title: "Monitoring") {
            HStack {
                Text("Sampling interval: 2 seconds · live chart: 5 minutes").font(.system(size: 12))
                Spacer()
                Button(model.paused ? "Resume monitoring" : "Pause monitoring") { model.paused.toggle() }.buttonStyle(SecondaryButton()).disabled(model.active != nil)
            }
            Text("Last collection: \(decimal(model.sample?.collectionMS)) ms. Recordings are saved in ~/Library/Application Support/Seagreen/Recordings. No automatic deletion; review and remove sessions in Experiments.").font(.system(size: 11)).foregroundStyle(Palette.muted)
            Text("Version 3.0.0 · local build").font(.system(size: 10, design: .monospaced)).foregroundStyle(Palette.muted)
        }
    }
    func description(_ title: String, _ body: String) -> some View {
        HStack(alignment: .top, spacing: 18) {
            Text(title).font(.system(size: 12, weight: .semibold)).frame(width: 100, alignment: .leading)
            Text(body).font(.system(size: 12)).foregroundStyle(Palette.muted).lineSpacing(4).frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

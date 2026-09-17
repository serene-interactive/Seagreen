import SwiftUI
import AppKit
import SeagreenCore

struct OverviewView: View {
    @EnvironmentObject var model: AppModel
    @State private var chartPower = false
    var body: some View {
        hero
        HStack(alignment: .top, spacing: 14) {
            MetricCard(label: "System CPU", value: decimal(model.sample?.cpuPercent), unit: "%", detail: "All logical cores · observed counters", icon: "cpu")
            MetricCard(label: "Working memory", value: decimal(model.sample.map { Double($0.memoryBytes) / 1_073_741_824 }), unit: "GB", detail: "Active + wired + compressed", icon: "memorychip")
            MetricCard(label: "Power", value: decimal(model.sample?.power?.watts), unit: "W", detail: model.sample?.power?.scope ?? "Connect a supported power source", icon: "bolt")
        }
        Panel {
            HStack {
                VStack(alignment: .leading, spacing: 5) {
                    Text("The last five minutes").font(.system(size: 18, weight: .medium, design: .serif))
                    Text(chartPower ? (model.sample?.power?.source.rawValue ?? "No power samples available") : "System utilization, sampled every two seconds").font(.system(size: 11)).foregroundStyle(Palette.muted)
                }
                Spacer()
                Picker("Chart metric", selection: $chartPower) { Text("CPU").tag(false); Text("Power").tag(true) }.labelsHidden().pickerStyle(.segmented).tint(Palette.green).frame(width: 140)
            }
            if chartPower && model.timeline.allSatisfy({ $0.watts == nil }) {
                VStack(spacing: 10) {
                    Image(systemName: "bolt.slash").font(.system(size: 24, weight: .light))
                    Text("Power data is not available on this source.")
                    Button("View measurement options") { model.selectedPage = "Measurement" }.buttonStyle(SecondaryButton())
                }.font(.system(size: 12)).foregroundStyle(Palette.muted).frame(maxWidth: .infinity).frame(height: 170)
            } else { HistoryChart(points: model.timeline, power: chartPower) }
        }
        HStack(alignment: .top, spacing: 18) {
            Panel(title: "Where your resources go") {
                ForEach(Array(model.groups.prefix(4))) { group in AppRow(group: group, compact: true) }
                Button("Explore applications") { model.selectedPage = "Applications" }.buttonStyle(SecondaryButton())
            }
            Panel(title: "A useful next step") {
                Image(systemName: insightIcon).font(.system(size: 25, weight: .light)).foregroundStyle(Palette.green)
                Text(insightTitle).font(.system(size: 20, design: .serif))
                Text(insightBody).font(.system(size: 12)).foregroundStyle(Palette.muted).lineSpacing(5).fixedSize(horizontal: false, vertical: true)
                Tag(text: "\(model.sample?.thermal ?? "Unknown") thermal state")
            }.frame(maxWidth: 315)
        }
    }
    var hero: some View {
        ZStack(alignment: .trailing) {
            RoundedRectangle(cornerRadius: 23).fill(Palette.ink)
            ContourArt().frame(width: 290, height: 210).padding(.trailing, 15).clipped()
            HStack {
                VStack(alignment: .leading, spacing: 15) {
                    Text("RESOURCE AWARENESS, WITH INTENTION").font(.system(size: 9, weight: .medium, design: .monospaced)).tracking(2).foregroundStyle(Palette.mint)
                    Text("Know your impact.\nFind your balance.").font(.system(size: 37, weight: .regular, design: .serif)).lineSpacing(1).foregroundStyle(Palette.paper)
                    Text("Live insight into the work your Mac is doing.").font(.system(size: 12)).foregroundStyle(Palette.paper.opacity(0.72))
                }
                Spacer()
            }.padding(30)
        }.frame(height: 222)
    }
    var insightIcon: String { (model.sample?.thermal == "High" || model.sample?.thermal == "Critical") ? "thermometer.sun" : "waveform.path" }
    var insightTitle: String {
        if model.sample?.thermal == "High" || model.sample?.thermal == "Critical" { return "Your Mac is under thermal pressure." }
        if let cpu = model.sample?.cpuPercent, cpu > 70 { return "There’s substantial work in progress." }
        return "Start with a baseline."
    }
    var insightBody: String {
        if model.sample?.thermal == "High" || model.sample?.thermal == "Critical" { return "Review the busiest apps before starting more work. Consider deferring a background job, then record another session to compare." }
        if let cpu = model.sample?.cpuPercent, cpu > 70 { return "Check which applications are busy. High CPU may be useful work; it does not by itself mean energy is being wasted." }
        return "Record a typical task before changing its settings. Repeat the same task afterward to compare energy coverage, runtime, and completed work."
    }
}

struct AppIcon: View {
    let group: AppGroup
    var body: some View {
        Group {
            if let bundle = group.bundle { Image(nsImage: NSWorkspace.shared.icon(forFile: bundle.path)).resizable().interpolation(.high) }
            else { Image(systemName: "terminal").resizable().scaledToFit().padding(7).foregroundStyle(Palette.green).background(Palette.line.opacity(0.4), in: RoundedRectangle(cornerRadius: 9)) }
        }.frame(width: 34, height: 34).accessibilityHidden(true)
    }
}

struct AppRow: View {
    let group: AppGroup
    var compact = false
    var body: some View {
        HStack(spacing: 12) {
            AppIcon(group: group)
            VStack(alignment: .leading, spacing: 4) {
                Text(group.name).font(.system(size: 12, weight: .medium)).lineLimit(1)
                Text("\(group.processes.count) process\(group.processes.count == 1 ? "" : "es")").font(.system(size: 10)).foregroundStyle(Palette.muted)
            }
            Spacer()
            if !compact {
                Text(bytes(group.memory)).frame(width: 95, alignment: .trailing).foregroundStyle(Palette.muted)
                Text(group.ioRate.map { "\(decimal($0 / 1024, places: 0)) KB/s" } ?? "—").frame(width: 100, alignment: .trailing).foregroundStyle(Palette.muted)
            }
            Text("\(decimal(group.cpu))%").monospacedDigit().frame(width: 68, alignment: .trailing)
        }.font(.system(size: 12)).padding(.vertical, 7)
    }
}

struct ApplicationsView: View {
    @EnvironmentObject var model: AppModel
    @State private var query = ""
    @State private var appsOnly = true
    @State private var sort = "CPU"
    @State private var selected: AppGroup?
    var filtered: [AppGroup] {
        model.groups.filter { (!appsOnly || $0.bundle != nil) && (query.isEmpty || $0.name.localizedCaseInsensitiveContains(query)) }
            .sorted { sort == "Memory" ? $0.memory > $1.memory : ($0.cpu ?? -1) > ($1.cpu ?? -1) }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Eyebrow(text: "Understand the workload")
            Text("A clearer view of your apps.").font(.system(size: 33, design: .serif))
            Text("Grouped by application bundle. CPU uses 100% for one logical core, so a busy app can exceed 100%.").font(.system(size: 12)).foregroundStyle(Palette.muted)
        }
        Panel {
            HStack(spacing: 18) {
                TextField("Find an application or process", text: $query).textFieldStyle(.roundedBorder).frame(maxWidth: 300)
                Toggle("Apps only", isOn: $appsOnly).toggleStyle(.switch).controlSize(.small)
                Spacer()
                Picker("Sort by", selection: $sort) { Text("CPU").tag("CPU"); Text("Memory").tag("Memory") }.frame(width: 145)
            }
            HStack {
                Eyebrow(text: "Application"); Spacer()
                Text("MEMORY").frame(width: 95, alignment: .trailing)
                Text("DISK I/O").frame(width: 100, alignment: .trailing)
                Text("CPU").frame(width: 68, alignment: .trailing)
            }.font(.system(size: 9, design: .monospaced)).foregroundStyle(Palette.muted)
            if filtered.isEmpty { Text("No matching applications.").foregroundStyle(Palette.muted).padding(.vertical, 25) }
            LazyVStack(spacing: 0) {
                ForEach(filtered) { group in
                    Button { selected = group } label: { AppRow(group: group).contentShape(Rectangle()) }.buttonStyle(.plain)
                    Divider().overlay(Palette.line.opacity(0.4))
                }
            }
            Text("\(model.sample?.inaccessibleProcesses ?? 0) processes could not be read. Some system processes are protected by macOS. Shared memory can appear in more than one process.")
                .font(.system(size: 10)).foregroundStyle(Palette.muted)
        }
        .sheet(item: $selected) { group in ProcessDetail(group: group) }
    }
}

struct ProcessDetail: View {
    let group: AppGroup
    @State private var pending: ProcessSample?
    @State private var force = false
    @State private var confirming = false
    @State private var status = ""
    @Environment(\.dismiss) var dismiss
    var mainProcess: ProcessSample? {
        guard let bundle = group.bundle else { return nil }
        let running = NSWorkspace.shared.runningApplications.first { $0.bundleURL == bundle && $0.activationPolicy != .prohibited }
        return group.processes.first { $0.id.pid == running?.processIdentifier }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack { AppIcon(group: group); Text(group.name).font(.system(size: 25, design: .serif)); Spacer(); Button("Done") { dismiss() } }
            Text("Snapshot at selection · per-app power is not inferred from CPU percentage.").font(.system(size: 12)).foregroundStyle(Palette.muted)
            if let main = mainProcess {
                HStack {
                    Button("Quit App") { pending = main; force = false; confirming = true }.buttonStyle(SecondaryButton())
                    Button("Force Quit App…") { pending = main; force = true; confirming = true }.buttonStyle(SecondaryButton())
                }.disabled((try? ProcessControl.checked(main.id)) == nil)
            }
            ScrollView {
                ForEach(group.processes) { process in
                    HStack {
                        VStack(alignment: .leading) { Text(process.name).lineLimit(1).help(process.name); Text("PID \(process.id.pid)").font(.caption).foregroundStyle(Palette.muted) }
                        Spacer(); Text(bytes(process.memoryBytes)); Text("\(decimal(process.cpuPercent))% CPU").frame(width: 100, alignment: .trailing)
                        Menu("Actions") {
                            Button("Quit") { pending = process; force = false; confirming = true }
                            Button("Force Quit…", role: .destructive) { pending = process; force = true; confirming = true }
                        }.frame(width: 85).disabled((try? ProcessControl.checked(process.id)) == nil)
                    }.padding(.vertical, 8)
                }
            }.frame(maxHeight: 400)
            Text(status.isEmpty ? "Quit requests a normal app shutdown. Force Quit can lose unsaved work. Only the selected process is targeted; children may remain. Protected processes cannot be controlled." : status).font(.system(size: 11)).foregroundStyle(Palette.muted)
        }.padding(28).frame(width: 710).background(Palette.paper)
        .alert(force ? "Force quit \(pending?.name ?? "process")?" : "Quit \(pending?.name ?? "process")?", isPresented: $confirming) {
            Button("Cancel", role: .cancel) {}
            Button(force ? "Force Quit" : "Request Quit", role: .destructive) {
                guard let target = pending else { return }
                do { status = try ProcessControl.request(target.id, force: force) }
                catch { status = error.localizedDescription }
            }
        } message: {
            Text("PID \(pending?.id.pid ?? 0). " + (force ? "Unsaved work will be lost." : "The app may ask you to save work or cancel. Background processes receive SIGTERM."))
        }
    }
}

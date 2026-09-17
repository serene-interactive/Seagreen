import SwiftUI
import AppKit
import SeagreenCore

final class AppDelegate: NSObject, NSApplicationDelegate {
    var model: AppModel?
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if model?.jobRunning == true {
            let alert = NSAlert()
            alert.messageText = "A launched job is still running"
            alert.informativeText = "Return to Seagreen, or request termination of the launched process and quit. Independently running child processes may continue."
            alert.addButton(withTitle: "Return to Seagreen"); alert.addButton(withTitle: "Stop launched process and quit")
            if alert.runModal() == .alertFirstButtonReturn { return .terminateCancel }
            model?.stopJob()
        }
        model?.shutdown(); return .terminateNow
    }
}

@main struct SeagreenApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var model = AppModel()
    init() {
        if CommandLine.arguments.contains("--diagnostics") {
            let collector = SystemCollector()
            _ = collector.sample(); Thread.sleep(forTimeInterval: 1)
            let sample = collector.sample()
            let report: [String: Any] = ["processes": sample.processes.count,
                "systemCPUPercent": sample.cpuPercent as Any? ?? NSNull(),
                "memoryBytes": sample.memoryBytes, "collectionMS": sample.collectionMS,
                "powerWatts": sample.power?.watts as Any? ?? NSNull(),
                "powerSource": sample.power?.key as Any? ?? NSNull(),
                "thermal": sample.thermal, "inaccessibleProcesses": sample.inaccessibleProcesses]
            if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]), let text = String(data: data, encoding: .utf8) { print(text) }
            exit(sample.error == nil && !sample.processes.isEmpty ? 0 : 1)
        }
    }
    var body: some Scene {
        WindowGroup("Seagreen", id: "main") {
            ContentView().environmentObject(model)
                .onAppear { delegate.model = model }
                .frame(minWidth: 1060, minHeight: 740)
                .preferredColorScheme(.light)
        }
        .defaultSize(width: 1240, height: 840)
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandMenu("Monitoring") {
                Button(model.paused ? "Resume Monitoring" : "Pause Monitoring") { model.paused.toggle() }
                    .disabled(model.active != nil).keyboardShortcut("p", modifiers: [.command, .shift])
                Button("Finish Recording") { model.finishRecording() }.disabled(model.active == nil)
            }
        }
        MenuBarExtra {
            MenuContent().environmentObject(model)
        } label: {
            Image(systemName: "drop.degreesign.fill")
            Text(model.sample?.power.map { "\(decimal($0.watts)) W" } ?? "\(decimal(model.sample?.cpuPercent, places: 0))%")
        }
    }
}

struct MenuContent: View {
    @EnvironmentObject var model: AppModel
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        Text("Seagreen · \(model.paused ? "Paused" : "Monitoring")")
        Text("System CPU: \(decimal(model.sample?.cpuPercent))%")
        if let power = model.sample?.power { Text("\(power.scope): \(decimal(power.watts)) W") }
        else { Text("Power measurement unavailable") }
        Divider()
        Button("Open Seagreen") { openWindow(id: "main"); NSApp.activate(ignoringOtherApps: true) }
        Button("Quit Seagreen") { NSApp.terminate(nil) }
    }
}

struct ContentView: View {
    @EnvironmentObject var model: AppModel
    @State private var showRecording = false
    let pages = [("Overview", "circle.grid.2x2"), ("Applications", "square.stack.3d.up"), ("Experiments", "waveform.path"), ("Efficiency", "leaf"), ("Measurement", "slider.horizontal.3")]
    var body: some View {
        HStack(spacing: 0) {
            sidebar
            VStack(spacing: 0) {
                HStack {
                    Text(model.selectedPage).font(.system(size: 13, weight: .medium))
                    Spacer()
                    HStack(spacing: 7) {
                        Circle().fill(model.paused ? Color.orange : Palette.green).frame(width: 6, height: 6)
                        Text(model.paused ? "Monitoring paused" : "Local monitoring · every 2 seconds").font(.system(size: 11)).foregroundStyle(Palette.muted)
                    }
                    Divider().frame(height: 16).padding(.horizontal, 10)
                    if model.active != nil {
                        Button { model.finishRecording() } label: { Label("Finish recording", systemImage: "stop.circle") }.buttonStyle(PrimaryButton())
                    } else {
                        Button { showRecording = true } label: { Label("Record session", systemImage: "record.circle") }.buttonStyle(PrimaryButton())
                    }
                }.padding(.horizontal, 32).padding(.top, 18).padding(.bottom, 18)
                Rectangle().fill(Palette.line).frame(height: 1)
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        switch model.selectedPage {
                        case "Applications": ApplicationsView()
                        case "Experiments": ExperimentsView(showRecording: $showRecording)
                        case "Efficiency": EfficiencyView()
                        case "Measurement": MeasurementView()
                        default: OverviewView()
                        }
                    }.padding(32).frame(maxWidth: 1400)
                }
                HStack {
                    Text("SEAGREEN 3.0.0").tracking(1.2)
                    Spacer()
                    Text("On-device. No account. No telemetry.")
                }.font(.system(size: 9, design: .monospaced)).foregroundStyle(Palette.muted).padding(.horizontal, 32).padding(.vertical, 12)
            }.background(Palette.paper)
        }.foregroundStyle(Palette.ink)
            .sheet(isPresented: $showRecording) { NewRecordingView().environmentObject(model) }
            .alert("Seagreen", isPresented: Binding(get: { model.message != nil }, set: { if !$0 { model.message = nil } })) {
                Button("OK") { model.message = nil }
            } message: { Text(model.message ?? "") }
    }
    var sidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 11) {
                SeagreenMark()
                VStack(alignment: .leading, spacing: 3) {
                    Text("Seagreen").font(.system(size: 22, weight: .medium, design: .serif))
                    Text("BY SERENE INTERACTIVE").font(.system(size: 7, weight: .medium)).tracking(1.3).foregroundStyle(Palette.muted)
                }
            }.padding(.top, 44).padding(.bottom, 44)
            Eyebrow(text: "Your workspace").padding(.leading, 12).padding(.bottom, 15)
            ForEach(pages, id: \.0) { page in
                Button { model.selectedPage = page.0 } label: {
                    HStack(spacing: 12) {
                        Image(systemName: page.1).font(.system(size: 15)).frame(width: 20)
                        Text(page.0).font(.system(size: 13, weight: model.selectedPage == page.0 ? .semibold : .regular))
                        Spacer()
                        if page.0 == "Experiments", model.active != nil { Circle().fill(Palette.green).frame(width: 6, height: 6) }
                    }.padding(.horizontal, 13).padding(.vertical, 13)
                        .background(model.selectedPage == page.0 ? Palette.line.opacity(0.5) : Color.clear, in: RoundedRectangle(cornerRadius: 10))
                }.buttonStyle(.plain).padding(.bottom, 4)
            }
            Spacer()
            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: "leaf").font(.system(size: 23, weight: .light)).foregroundStyle(Palette.green)
                Text("A lighter footprint.\nA clearer picture.").font(.system(size: 19, weight: .regular, design: .serif)).lineSpacing(4)
                Text("Understand your Mac.\nMake every change count.").font(.system(size: 11)).foregroundStyle(Palette.muted).lineSpacing(4)
            }.padding(16).padding(.bottom, 28)
        }.padding(.horizontal, 20).frame(width: 222).background(Palette.surface)
    }
}

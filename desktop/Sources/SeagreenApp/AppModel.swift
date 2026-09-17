import AppKit
import SwiftUI
import UniformTypeIdentifiers
import SeagreenCore

struct AppGroup: Identifiable {
    let id: String
    let name: String
    let bundle: URL?
    let processes: [ProcessSample]
    var cpu: Double? {
        let values = processes.compactMap(\.cpuPercent)
        return values.isEmpty ? nil : values.reduce(0, +)
    }
    var memory: UInt64 { processes.reduce(0) { $0 + $1.memoryBytes } }
    var readRate: Double { processes.compactMap(\.readBytesPerSecond).reduce(0, +) }
    var writeRate: Double { processes.compactMap(\.writeBytesPerSecond).reduce(0, +) }
    var ioRate: Double? {
        let values = processes.flatMap { [$0.readBytesPerSecond, $0.writeBytesPerSecond].compactMap { $0 } }
        return values.isEmpty ? nil : values.reduce(0, +)
    }
}

// Existing identities keep their slots, including stopped rows until manual refresh.
func retainingApplicationRows(_ previous: [AppGroup], incoming: [AppGroup]) -> [AppGroup] {
    let byID = Dictionary(uniqueKeysWithValues: incoming.map { ($0.id, $0) })
    let existing = Set(previous.map(\.id))
    return previous.map { old in
        byID[old.id] ?? AppGroup(id: old.id, name: old.name, bundle: old.bundle, processes: [])
    } + incoming.filter { !existing.contains($0.id) }
}

@MainActor final class AppModel: ObservableObject {
    @Published var sample: SystemSample?
    @Published var timeline: [TimelinePoint] = []
    @Published var groups: [AppGroup] = []
    @Published var recordings: [Recording] = []
    @Published var active: Recording?
    @Published var message: String?
    @Published var selectedPage = "Overview"
    @Published var powerFileName: String?
    @Published var jobName: String?
    @Published var jobStatus = "No job running"
    @Published var jobOutput = ""
    @Published var jobRunning = false
    @Published var paused = false
    private let collector = SystemCollector()
    private let queue = DispatchQueue(label: "com.sereneinteractive.seagreen.collector", qos: .utility)
    private var timer: Timer?
    private var collecting = false
    private var store: RecordingStore?
    private var energy = EnergyIntegrator()
    private var process: Process?
    private var jobPipe: Pipe?
    private var saveCounter = 0
    private var retainedPowerURL: URL?
    private var deviceID: String {
        var size = 0
        sysctlbyname("hw.model", nil, &size, nil, 0)
        var model = [CChar](repeating: 0, count: max(1, size))
        sysctlbyname("hw.model", &model, &size, nil, 0)
        // Local random identity avoids collecting a hardware serial number.
        let key = "SeagreenLocalDeviceID"
        let identifier = UserDefaults.standard.string(forKey: key) ?? UUID().uuidString
        UserDefaults.standard.set(identifier, forKey: key)
        return String(cString: model) + ":" + identifier
    }
    init() {
        do { store = try RecordingStore(); recordings = try store!.load() }
        catch { message = "Could not open local recording history: \(error.localizedDescription)" }
        tick()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.tick() }
        }
    }
    func tick() {
        guard !collecting, !paused else { return }
        collecting = true
        queue.async { [weak self, collector] in
            let sample = collector.sample()
            DispatchQueue.main.async { self?.receive(sample) }
        }
    }
    private func receive(_ next: SystemSample) {
        collecting = false
        sample = next
        let point = TimelinePoint(date: next.date, cpu: next.cpuPercent, memoryGB: Double(next.memoryBytes) / 1_073_741_824,
                                  watts: next.power?.watts, powerKey: next.power?.key)
        timeline.append(point)
        if timeline.count > 150 { timeline.removeFirst(timeline.count - 150) }
        let incoming = groupProcesses(next.processes)
        groups = retainingApplicationRows(groups, incoming: incoming)
        if var recording = active {
            energy.add(time: next.uptime, power: next.power)
            recording.points.append(point); recording.ended = next.date
            recording.energyWh = energy.wattHours; recording.coveredSeconds = energy.coveredSeconds
            if let key = next.power?.key, !recording.powerKeys.contains(key) { recording.powerKeys.append(key); recording.powerKeys.sort() }
            active = recording
            saveCounter += 1
            if saveCounter >= 15 { saveCounter = 0; save(recording) }
            if recording.duration >= 7200 { finishRecording(); message = "Recording saved at the two-hour limit. Start another session to continue." }
        }
    }
    private func groupProcesses(_ processes: [ProcessSample]) -> [AppGroup] {
        var byKey: [String: [ProcessSample]] = [:]
        var bundles: [String: URL] = [:]
        for process in processes {
            let key: String
            if let range = process.path.range(of: ".app/") {
                let path = String(process.path[..<range.lowerBound]) + ".app"
                key = path; bundles[key] = URL(fileURLWithPath: path)
            } else { key = "process:\(process.id.pid):\(process.id.started)" }
            byKey[key, default: []].append(process)
        }
        return byKey.map { key, value in
            let bundle = bundles[key]
            let name = bundle.map { $0.deletingPathExtension().lastPathComponent } ?? value[0].name
            return AppGroup(id: key, name: name, bundle: bundle, processes: value)
        }.sorted {
            let a = $0.cpu ?? -1, b = $1.cpu ?? -1
            return a == b ? $0.id < $1.id : a > b
        }
    }
    func refreshApplicationOrder(by sort: String) {
        groups = groups.filter { !$0.processes.isEmpty }.sorted {
            let a = sort == "Memory" ? Double($0.memory) : ($0.cpu ?? -1)
            let b = sort == "Memory" ? Double($1.memory) : ($1.cpu ?? -1)
            return a == b ? $0.id < $1.id : a > b
        }
    }
    func beginRecording(title: String, notes: String, units: String, unitName: String) {
        guard active == nil else { return }
        paused = false; energy = EnergyIntegrator(); saveCounter = 0
        let count = Double(units)
        active = Recording(title: title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "Untitled session" : title,
                           started: Date(), notes: notes, device: deviceID,
                           completedUnits: count.flatMap { $0.isFinite && $0 > 0 ? $0 : nil },
                           unitName: unitName.isEmpty ? "task" : unitName)
        selectedPage = "Experiments"
    }
    func finishRecording() {
        guard var recording = active else { return }
        recording.ended = Date(); save(recording)
        active = nil; energy = EnergyIntegrator()
        reload()
    }
    func save(_ recording: Recording) {
        do { guard let store else { throw CocoaError(.fileWriteUnknown) }; try store.save(recording) }
        catch { message = "Recording could not be saved: \(error.localizedDescription)" }
    }
    func reload() {
        do { recordings = try store?.load() ?? [] }
        catch { message = "History could not be loaded: \(error.localizedDescription)" }
    }
    func delete(_ recording: Recording) {
        do { try store?.delete(recording); reload() }
        catch { message = "Could not delete recording: \(error.localizedDescription)" }
    }
    func export(_ recording: Recording, csv: Bool) {
        let panel = NSSavePanel()
        panel.directoryURL = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
        panel.allowedContentTypes = csv ? [.commaSeparatedText] : [.json]
        panel.nameFieldStringValue = "Seagreen-\(recording.id.uuidString.prefix(8)).\(csv ? "csv" : "json")"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            if csv { try RecordingStore.csv(recording).write(to: url, atomically: true, encoding: .utf8) }
            else { let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]; try encoder.encode(recording).write(to: url, options: .atomic) }
        } catch { message = "Export failed: \(error.localizedDescription)" }
    }
    func choosePowerFile() {
        guard active == nil else { message = "Finish your recording before switching power sources."; return }
        let panel = NSOpenPanel(); panel.canChooseDirectories = false; panel.allowsMultipleSelection = false
        panel.message = "Select a live powermetrics property-list output file. Stale or unsupported data is not used."
        guard panel.runModal() == .OK, let url = panel.url else { return }
        retainedPowerURL = url; powerFileName = url.lastPathComponent
        queue.async { [collector] in collector.powerFile = url }
    }
    func disconnectPowerFile() {
        guard active == nil else { return }
        retainedPowerURL = nil; powerFileName = nil
        queue.async { [collector] in collector.powerFile = nil }
    }
    func launch(executable: URL, arguments: [String], efficient: Bool) {
        guard !jobRunning else { return }
        guard FileManager.default.isExecutableFile(atPath: executable.path), !executable.hasDirectoryPath else {
            message = "Choose an executable file, such as a Python interpreter or a command-line tool."; return
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/sbin/taskpolicy")
        task.arguments = (efficient ? ["-b"] : []) + [executable.path] + arguments
        let pipe = Pipe(); task.standardOutput = pipe; task.standardError = pipe
        task.standardInput = FileHandle.nullDevice
        jobOutput = ""; jobPipe = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { handle.readabilityHandler = nil; return }
            let text = String(decoding: data, as: UTF8.self)
            DispatchQueue.main.async {
                guard let self else { return }
                self.jobOutput = String((self.jobOutput + text).suffix(32768))
            }
        }
        task.terminationHandler = { [weak self] job in
            DispatchQueue.main.async {
                self?.jobRunning = false
                self?.jobStatus = "Exited with status \(job.terminationStatus)"
                self?.process = nil
            }
        }
        do {
            try task.run(); process = task; jobRunning = true; jobName = executable.lastPathComponent
            jobStatus = efficient ? "Background policy requested · PID \(task.processIdentifier)" : "Standard policy · PID \(task.processIdentifier)"
        } catch { pipe.fileHandleForReading.readabilityHandler = nil; message = "Job could not start: \(error.localizedDescription)" }
    }
    func stopJob() {
        guard let process, process.isRunning else { return }
        process.terminate()
        jobStatus = "Termination requested for the launched process"
    }
    func shutdown() { finishRecording() }
}

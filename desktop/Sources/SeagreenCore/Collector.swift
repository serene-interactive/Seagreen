import Foundation
import IOKit
import IOKit.ps
import SGSystem

// All mutable collector state is protected by this lock, including file selection.
public final class SystemCollector: @unchecked Sendable {
    private let lock = NSLock()
    private var previous: [ProcessIdentity: sg_process] = [:]
    private var previousHost: sg_host?
    private var previousTime: Double?
    private var selectedPowerFile: URL?
    public var powerFile: URL? {
        get { lock.lock(); defer { lock.unlock() }; return selectedPowerFile }
        set { lock.lock(); defer { lock.unlock() }; selectedPowerFile = newValue }
    }
    public init() {}

    public func sample() -> SystemSample {
        lock.lock(); defer { lock.unlock() }
        let begin = ProcessInfo.processInfo.systemUptime
        let elapsed = previousTime.map { begin - $0 } ?? 0
        var host = sg_host()
        let hostOK = sg_read_host(&host) == 1
        var hostCPU: Double?
        if hostOK, let old = previousHost, elapsed > 0, elapsed <= 15 {
            let current = host.user_ticks + host.system_ticks + host.nice_ticks
            let last = old.user_ticks + old.system_ticks + old.nice_ticks
            if current >= last, host.idle_ticks >= old.idle_ticks {
                let active = current - last, idle = host.idle_ticks - old.idle_ticks
                if active + idle > 0 { hostCPU = Double(active) / Double(active + idle) * 100 }
            }
        }
        var pids = [Int32](repeating: 0, count: 65536)
        let count = pids.withUnsafeMutableBufferPointer { sg_pids($0.baseAddress, Int32($0.count)) }
        var next: [ProcessIdentity: sg_process] = [:]
        var samples: [ProcessSample] = []
        var inaccessible = 0
        for pid in pids.prefix(Int(count)) where pid > 0 {
            var raw = sg_process()
            guard sg_read_process(pid, &raw) == 1 else { inaccessible += 1; continue }
            let identity = ProcessIdentity(pid: pid, started: raw.start_usec)
            let old = previous[identity]
            next[identity] = raw
            let name = withUnsafePointer(to: &raw.name) { pointer in pointer.withMemoryRebound(to: CChar.self, capacity: 256) { String(cString: $0) } }
            let path = withUnsafePointer(to: &raw.path) { pointer in pointer.withMemoryRebound(to: CChar.self, capacity: 4096) { String(cString: $0) } }
            samples.append(ProcessSample(id: identity, parentPID: raw.parent_pid, uid: raw.uid,
                name: name, path: path,
                cpuPercent: old.flatMap { MeasurementMath.cpuPercent(previous: $0.cpu_nsec, current: raw.cpu_nsec, elapsed: elapsed) },
                memoryBytes: raw.resident_bytes,
                readBytesPerSecond: old.flatMap { $0.io_available == 1 && raw.io_available == 1 ? MeasurementMath.rate(previous: $0.read_bytes, current: raw.read_bytes, elapsed: elapsed) : nil },
                writeBytesPerSecond: old.flatMap { $0.io_available == 1 && raw.io_available == 1 ? MeasurementMath.rate(previous: $0.write_bytes, current: raw.write_bytes, elapsed: elapsed) : nil }))
        }
        previous = next; previousHost = hostOK ? host : nil; previousTime = begin
        let battery = Self.readBattery()
        let importedPower = selectedPowerFile.flatMap { PowerMetricsReader.latest(at: $0) }
        let thermal: String
        switch ProcessInfo.processInfo.thermalState {
        case .nominal: thermal = "Nominal"
        case .fair: thermal = "Warm"
        case .serious: thermal = "High"
        case .critical: thermal = "Critical"
        @unknown default: thermal = "Unknown"
        }
        return SystemSample(date: Date(), uptime: begin, cpuPercent: hostCPU,
            memoryBytes: host.memory_used, totalMemoryBytes: host.memory_total,
            battery: battery, power: importedPower ?? battery.power, thermal: thermal,
            lowPowerMode: ProcessInfo.processInfo.isLowPowerModeEnabled,
            processes: samples.sorted { ($0.cpuPercent ?? -1) > ($1.cpuPercent ?? -1) },
            inaccessibleProcesses: inaccessible,
            collectionMS: (ProcessInfo.processInfo.systemUptime - begin) * 1000,
            error: hostOK ? nil : "macOS did not return system counters.")
    }

    public static func readBattery() -> BatteryState {
        var state = BatteryState()
        if let blob = IOPSCopyPowerSourcesInfo()?.takeRetainedValue(),
           let sources = IOPSCopyPowerSourcesList(blob)?.takeRetainedValue() as? [CFTypeRef] {
            for source in sources {
                guard let description = IOPSGetPowerSourceDescription(blob, source)?.takeUnretainedValue() as? [String: Any],
                      description[kIOPSTypeKey] as? String == kIOPSInternalBatteryType else { continue }
                let current = (description[kIOPSCurrentCapacityKey] as? NSNumber)?.doubleValue
                let max = (description[kIOPSMaxCapacityKey] as? NSNumber)?.doubleValue
                if let current, let max, max > 0 { state.percent = min(100, Swift.max(0, current / max * 100)) }
                state.pluggedIn = description[kIOPSPowerSourceStateKey] as? String == kIOPSACPowerValue
                state.detail = state.pluggedIn == true ? "Connected to power · discharge measurement unavailable" : "On battery · sensor power unavailable"
            }
        }
        // Optional AppleSmartBattery fields are not available on every Mac. Never infer watts from battery percentage.
        let service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleSmartBattery"))
        guard service != 0 else { return state }
        defer { IOObjectRelease(service) }
        var properties: Unmanaged<CFMutableDictionary>?
        guard IORegistryEntryCreateCFProperties(service, &properties, kCFAllocatorDefault, 0) == KERN_SUCCESS,
              let dictionary = properties?.takeRetainedValue() as? [String: Any], state.pluggedIn == false else { return state }
        guard let voltage = dictionary["Voltage"] as? NSNumber,
              let current = dictionary["Amperage"] as? NSNumber else { return state }
        // Drivers may expose signed current in an unsigned 64-bit NSNumber.
        let amps = Double(Int64(bitPattern: current.uint64Value))
        if let watts = MeasurementMath.batteryWatts(millivolts: voltage.doubleValue, milliamps: amps, pluggedIn: false) {
            state.power = PowerReading(watts: watts, source: .battery, scope: "Whole-device battery discharge")
            state.detail = "Voltage × discharge current · whole device, not individual apps"
        }
        return state
    }
}

public enum PowerMetricsReader {
    public static func decode(_ data: Data) -> PowerReading? {
        guard let root = try? PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any],
              let processor = root["processor"] as? [String: Any] else { return nil }
        // Known Apple silicon schema, mW. Reject unknown fields rather than guessing units or scope.
        if let number = processor["combined_power"] as? NSNumber {
            let watts = number.doubleValue / 1000
            guard watts.isFinite, watts >= 0, watts <= 1000 else { return nil }
            return PowerReading(watts: watts, source: .powermetrics, scope: "CPU + GPU + ANE")
        }
        if let number = processor["cpu_power"] as? NSNumber {
            let watts = number.doubleValue / 1000
            guard watts.isFinite, watts >= 0, watts <= 1000 else { return nil }
            return PowerReading(watts: watts, source: .powermetrics, scope: "CPU only")
        }
        return nil
    }
    public static func latest(at url: URL, now: Date = Date()) -> PowerReading? {
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
              let modified = attrs[.modificationDate] as? Date,
              now.timeIntervalSince(modified) >= -2, now.timeIntervalSince(modified) < 10,
              let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }
        guard let end = try? handle.seekToEnd() else { return nil }
        try? handle.seek(toOffset: end > 1_048_576 ? end - 1_048_576 : 0)
        guard let data = try? handle.readToEnd(), let string = String(data: data, encoding: .utf8),
              let close = string.range(of: "</plist>", options: .backwards),
              let open = string[..<close.upperBound].range(of: "<?xml", options: .backwards) else { return nil }
        return decode(Data(string[open.lowerBound..<close.upperBound].utf8))
    }
}

import Foundation

public struct ProcessIdentity: Hashable, Codable, Sendable {
    public let pid: Int32
    public let started: UInt64
    public init(pid: Int32, started: UInt64) { self.pid = pid; self.started = started }
}

public struct ProcessSample: Identifiable, Sendable {
    public let id: ProcessIdentity
    public let parentPID: Int32
    public let uid: UInt32
    public let name: String
    public let path: String
    public let cpuPercent: Double?
    public let memoryBytes: UInt64
    public let readBytesPerSecond: Double?
    public let writeBytesPerSecond: Double?
}

public struct PowerReading: Codable, Equatable, Sendable {
    public enum Source: String, Codable, Sendable {
        case battery = "Battery sensor"
        case powermetrics = "Apple power estimate"
    }
    public let watts: Double
    public let source: Source
    public let scope: String
    public init(watts: Double, source: Source, scope: String) {
        self.watts = watts; self.source = source; self.scope = scope
    }
    public var key: String { source.rawValue + ":" + scope }
}

public struct BatteryState: Sendable {
    public var percent: Double?
    public var pluggedIn: Bool?
    public var power: PowerReading?
    public var detail: String
    public init(percent: Double? = nil, pluggedIn: Bool? = nil, power: PowerReading? = nil, detail: String = "No internal battery detected") {
        self.percent = percent; self.pluggedIn = pluggedIn; self.power = power; self.detail = detail
    }
}

public struct SystemSample: Sendable {
    public let date: Date
    public let uptime: Double
    public let cpuPercent: Double?
    public let memoryBytes: UInt64
    public let totalMemoryBytes: UInt64
    public let battery: BatteryState
    public let power: PowerReading?
    public let thermal: String
    public let lowPowerMode: Bool
    public let processes: [ProcessSample]
    public let inaccessibleProcesses: Int
    public let collectionMS: Double
    public let error: String?
}

public struct TimelinePoint: Codable, Identifiable, Sendable {
    public var id: Date { date }
    public let date: Date
    public let cpu: Double?
    public let memoryGB: Double
    public let watts: Double?
    public let powerKey: String?
    public init(date: Date, cpu: Double?, memoryGB: Double, watts: Double?, powerKey: String?) {
        self.date = date; self.cpu = cpu; self.memoryGB = memoryGB; self.watts = watts; self.powerKey = powerKey
    }
}

public enum MeasurementMath {
    public static func cpuPercent(previous: UInt64, current: UInt64, elapsed: Double) -> Double? {
        guard elapsed > 0, elapsed <= 15, elapsed.isFinite, current >= previous else { return nil }
        return Double(current - previous) / 1_000_000_000 / elapsed * 100
    }
    public static func rate(previous: UInt64, current: UInt64, elapsed: Double) -> Double? {
        guard elapsed > 0, elapsed <= 15, elapsed.isFinite, current >= previous else { return nil }
        return Double(current - previous) / elapsed
    }
    public static func batteryWatts(millivolts: Double, milliamps: Double, pluggedIn: Bool) -> Double? {
        guard !pluggedIn, millivolts.isFinite, milliamps.isFinite,
              millivolts >= 5000, millivolts <= 25000, milliamps < 0 else { return nil }
        let watts = millivolts * -milliamps / 1_000_000
        return watts > 0 && watts <= 250 ? watts : nil
    }
}

/// Integrate only adjacent, same-source readings. Sleep, gaps and source changes add no energy.
public struct EnergyIntegrator: Sendable {
    public private(set) var wattHours: Double = 0
    public private(set) var coveredSeconds: Double = 0
    private var previous: (time: Double, power: PowerReading)?
    public init() {}
    public mutating func add(time: Double, power: PowerReading?) {
        guard time.isFinite, let power, power.watts.isFinite, power.watts >= 0 else {
            previous = nil; return
        }
        defer { previous = (time, power) }
        guard let last = previous, last.power.key == power.key else { return }
        let delta = time - last.time
        guard delta > 0, delta <= 15 else { return }
        wattHours += (last.power.watts + power.watts) / 2 * delta / 3600
        coveredSeconds += delta
    }
    public var kilowattHours: Double { wattHours / 1000 }
}

public struct Recording: Codable, Identifiable, Sendable {
    public var id = UUID()
    public var title: String
    public var started: Date
    public var ended: Date
    public var notes: String
    public var points: [TimelinePoint]
    public var energyWh: Double
    public var coveredSeconds: Double
    public var powerKeys: [String]
    public var device: String
    public var completedUnits: Double?
    public var unitName: String
    public var duration: Double { max(0, ended.timeIntervalSince(started)) }
    public var coverage: Double { duration > 0 ? min(1, coveredSeconds / duration) : 0 }
    public var averageCPU: Double? {
        let values = points.compactMap(\.cpu)
        return values.isEmpty ? nil : values.reduce(0, +) / Double(values.count)
    }
    public var energyPerUnit: Double? {
        guard coverage >= 0.9, powerKeys.count == 1, let units = completedUnits, units > 0 else { return nil }
        return energyWh / units
    }
    public init(title: String, started: Date, notes: String = "", device: String, completedUnits: Double? = nil, unitName: String = "task") {
        self.title = title; self.started = started; self.ended = started; self.notes = notes
        self.device = device; self.completedUnits = completedUnits; self.unitName = unitName
        self.points = []; self.energyWh = 0; self.coveredSeconds = 0; self.powerKeys = []
    }
    public static func comparisonIssue(_ a: Recording, _ b: Recording) -> String? {
        guard a.device == b.device else { return "Use recordings from the same Mac." }
        guard a.coverage >= 0.9, b.coverage >= 0.9 else { return "At least 90% power coverage is needed in both recordings." }
        guard a.powerKeys.count == 1, a.powerKeys == b.powerKeys else { return "Use the same power source and measurement scope." }
        guard a.energyPerUnit != nil, b.energyPerUnit != nil, a.unitName == b.unitName else { return "Enter completed work using the same unit in both recordings." }
        return nil
    }
}

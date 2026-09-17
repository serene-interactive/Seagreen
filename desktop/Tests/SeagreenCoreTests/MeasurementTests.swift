import Foundation
#if !STANDALONE_TESTS
import XCTest
#endif
import SeagreenCore

final class MeasurementTests: XCTestCase {
    let battery = PowerReading(watts: 10, source: .battery, scope: "Whole device")
    func testWattHoursAndKilowattHours() {
        var integrator = EnergyIntegrator()
        for second in stride(from: 0, through: 3600, by: 2) { integrator.add(time: Double(second), power: battery) }
        XCTAssertEqual(integrator.wattHours, 10, accuracy: 0.000001)
        XCTAssertEqual(integrator.kilowattHours, 0.01, accuracy: 0.000001)
        XCTAssertEqual(integrator.coveredSeconds, 3600)
    }
    func testTrapezoidalIntegration() {
        var integrator = EnergyIntegrator()
        integrator.add(time: 0, power: battery)
        integrator.add(time: 10, power: PowerReading(watts: 30, source: .battery, scope: "Whole device"))
        XCTAssertEqual(integrator.wattHours, 200 / 3600, accuracy: 0.000001)
    }
    func testMissingSamplesSleepAndSourceChangesAreExcluded() {
        var integrator = EnergyIntegrator()
        integrator.add(time: 0, power: battery); integrator.add(time: 2, power: nil)
        integrator.add(time: 4, power: battery); integrator.add(time: 500, power: battery)
        integrator.add(time: 502, power: PowerReading(watts: 10, source: .powermetrics, scope: "CPU only"))
        integrator.add(time: 504, power: battery)
        XCTAssertEqual(integrator.wattHours, 0)
        XCTAssertEqual(integrator.coveredSeconds, 0)
        integrator.add(time: 506, power: battery)
        XCTAssertEqual(integrator.coveredSeconds, 2)
    }
    func testInvalidPowerRejected() {
        var integrator = EnergyIntegrator()
        integrator.add(time: 0, power: battery)
        integrator.add(time: 1, power: PowerReading(watts: .nan, source: .battery, scope: "Whole device"))
        integrator.add(time: 2, power: battery)
        XCTAssertEqual(integrator.wattHours, 0)
    }
    func testMulticoreCPUAndCounterResets() {
        XCTAssertEqual(MeasurementMath.cpuPercent(previous: 0, current: 4_000_000_000, elapsed: 2), 200)
        XCTAssertNil(MeasurementMath.cpuPercent(previous: 10, current: 0, elapsed: 2))
        XCTAssertNil(MeasurementMath.cpuPercent(previous: 0, current: 10, elapsed: 0))
        XCTAssertNil(MeasurementMath.cpuPercent(previous: 0, current: 10, elapsed: 30))
        XCTAssertNil(MeasurementMath.rate(previous: 20, current: 10, elapsed: 2))
    }
    func testPIDReuseIdentity() {
        XCTAssertNotEqual(ProcessIdentity(pid: 10, started: 100), ProcessIdentity(pid: 10, started: 200))
    }
    func testBatteryUnitsAndChargingExcluded() {
        XCTAssertEqual(MeasurementMath.batteryWatts(millivolts: 12000, milliamps: -1000, pluggedIn: false), 12)
        XCTAssertNil(MeasurementMath.batteryWatts(millivolts: 12000, milliamps: -1000, pluggedIn: true))
        XCTAssertNil(MeasurementMath.batteryWatts(millivolts: 12000, milliamps: 1000, pluggedIn: false))
        XCTAssertNil(MeasurementMath.batteryWatts(millivolts: 12, milliamps: -1000, pluggedIn: false))
    }
    func testPowerMetricsSchemaAndUnits() throws {
        let data = try PropertyListSerialization.data(fromPropertyList: ["processor": ["combined_power": 2500.0, "cpu_power": 1000.0]], format: .xml, options: 0)
        XCTAssertEqual(PowerMetricsReader.decode(data)?.watts, 2.5)
        XCTAssertEqual(PowerMetricsReader.decode(data)?.scope, "CPU + GPU + ANE")
        let unknown = try PropertyListSerialization.data(fromPropertyList: ["watts": 5], format: .xml, options: 0)
        XCTAssertNil(PowerMetricsReader.decode(unknown))
        XCTAssertNil(PowerMetricsReader.decode(Data("not a plist".utf8)))
    }
    func testPowerFilePartialWritesAndStaleness() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: url) }
        var data = try PropertyListSerialization.data(fromPropertyList: ["processor": ["cpu_power": 3000]], format: .xml, options: 0)
        data.append(Data("\0<?xml incomplete".utf8))
        try data.write(to: url)
        XCTAssertEqual(PowerMetricsReader.latest(at: url)?.watts, 3)
        XCTAssertNil(PowerMetricsReader.latest(at: url, now: Date().addingTimeInterval(20)))
    }
    func testRecordingPersistenceAndCSV() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: url) }
        let store = try RecordingStore(directory: url)
        var recording = Recording(title: "Example", started: Date(), device: "test")
        recording.points.append(TimelinePoint(date: Date(), cpu: 50, memoryGB: 2, watts: nil, powerKey: nil))
        try store.save(recording)
        let loaded = try store.load()
        XCTAssertEqual(loaded.count, 1)
        XCTAssertEqual(loaded[0].id, recording.id)
        XCTAssertTrue(RecordingStore.csv(recording).contains("unavailable"))
        try store.delete(recording)
        XCTAssertEqual(try store.load().count, 0)
    }
    func testComparisonRequiresMatchingEvidence() {
        var a = Recording(title: "A", started: Date(), device: "one", completedUnits: 1)
        var b = Recording(title: "B", started: Date(), device: "one", completedUnits: 1)
        XCTAssertNotNil(Recording.comparisonIssue(a, b))
        a.ended = a.started.addingTimeInterval(10); b.ended = b.started.addingTimeInterval(10)
        a.coveredSeconds = 10; b.coveredSeconds = 10
        a.powerKeys = ["battery"]; b.powerKeys = ["battery"]
        XCTAssertNil(Recording.comparisonIssue(a, b))
        b.powerKeys = ["CPU"]
        XCTAssertNotNil(Recording.comparisonIssue(a, b))
        b.powerKeys = ["battery"]; b.device = "two"
        XCTAssertNotNil(Recording.comparisonIssue(a, b))
    }
    func testLiveCollector() {
        let collector = SystemCollector()
        let first = collector.sample()
        XCTAssertFalse(first.processes.isEmpty)
        XCTAssertNil(first.cpuPercent)
        Thread.sleep(forTimeInterval: 0.1)
        let next = collector.sample()
        XCTAssertNil(next.error)
        XCTAssertNotNil(next.cpuPercent)
        XCTAssertTrue(next.processes.contains { $0.id.pid == ProcessInfo.processInfo.processIdentifier })
        XCTAssertTrue(next.totalMemoryBytes > 0)
    }
    func testLiveCPUTimebase() {
        let collector = SystemCollector()
        _ = collector.sample()
        let deadline = ProcessInfo.processInfo.systemUptime + 0.3
        var iterations = 0
        while ProcessInfo.processInfo.systemUptime < deadline { iterations += 1 }
        let next = collector.sample()
        let own = next.processes.first { $0.id.pid == ProcessInfo.processInfo.processIdentifier }
        XCTAssertTrue(iterations > 0)
        XCTAssertTrue((own?.cpuPercent ?? 0) > 15)
        XCTAssertTrue((own?.cpuPercent ?? 1000) < 200)
    }
    static var allTests: [(String, (MeasurementTests) -> () throws -> Void)] = [
        ("testWattHoursAndKilowattHours", testWattHoursAndKilowattHours),
        ("testTrapezoidalIntegration", testTrapezoidalIntegration),
        ("testMissingSamplesSleepAndSourceChangesAreExcluded", testMissingSamplesSleepAndSourceChangesAreExcluded),
        ("testInvalidPowerRejected", testInvalidPowerRejected),
        ("testMulticoreCPUAndCounterResets", testMulticoreCPUAndCounterResets),
        ("testPIDReuseIdentity", testPIDReuseIdentity),
        ("testBatteryUnitsAndChargingExcluded", testBatteryUnitsAndChargingExcluded),
        ("testPowerMetricsSchemaAndUnits", testPowerMetricsSchemaAndUnits),
        ("testPowerFilePartialWritesAndStaleness", testPowerFilePartialWritesAndStaleness),
        ("testRecordingPersistenceAndCSV", testRecordingPersistenceAndCSV),
        ("testComparisonRequiresMatchingEvidence", testComparisonRequiresMatchingEvidence),
        ("testLiveCollector", testLiveCollector),
        ("testLiveCPUTimebase", testLiveCPUTimebase)
    ]
}

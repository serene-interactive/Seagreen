import Foundation
for (name, run) in MeasurementTests.allTests {
    let before = testFailures
    do { try run(MeasurementTests())() } catch { testFailures += 1; print("FAIL \(name): \(error)") }
    if testFailures == before { print("PASS \(name)") }
}
print("\(MeasurementTests.allTests.count) tests; \(testFailures) failures")
exit(testFailures == 0 ? 0 : 1)

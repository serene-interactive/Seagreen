// Command Line Tools installations omit XCTest. Run the same test methods with a small assertion adapter.
import Foundation
class XCTestCase {}
var testFailures = 0
func fail(_ message: String, _ file: StaticString, _ line: UInt) {
    testFailures += 1; print("FAIL \(file):\(line): \(message)")
}
func XCTAssertTrue(_ value: @autoclosure () throws -> Bool, file: StaticString = #file, line: UInt = #line) {
    do { if try !value() { fail("Expected true", file, line) } } catch { fail(String(describing: error), file, line) }
}
func XCTAssertFalse(_ value: @autoclosure () throws -> Bool, file: StaticString = #file, line: UInt = #line) {
    do { if try value() { fail("Expected false", file, line) } } catch { fail(String(describing: error), file, line) }
}
func XCTAssertNil<T>(_ value: @autoclosure () throws -> T?, file: StaticString = #file, line: UInt = #line) {
    do { if try value() != nil { fail("Expected nil", file, line) } } catch { fail(String(describing: error), file, line) }
}
func XCTAssertNotNil<T>(_ value: @autoclosure () throws -> T?, file: StaticString = #file, line: UInt = #line) {
    do { if try value() == nil { fail("Expected value", file, line) } } catch { fail(String(describing: error), file, line) }
}
func XCTAssertEqual<T: Equatable>(_ a: @autoclosure () throws -> T, _ b: @autoclosure () throws -> T, file: StaticString = #file, line: UInt = #line) {
    do { let first = try a(), second = try b(); if first != second { fail("\(first) != \(second)", file, line) } } catch { fail(String(describing: error), file, line) }
}
func XCTAssertNotEqual<T: Equatable>(_ a: T, _ b: T, file: StaticString = #file, line: UInt = #line) { if a == b { fail("Expected different values", file, line) } }
func XCTAssertEqual(_ a: Double, _ b: Double, accuracy: Double, file: StaticString = #file, line: UInt = #line) {
    if !a.isFinite || !b.isFinite || abs(a-b) > accuracy { fail("\(a) != \(b) ± \(accuracy)", file, line) }
}

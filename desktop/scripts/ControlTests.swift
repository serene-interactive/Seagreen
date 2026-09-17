import AppKit
import SGSystem
import SeagreenCore

@main struct ControlTests {
    @MainActor static func main() throws {
        func identity(_ pid: Int32) throws -> ProcessIdentity {
            var info = sg_process()
            guard sg_read_process(pid, &info) != 0 else { throw ProcessControl.failure("Missing test process") }
            return ProcessIdentity(pid: pid, started: info.start_usec)
        }
        func rejected(_ operation: () throws -> Void) {
            do { try operation(); fatalError("Unsafe request was accepted") } catch {}
        }
        rejected { _ = try ProcessControl.request(identity(getpid()), force: true) }
        rejected { _ = try ProcessControl.request(identity(getppid()), force: true) }
        rejected { _ = try ProcessControl.request(ProcessIdentity(pid: 1, started: 1), force: true) }
        for force in [false, true] {
            let child = Process()
            child.executableURL = URL(fileURLWithPath: "/bin/sleep")
            child.arguments = ["90"]
            try child.run()
            defer { if child.isRunning { child.terminate() } }
            let id = try identity(child.processIdentifier)
            rejected { _ = try ProcessControl.request(ProcessIdentity(pid: id.pid, started: id.started + 1), force: force) }
            precondition(child.isRunning)
            _ = try ProcessControl.request(id, force: force)
            let deadline = Date().addingTimeInterval(5)
            while child.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.05) }
            precondition(!child.isRunning, "Selected helper did not exit")
        }
        print("PASS native process controls: quit, force quit, stale identity, self, ancestors and system protection")
    }
}

import AppKit
import SeagreenCore
import SGSystem

@MainActor enum ProcessControl {
    static func checked(_ identity: ProcessIdentity) throws -> sg_process {
        var live = sg_process()
        guard identity.pid > 1, sg_read_process(identity.pid, &live) != 0,
              live.start_usec == identity.started else { throw failure("This process has exited or changed. Select it again from Applications.") }
        var ancestors = Set<Int32>([getpid()])
        var parent = getppid()
        while parent > 1 && !ancestors.contains(parent) {
            ancestors.insert(parent)
            var info = sg_process()
            guard sg_read_process(parent, &info) != 0 else { break }
            parent = info.parent_pid
        }
        let name = withUnsafePointer(to: &live.name) { $0.withMemoryRebound(to: CChar.self, capacity: 256) { String(cString: $0) } }.lowercased()
        guard geteuid() != 0, live.uid == getuid(), !ancestors.contains(identity.pid),
              !["seagreen", "launchd", "kernel_task", "windowserver", "loginwindow"].contains(name) else {
            throw failure("Seagreen, system/session processes, and processes owned by another user are protected.")
        }
        return live
    }
    static func failure(_ message: String) -> NSError { NSError(domain: "Seagreen", code: 1, userInfo: [NSLocalizedDescriptionKey: message]) }
    static func request(_ identity: ProcessIdentity, force: Bool) throws -> String {
        _ = try checked(identity)
        if let app = NSRunningApplication(processIdentifier: identity.pid), app.activationPolicy != .prohibited {
            let accepted = force ? app.forceTerminate() : app.terminate()
            guard accepted else { throw failure("The app declined the request or could not be reached. It may be waiting for you to save work.") }
            return force ? "Force-quit request sent." : "Quit requested. The app may ask you to save work or cancel."
        }
        // Recheck identity immediately before signaling; never target an entire process group.
        _ = try checked(identity)
        guard kill(identity.pid, force ? SIGKILL : SIGTERM) == 0 else { throw failure("The process exited or macOS denied permission.") }
        return force ? "Force-quit request sent." : "Termination requested (SIGTERM). The process may handle or ignore it."
    }
}

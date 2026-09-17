import Foundation
import SeagreenCore

@main struct RowTests {
    static func main() {
        func row(_ id: String, _ name: String) -> AppGroup {
            AppGroup(id: id, name: name, bundle: nil, processes: [])
        }
        let first = [row("1:10", "One"), row("2:10", "Two")]
        let updated = retainingApplicationRows(first, incoming: [row("2:10", "Updated two"), row("1:10", "Updated one")])
        precondition(updated.map(\.id) == ["1:10", "2:10"])
        precondition(updated.map(\.name) == ["Updated one", "Updated two"])
        let reused = retainingApplicationRows(updated, incoming: [row("2:10", "Two"), row("1:11", "New process")])
        precondition(reused.map(\.id) == ["1:10", "2:10", "1:11"])
        precondition(reused[0].processes.isEmpty)
        precondition(retainingApplicationRows([], incoming: first).map(\.id) == first.map(\.id))
        print("PASS stable application identities, live replacement, stopped slots and PID reuse")
    }
}

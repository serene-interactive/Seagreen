import Foundation

public final class RecordingStore {
    public let directory: URL
    public init(directory: URL? = nil) throws {
        self.directory = directory ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Seagreen/Recordings", isDirectory: true)
        try FileManager.default.createDirectory(at: self.directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    }
    public func load() throws -> [Recording] {
        let files = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: [.fileSizeKey])
        return files.filter { $0.pathExtension == "json" }.compactMap { url in
            guard let size = try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize, size < 10_000_000,
                  let data = try? Data(contentsOf: url) else { return nil }
            return try? JSONDecoder().decode(Recording.self, from: data)
        }.sorted { $0.started > $1.started }
    }
    public func save(_ recording: Recording) throws {
        let url = directory.appendingPathComponent(recording.id.uuidString + ".json")
        try JSONEncoder().encode(recording).write(to: url, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
    }
    public func delete(_ recording: Recording) throws {
        try FileManager.default.removeItem(at: directory.appendingPathComponent(recording.id.uuidString + ".json"))
    }
    public static func csv(_ recording: Recording) -> String {
        func quote(_ s: String) -> String { "\"" + s.replacingOccurrences(of: "\"", with: "\"\"") + "\"" }
        let formatter = ISO8601DateFormatter()
        var lines = ["timestamp,cpu_percent,memory_gb,power_watts,power_source_scope"]
        for p in recording.points {
            lines.append([formatter.string(from: p.date), p.cpu.map(String.init(describing:)) ?? "", String(p.memoryGB),
                          p.watts.map(String.init(describing:)) ?? "", quote(p.powerKey ?? "unavailable")].joined(separator: ","))
        }
        return lines.joined(separator: "\n") + "\n"
    }
}

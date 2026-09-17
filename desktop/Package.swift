// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Seagreen",
    platforms: [.macOS(.v13)],
    products: [.executable(name: "Seagreen", targets: ["SeagreenApp"])],
    targets: [
        .target(name: "SGSystem", publicHeadersPath: "include", linkerSettings: [.linkedLibrary("proc")]),
        .target(name: "SeagreenCore", dependencies: ["SGSystem"], linkerSettings: [.linkedFramework("IOKit")]),
        .executableTarget(name: "SeagreenApp", dependencies: ["SeagreenCore", "SGSystem"]),
        .testTarget(name: "SeagreenCoreTests", dependencies: ["SeagreenCore"])
    ]
)

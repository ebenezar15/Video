// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "ClipForge",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "ClipForge", targets: ["ClipForge"]),
        .library(name: "ClipForgeCore", targets: ["ClipForgeCore"]),
    ],
    targets: [
        // Foundation only: models, engine client, engine install/launch, Claude Desktop config.
        .target(name: "ClipForgeCore"),
        // The SwiftUI app.
        .executableTarget(name: "ClipForge", dependencies: ["ClipForgeCore"]),
        .testTarget(name: "ClipForgeCoreTests", dependencies: ["ClipForgeCore"]),
    ]
)

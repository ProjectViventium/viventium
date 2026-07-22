// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "ViventiumBootstrap",
    platforms: [.macOS(.v13)],
    products: [.executable(name: "ViventiumBootstrap", targets: ["ViventiumBootstrap"])],
    targets: [
        .executableTarget(
            name: "ViventiumBootstrap",
            path: "Sources/ViventiumBootstrap",
            exclude: ["Info.plist"]
        ),
    ]
)

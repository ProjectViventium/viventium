// swift-tools-version: 5.10

import PackageDescription

let package = Package(
    name: "ViventiumHelper",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "ViventiumHelper", targets: ["ViventiumHelper"]),
    ],
    targets: [
        .executableTarget(
            name: "ViventiumHelper",
            path: "Sources/ViventiumHelper",
            exclude: [
                "Resources/Info.plist",
                "Resources/Viventium.icns",
            ]),
    ])

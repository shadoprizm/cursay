// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "CursayMac",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .library(name: "CursayCore", targets: ["CursayCore"]),
        .executable(name: "Cursay", targets: ["CursayMac"]),
    ],
    targets: [
        .target(name: "CursayCore"),
        .executableTarget(
            name: "CursayMac",
            dependencies: ["CursayCore"]
        ),
        .testTarget(
            name: "CursayCoreTests",
            dependencies: ["CursayCore"]
        ),
    ]
)

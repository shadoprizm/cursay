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
    dependencies: [
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.10.0"),
    ],
    targets: [
        .target(name: "CursayCore"),
        .executableTarget(
            name: "CursayMac",
            dependencies: [
                "CursayCore",
                .product(name: "Sparkle", package: "Sparkle"),
            ]
        ),
        .testTarget(
            name: "CursayCoreTests",
            dependencies: ["CursayCore"]
        ),
        .testTarget(
            name: "CursayMacTests",
            dependencies: ["CursayMac"]
        ),
    ]
)

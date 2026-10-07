import Foundation
import CursayCore
import os

enum LocalBackendError: LocalizedError {
    case helperMissing
    case launchFailed(String)
    case startupTimedOut
    case serviceUnavailable

    var errorDescription: String? {
        switch self {
        case .helperMissing:
            return "This Cursay build does not contain the Local Whisper helper. Install the current macOS release."
        case let .launchFailed(message):
            return "Local Whisper could not start: \(message)"
        case .startupTimedOut:
            return "Local Whisper did not become ready. Check that another app is not using port 8765."
        case .serviceUnavailable:
            return "The configured transcription service did not answer its health check."
        }
    }
}

@MainActor
final class LocalBackendManager {
    static let endpoint = "http://127.0.0.1:8765/v1/audio/transcriptions"

    private let logger = Logger(subsystem: "io.github.shadoprizm.Cursay", category: "local-backend")
    private var process: Process?

    var helperAvailable: Bool {
        FileManager.default.isExecutableFile(atPath: helperURL.path)
    }

    func ensureRunning(using client: TranscriptionClient) async throws {
        if await client.health(endpoint: Self.endpoint) {
            return
        }
        if let process, process.isRunning {
            try await waitUntilHealthy(using: client)
            return
        }
        guard helperAvailable else {
            throw LocalBackendError.helperMissing
        }

        let process = Process()
        process.executableURL = helperURL
        process.currentDirectoryURL = helperURL.deletingLastPathComponent()
        process.arguments = [
            "--parent-pid", String(ProcessInfo.processInfo.processIdentifier),
            "--port", "8765",
        ]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
        } catch {
            throw LocalBackendError.launchFailed(error.localizedDescription)
        }
        self.process = process
        logger.notice("Started bundled Local Whisper helper with pid \(process.processIdentifier, privacy: .public)")
        try await waitUntilHealthy(using: client)
    }

    func stop() {
        guard let process, process.isRunning else { return }
        process.terminate()
        self.process = nil
    }

    private var helperURL: URL {
        (Bundle.main.resourceURL ?? Bundle.main.bundleURL)
            .appendingPathComponent("CursaySTT", isDirectory: true)
            .appendingPathComponent("CursaySTT", isDirectory: false)
    }

    private func waitUntilHealthy(using client: TranscriptionClient) async throws {
        for _ in 0..<160 {
            if await client.health(endpoint: Self.endpoint) {
                return
            }
            if let process, !process.isRunning {
                throw LocalBackendError.launchFailed("the helper exited with status \(process.terminationStatus)")
            }
            try await Task.sleep(for: .milliseconds(250))
        }
        stop()
        throw LocalBackendError.startupTimedOut
    }
}

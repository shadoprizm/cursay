import AppKit
import AVFoundation
import Combine
import CursayCore
import Foundation
import ServiceManagement

enum AppPhase: Equatable {
    case ready
    case recording
    case transcribing
    case complete(pasted: Bool)
    case failed(String)

    var isRecording: Bool {
        self == .recording
    }

    var isBusy: Bool {
        self == .recording || self == .transcribing
    }

    var statusText: String {
        switch self {
        case .ready:
            return "Ready — hold the shortcut to dictate"
        case .recording:
            return "Listening… release the shortcut when you’re finished"
        case .transcribing:
            return "Transcribing and cleaning your words…"
        case let .complete(pasted):
            return pasted ? "Pasted into your active app" : "Copied to the clipboard"
        case let .failed(message):
            return message
        }
    }
}

enum BackendState: Equatable {
    case checking
    case available
    case unavailable

    var label: String {
        switch self {
        case .checking: return "Checking…"
        case .available: return "Connected"
        case .unavailable: return "Unavailable"
        }
    }
}

@MainActor
final class AppModel: ObservableObject {
    @Published private(set) var phase: AppPhase = .ready
    @Published private(set) var history: [Dictation] = []
    @Published private(set) var latestText = ""
    @Published private(set) var backendState: BackendState = .checking
    @Published private(set) var shortcutRegistered = false
    @Published private(set) var shortcutLabel = "Ctrl + Space"
    @Published private(set) var launchAtLogin = false
    @Published var searchQuery = ""

    let settings = AppSettings()
    let pasteController = PasteController()

    private let recorder = AudioRecorder()
    private let transcriptionClient = TranscriptionClient()
    private let hotKey = GlobalHotKey()
    private var historyStore: HistoryStore?
    private var recordingTarget: NSRunningApplication?
    private var shortcutHeld = false

    init() {
        do {
            let store = try HistoryStore()
            historyStore = store
            history = try store.load()
        } catch {
            phase = .failed(error.localizedDescription)
        }

        launchAtLogin = SMAppService.mainApp.status == .enabled
        hotKey.onPressed = { [weak self] in self?.shortcutPressed() }
        hotKey.onReleased = { [weak self] in self?.shortcutReleased() }
        do {
            shortcutLabel = try hotKey.registerPreferredShortcut()
            shortcutRegistered = true
        } catch {
            shortcutRegistered = false
            phase = .failed(error.localizedDescription)
        }

        Task {
            _ = await AudioRecorder.requestPermission()
            await checkBackend()
        }
    }

    var filteredHistory: [Dictation] {
        HistoryStore.search(searchQuery, in: history)
    }

    var stats: HistoryStats {
        HistoryStore.stats(for: history)
    }

    var microphoneStatus: String {
        switch AudioRecorder.authorizationStatus {
        case .authorized: return "Allowed"
        case .denied: return "Denied"
        case .restricted: return "Restricted"
        case .notDetermined: return "Not requested"
        @unknown default: return "Unknown"
        }
    }

    func toggleRecording() {
        if recorder.isRecording {
            stopRecording()
        } else {
            Task {
                let allowed = await AudioRecorder.requestPermission()
                guard allowed else {
                    phase = .failed(AudioRecorderError.permissionDenied.localizedDescription)
                    return
                }
                startRecording()
            }
        }
    }

    func startRecording() {
        guard !phase.isBusy else { return }
        let frontmost = NSWorkspace.shared.frontmostApplication
        recordingTarget = frontmost?.bundleIdentifier == Bundle.main.bundleIdentifier ? nil : frontmost
        do {
            try recorder.start()
            phase = .recording
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func stopRecording() {
        guard recorder.isRecording else { return }
        do {
            let recording = try recorder.stop()
            phase = .transcribing
            Task {
                await process(recordingURL: recording.url, measuredDuration: recording.duration)
            }
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    func copy(_ text: String) {
        if pasteController.copy(text) {
            phase = .complete(pasted: false)
        } else {
            phase = .failed("Cursay could not update the clipboard.")
        }
    }

    func delete(_ dictation: Dictation) {
        history.removeAll { $0.id == dictation.id }
        persistHistory()
    }

    func clearHistory() {
        history.removeAll()
        persistHistory()
    }

    func checkBackend() async {
        backendState = .checking
        backendState = await transcriptionClient.health(endpoint: settings.endpoint) ? .available : .unavailable
    }

    func requestAccessibilityAccess() {
        pasteController.requestAccessibilityAccess()
    }

    func setLaunchAtLogin(_ enabled: Bool) {
        do {
            if enabled {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
            launchAtLogin = enabled
        } catch {
            launchAtLogin = SMAppService.mainApp.status == .enabled
            phase = .failed("Launch at login could not be changed: \(error.localizedDescription)")
        }
    }

    private func shortcutPressed() {
        shortcutHeld = true
        guard !phase.isBusy else { return }
        if AudioRecorder.authorizationStatus == .authorized {
            startRecording()
            return
        }
        Task {
            let allowed = await AudioRecorder.requestPermission()
            guard allowed else {
                phase = .failed(AudioRecorderError.permissionDenied.localizedDescription)
                return
            }
            if shortcutHeld {
                startRecording()
            }
        }
    }

    private func shortcutReleased() {
        shortcutHeld = false
        stopRecording()
    }

    private func process(recordingURL: URL, measuredDuration: Double) async {
        var workingURL = recordingURL
        if settings.preserveRecordings {
            do {
                workingURL = try preserveRecording(recordingURL)
            } catch {
                phase = .failed("The recording could not be saved: \(error.localizedDescription)")
                try? FileManager.default.removeItem(at: recordingURL)
                return
            }
        }

        do {
            let result = try await transcriptionClient.transcribe(
                audioURL: workingURL,
                endpoint: settings.endpoint,
                model: settings.model,
                language: settings.language
            )
            let raw = result.text.trimmingCharacters(in: .whitespacesAndNewlines)
            let (final, metadata) = TranscriptCleaner.clean(
                raw,
                mode: settings.mode,
                removeFillers: settings.removeFillers
            )
            let entry = Dictation(
                rawText: raw,
                finalText: final,
                mode: settings.mode,
                language: result.language ?? settings.language,
                durationSeconds: result.duration ?? measuredDuration,
                provider: result.provider ?? "speech service",
                model: result.model ?? settings.model,
                fillersRemoved: metadata.fillersRemoved,
                recordingPath: settings.preserveRecordings ? workingURL.path : nil
            )
            history.insert(entry, at: 0)
            persistHistory()
            latestText = final

            let pasted: Bool
            if settings.autoPaste {
                pasted = await pasteController.paste(final, into: recordingTarget)
            } else {
                pasted = false
                _ = pasteController.copy(final)
            }
            phase = .complete(pasted: pasted)
        } catch {
            phase = .failed(error.localizedDescription)
        }

        if !settings.preserveRecordings {
            try? FileManager.default.removeItem(at: workingURL)
        }
        recordingTarget = nil
    }

    private func preserveRecording(_ source: URL) throws -> URL {
        let base = try FileManager.default.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let directory = base
            .appendingPathComponent("Cursay", isDirectory: true)
            .appendingPathComponent("Recordings", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let destination = directory.appendingPathComponent(source.lastPathComponent)
        try FileManager.default.moveItem(at: source, to: destination)
        return destination
    }

    private func persistHistory() {
        do {
            try historyStore?.save(history)
        } catch {
            phase = .failed("History could not be saved: \(error.localizedDescription)")
        }
    }
}

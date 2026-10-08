import AppKit
import AVFoundation
import Combine
import CursayCore
import Foundation
import ServiceManagement
import os

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
    case unavailable(String)
    case upgradeRequired

    var label: String {
        switch self {
        case .checking: return "Checking…"
        case .available: return "Connected"
        case .unavailable: return "Unavailable"
        case .upgradeRequired: return "Upgrade to Pro"
        }
    }

    var detail: String? {
        if self == .upgradeRequired { return CloudAccess.upgradeRequired.message }
        if case let .unavailable(message) = self { return message }
        return nil
    }
}

@MainActor
final class AppModel: ObservableObject {
    private let logger = Logger(subsystem: "io.github.shadoprizm.Cursay", category: "application")

    @Published private(set) var phase: AppPhase = .ready
    @Published private(set) var history: [Dictation] = []
    @Published private(set) var latestText = ""
    @Published private(set) var backendState: BackendState = .checking
    @Published private(set) var shortcutRegistered = false
    @Published private(set) var shortcutLabel = "Ctrl + Space"
    @Published private(set) var launchAtLogin = false
    @Published private(set) var cloudStatus = "Not linked"
    @Published private(set) var cloudUsage = ""
    @Published private(set) var cloudLinked = false
    @Published private(set) var cloudAccess: CloudAccess?
    @Published var showCloudUpgradePrompt = false
    @Published private(set) var lastFallbackReason: String?
    @Published var searchQuery = ""

    let settings = AppSettings()
    let pasteController = PasteController()
    let updates = UpdateController()

    private let recorder = AudioRecorder()
    private let transcriptionClient = TranscriptionClient()
    private let polishClient = PolishClient()
    private let cloudClient = CloudClient(baseURL: URL(string: "https://cursay.com")!)
    private let localBackend = LocalBackendManager()
    private let hotKey = GlobalHotKey()
    private var historyStore: HistoryStore?
    private var recordingTarget: PasteTarget?
    private var shortcutHeld = false
    private var backendCheckGeneration = 0
    private var cloudPreflight: CloudTranscriptionPreflight?

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
            let registered = try hotKey.register(settings.shortcut)
            settings.shortcut = registered
            shortcutLabel = registered.displayName
            shortcutRegistered = true
            logger.notice("Global shortcut registered: \(self.shortcutLabel, privacy: .public)")
        } catch {
            shortcutRegistered = false
            phase = .failed(error.localizedDescription)
            logger.error("Global shortcut registration failed: \(error.localizedDescription, privacy: .public)")
        }

        let accessibilityAllowed = pasteController.isAccessibilityTrusted
        logger.notice("Accessibility permission allowed: \(accessibilityAllowed, privacy: .public)")
        if settings.autoPaste && !accessibilityAllowed {
            pasteController.requestAccessibilityAccess()
        }

        Task {
            let microphoneAllowed = await AudioRecorder.requestPermission()
            logger.notice("Microphone permission allowed: \(microphoneAllowed, privacy: .public)")
            await checkBackend()
            await refreshCloudAccount()
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
        recordingTarget = pasteController.captureTarget()
        do {
            try recorder.start()
            if settings.provider == .cloud {
                let client = cloudClient
                cloudPreflight = CloudTranscriptionPreflight { try await client.account() }
            }
            phase = .recording
            logger.notice("Recording started")
        } catch {
            phase = .failed(error.localizedDescription)
            logger.error("Recording failed to start: \(error.localizedDescription, privacy: .public)")
        }
    }

    func stopRecording() {
        guard recorder.isRecording else { return }
        do {
            let recording = try recorder.stop()
            phase = .transcribing
            logger.notice("Recording stopped; transcription started")
            Task {
                await process(recordingURL: recording.url, measuredDuration: recording.duration)
            }
        } catch {
            cloudPreflight?.cancel()
            cloudPreflight = nil
            phase = .failed(error.localizedDescription)
            logger.error("Recording failed to stop: \(error.localizedDescription, privacy: .public)")
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
        backendCheckGeneration += 1
        let generation = backendCheckGeneration
        let provider = settings.provider
        backendState = .checking
        if provider == .cloud {
            await refreshCloudAccount()
            guard generation == backendCheckGeneration, settings.provider == provider else { return }
            switch cloudAccess {
            case .available: backendState = .available
            case .upgradeRequired: backendState = .upgradeRequired
            case .allowanceExhausted: backendState = .unavailable(CloudAccess.allowanceExhausted.message)
            case nil: backendState = .unavailable(cloudStatus)
            }
        } else {
            do {
                if settings.provider == .local {
                    try await localBackend.ensureRunning(using: transcriptionClient)
                } else if await transcriptionClient.health(endpoint: settings.endpoint) == false {
                    throw LocalBackendError.serviceUnavailable
                }
                guard generation == backendCheckGeneration, settings.provider == provider else { return }
                backendState = .available
                logger.notice("Transcription backend available")
            } catch {
                guard generation == backendCheckGeneration, settings.provider == provider else { return }
                backendState = .unavailable(error.localizedDescription)
                logger.error("Transcription backend unavailable: \(error.localizedDescription, privacy: .public)")
            }
        }
    }

    func selectProvider(_ provider: TranscriptionProvider) {
        settings.provider = provider
        Task {
            await checkBackend()
            if settings.provider == .cloud, backendState == .upgradeRequired {
                showCloudUpgradePrompt = true
            }
        }
    }

    var cloudAccessNotice: String? {
        guard settings.provider == .cloud, let access = cloudAccess, access != .available else { return nil }
        return access.message + (settings.cloudLocalFallback ? " Dictation will use free Local Whisper." : " Cloud dictation is unavailable.")
    }

    func openCloudUpgrade() {
        NSWorkspace.shared.open(URL(string: "https://cursay.com/account")!)
    }

    func linkCloudDevice() {
        cloudStatus = "Creating a secure linking code…"
        Task {
            do {
                let authorization = try await cloudClient.beginLink()
                cloudStatus = "Code \(authorization.userCode) — waiting for approval"
                NSWorkspace.shared.open(authorization.verificationUriComplete)
                let deadline = Date().addingTimeInterval(TimeInterval(authorization.expiresIn))
                while Date() < deadline {
                    try await Task.sleep(for: .seconds(max(2, authorization.interval)))
                    if try await cloudClient.pollLink(deviceCode: authorization.deviceCode) {
                        await refreshCloudAccount()
                        if settings.provider == .cloud { await checkBackend() }
                        return
                    }
                }
                cloudStatus = "The linking code expired. Try again."
            } catch {
                cloudStatus = error.localizedDescription
                cloudLinked = false
            }
        }
    }

    func refreshCloudAccount() async {
        do {
            let account = try await cloudClient.account()
            cloudLinked = true
            cloudAccess = account.access
            cloudStatus = "Linked · \(account.plan.capitalized) · \(account.deviceCount) of \(account.deviceLimit) devices"
            cloudUsage = account.access == .upgradeRequired
                ? "Cloud transcription requires Cursay Pro. Local Whisper is free and unlimited."
                : "\(account.remainingSeconds / 60) of \(account.allowanceSeconds / 60) cloud minutes remaining"
        } catch {
            cloudLinked = false
            cloudAccess = nil
            if let cloudError = error as? CloudClientError, case .notLinked = cloudError {
                cloudAccess = .upgradeRequired
            }
            cloudStatus = error.localizedDescription
            cloudUsage = ""
        }
    }

    func signOutCloud() {
        Task {
            do {
                try await cloudClient.revokeAndSignOut()
                cloudLinked = false
                cloudAccess = nil
                cloudStatus = "This Mac is signed out and revoked."
                cloudUsage = ""
                if settings.provider == .cloud { backendState = .unavailable("Link this Mac to use Cursay Cloud.") }
            } catch {
                phase = .failed(error.localizedDescription)
            }
        }
    }

    func requestAccessibilityAccess() {
        pasteController.requestAccessibilityAccess()
    }

    func setShortcut(_ choice: ShortcutChoice) {
        let previous = settings.shortcut
        do {
            let registered = try hotKey.register(choice)
            settings.shortcut = registered
            shortcutLabel = registered.displayName
            shortcutRegistered = true
        } catch {
            if let restored = try? hotKey.register(previous) {
                settings.shortcut = restored
                shortcutLabel = restored.displayName
                shortcutRegistered = true
            } else {
                shortcutRegistered = false
            }
            phase = .failed(error.localizedDescription)
        }
    }

    func checkForUpdates() {
        updates.checkForUpdates()
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
        let preflight = cloudPreflight
        cloudPreflight = nil
        defer { preflight?.cancel() }
        let processingStarted = ContinuousClock.now
        var transcriptionFinished = processingStarted
        var polishFinished = processingStarted
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
            let result: TranscriptionResult
            var cloudSucceeded = false
            lastFallbackReason = nil
            switch settings.provider {
            case .cloud:
                do {
                    result = try await cloudClient.transcribe(
                        audioURL: workingURL, language: settings.language, preflight: preflight
                    )
                    cloudSucceeded = true
                } catch {
                    guard settings.cloudLocalFallback else { throw error }
                    let cloudError = error
                    try await localBackend.ensureRunning(using: transcriptionClient)
                    lastFallbackReason = "Cursay Cloud was unavailable (\(cloudError.localizedDescription)). Local Whisper was used."
                    result = try await transcriptionClient.transcribe(
                        audioURL: workingURL,
                        endpoint: LocalBackendManager.endpoint,
                        model: "whisper-base.en",
                        language: settings.language
                    )
                }
            case .local:
                try await localBackend.ensureRunning(using: transcriptionClient)
                result = try await transcriptionClient.transcribe(
                    audioURL: workingURL,
                    endpoint: LocalBackendManager.endpoint,
                    model: "whisper-base.en",
                    language: settings.language
                )
            case .custom:
                result = try await transcriptionClient.transcribe(
                    audioURL: workingURL,
                    endpoint: settings.endpoint,
                    model: settings.model,
                    language: settings.language
                )
            }
            transcriptionFinished = .now
            let raw = result.text.trimmingCharacters(in: .whitespacesAndNewlines)
            var (final, metadata) = TranscriptCleaner.clean(
                raw,
                mode: settings.mode,
                removeFillers: settings.removeFillers
            )
            if settings.smartPolish && [.professional, .casual, .prompt].contains(settings.mode) {
                do {
                    if cloudSucceeded, let grant = result.polishGrant {
                        final = try await cloudClient.polish(text: final, style: settings.mode, grant: grant)
                    } else if settings.provider != .cloud {
                        final = try await polishClient.polish(
                            final, mode: settings.mode, endpoint: settings.polishEndpoint, model: settings.polishModel
                        )
                    }
                } catch {
                    let notice = "Smart Polish was unavailable (\(error.localizedDescription)); basic cleanup was kept."
                    lastFallbackReason = [lastFallbackReason, notice].compactMap { $0 }.joined(separator: " ")
                }
            }
            polishFinished = .now
            let entry = Dictation(
                rawText: raw,
                finalText: final,
                mode: settings.mode,
                language: result.language ?? settings.language,
                durationSeconds: result.duration ?? measuredDuration,
                provider: result.provider ?? "speech service",
                model: result.model ?? (settings.provider == .local ? "whisper-base.en" : settings.model),
                fillersRemoved: metadata.fillersRemoved,
                recordingPath: settings.preserveRecordings ? workingURL.path : nil,
                costUsd: result.reportedCostUsd
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
            logger.notice("Dictation completed; automatic paste succeeded: \(pasted, privacy: .public)")
            let sttTime = processingStarted.duration(to: transcriptionFinished)
            let polishTime = transcriptionFinished.duration(to: polishFinished)
            let totalTime = processingStarted.duration(to: .now)
            logger.notice("Dictation timing; speech: \(String(describing: sttTime), privacy: .public), polish: \(String(describing: polishTime), privacy: .public), total: \(String(describing: totalTime), privacy: .public)")
            if cloudSucceeded { await refreshCloudAccount() }
        } catch {
            phase = .failed(error.localizedDescription)
            logger.error("Dictation failed: \(error.localizedDescription, privacy: .public)")
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

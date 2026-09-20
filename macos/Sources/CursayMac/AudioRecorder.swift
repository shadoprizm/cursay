import AVFoundation
import Foundation

enum AudioRecorderError: LocalizedError {
    case permissionDenied
    case couldNotStart
    case notRecording
    case emptyRecording

    var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "Microphone access is required. Enable Cursay in System Settings → Privacy & Security → Microphone."
        case .couldNotStart:
            return "Cursay could not start the microphone recording."
        case .notRecording:
            return "There is no recording in progress."
        case .emptyRecording:
            return "No microphone audio was captured."
        }
    }
}

@MainActor
final class AudioRecorder: NSObject {
    private var recorder: AVAudioRecorder?
    private var startedAt: Date?

    var isRecording: Bool {
        recorder?.isRecording == true
    }

    static var authorizationStatus: AVAuthorizationStatus {
        AVCaptureDevice.authorizationStatus(for: .audio)
    }

    static func requestPermission() async -> Bool {
        if authorizationStatus == .authorized { return true }
        if authorizationStatus == .denied || authorizationStatus == .restricted { return false }
        return await AVCaptureDevice.requestAccess(for: .audio)
    }

    func start() throws {
        guard Self.authorizationStatus == .authorized else {
            throw AudioRecorderError.permissionDenied
        }
        guard !isRecording else { return }

        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("Cursay", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let output = directory.appendingPathComponent("dictation-\(UUID().uuidString).wav")
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16_000.0,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsFloatKey: false,
        ]
        let nextRecorder = try AVAudioRecorder(url: output, settings: settings)
        nextRecorder.isMeteringEnabled = true
        nextRecorder.prepareToRecord()
        guard nextRecorder.record() else {
            throw AudioRecorderError.couldNotStart
        }
        recorder = nextRecorder
        startedAt = Date()
    }

    func stop() throws -> (url: URL, duration: Double) {
        guard let recorder, recorder.isRecording else {
            throw AudioRecorderError.notRecording
        }
        let duration = max(0, Date().timeIntervalSince(startedAt ?? Date()))
        recorder.stop()
        let url = recorder.url
        self.recorder = nil
        startedAt = nil

        let values = try url.resourceValues(forKeys: [.fileSizeKey])
        guard (values.fileSize ?? 0) > 44 else {
            try? FileManager.default.removeItem(at: url)
            throw AudioRecorderError.emptyRecording
        }
        return (url, duration)
    }

    func cancel() {
        guard let recorder else { return }
        recorder.stop()
        try? FileManager.default.removeItem(at: recorder.url)
        self.recorder = nil
        startedAt = nil
    }
}

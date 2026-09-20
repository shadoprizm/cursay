import Foundation

public enum DictationMode: String, CaseIterable, Codable, Identifiable, Sendable {
    case professional
    case casual
    case code
    case raw

    public var id: String { rawValue }

    public var displayName: String {
        rawValue.capitalized
    }
}

public struct TranscriptMetadata: Equatable, Sendable {
    public let fillersRemoved: [String]

    public init(fillersRemoved: [String]) {
        self.fillersRemoved = fillersRemoved
    }
}

public struct TranscriptionResult: Codable, Sendable {
    public let text: String
    public let language: String?
    public let duration: Double?
    public let provider: String?
    public let model: String?

    public init(
        text: String,
        language: String? = nil,
        duration: Double? = nil,
        provider: String? = nil,
        model: String? = nil
    ) {
        self.text = text
        self.language = language
        self.duration = duration
        self.provider = provider
        self.model = model
    }
}

public struct Dictation: Identifiable, Codable, Equatable, Sendable {
    public let id: UUID
    public let createdAt: Date
    public let rawText: String
    public let finalText: String
    public let mode: DictationMode
    public let language: String
    public let durationSeconds: Double
    public let provider: String
    public let model: String
    public let fillersRemoved: [String]
    public let recordingPath: String?

    public init(
        id: UUID = UUID(),
        createdAt: Date = Date(),
        rawText: String,
        finalText: String,
        mode: DictationMode,
        language: String,
        durationSeconds: Double,
        provider: String,
        model: String,
        fillersRemoved: [String] = [],
        recordingPath: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.rawText = rawText
        self.finalText = finalText
        self.mode = mode
        self.language = language
        self.durationSeconds = durationSeconds
        self.provider = provider
        self.model = model
        self.fillersRemoved = fillersRemoved
        self.recordingPath = recordingPath
    }

    public var wordCount: Int {
        finalText.split(whereSeparator: { $0.isWhitespace }).count
    }
}

public struct FillerStat: Identifiable, Equatable, Sendable {
    public var id: String { word }
    public let word: String
    public let count: Int

    public init(word: String, count: Int) {
        self.word = word
        self.count = count
    }
}

public struct HistoryStats: Equatable, Sendable {
    public let dictations: Int
    public let words: Int
    public let seconds: Double
    public let fillers: [FillerStat]

    public init(dictations: Int, words: Int, seconds: Double, fillers: [FillerStat]) {
        self.dictations = dictations
        self.words = words
        self.seconds = seconds
        self.fillers = fillers
    }
}

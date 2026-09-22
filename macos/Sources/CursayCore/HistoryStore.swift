import Foundation

public enum HistoryStoreError: LocalizedError {
    case applicationSupportUnavailable

    public var errorDescription: String? {
        switch self {
        case .applicationSupportUnavailable:
            return "Cursay could not open its Application Support folder."
        }
    }
}

public final class HistoryStore {
    public let fileURL: URL

    public init(directory: URL? = nil) throws {
        let baseDirectory: URL
        if let directory {
            baseDirectory = directory
        } else {
            guard let applicationSupport = FileManager.default.urls(
                for: .applicationSupportDirectory,
                in: .userDomainMask
            ).first else {
                throw HistoryStoreError.applicationSupportUnavailable
            }
            baseDirectory = applicationSupport.appendingPathComponent("Cursay", isDirectory: true)
        }
        try FileManager.default.createDirectory(at: baseDirectory, withIntermediateDirectories: true)
        fileURL = baseDirectory.appendingPathComponent("history.json")
    }

    public func load() throws -> [Dictation] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let data = try Data(contentsOf: fileURL)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .secondsSince1970
        return try decoder.decode([Dictation].self, from: data).sorted { $0.createdAt > $1.createdAt }
    }

    public func save(_ dictations: [Dictation]) throws {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .secondsSince1970
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(dictations)
        try data.write(to: fileURL, options: [.atomic])
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: fileURL.path)
    }

    public static func search(_ query: String, in dictations: [Dictation]) -> [Dictation] {
        let needle = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !needle.isEmpty else { return dictations }
        return dictations.filter {
            $0.finalText.localizedCaseInsensitiveContains(needle)
                || $0.rawText.localizedCaseInsensitiveContains(needle)
        }
    }

    public static func stats(for dictations: [Dictation]) -> HistoryStats {
        var fillerCounts: [String: Int] = [:]
        for dictation in dictations {
            for filler in dictation.fillersRemoved {
                fillerCounts[filler.lowercased(), default: 0] += 1
            }
        }
        let fillers = fillerCounts
            .sorted { lhs, rhs in
                lhs.value == rhs.value ? lhs.key < rhs.key : lhs.value > rhs.value
            }
            .prefix(10)
            .map { FillerStat(word: $0.key, count: $0.value) }
        return HistoryStats(
            dictations: dictations.count,
            words: dictations.reduce(0) { $0 + $1.wordCount },
            seconds: dictations.reduce(0) { $0 + $1.durationSeconds },
            fillers: fillers
        )
    }
}

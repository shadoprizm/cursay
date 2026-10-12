import Foundation

public struct DailyDictationSpeed: Identifiable, Equatable, Sendable {
    public var id: Date { day }
    public let day: Date
    public var words = 0
    public var dictations = 0
    public var timedWords = 0
    public var seconds = 0.0
    public var timedDictations = 0
    public var segment = 0
    public var wpm: Double? { DictationSpeed.rate(words: timedWords, seconds: seconds) }
}

public struct DictationSpeedSummary: Equatable, Sendable {
    public let days: Int
    public let daily: [DailyDictationSpeed]
    public let averageWPM: Double?
    public let lifetimeWPM: Double?
    public let latestWPM: Double?
    public var words: Int { daily.reduce(0) { $0 + $1.words } }
    public var timedDictations: Int { daily.reduce(0) { $0 + $1.timedDictations } }
}

public enum DictationSpeed {
    public static func rate(words: Int, seconds: Double) -> Double? {
        guard words > 0, seconds > 0, seconds.isFinite else { return nil }
        return Double(words) * 60 / seconds
    }

    public static func summarize(
        _ dictations: [Dictation], days: Int = 30, now: Date = Date(), calendar: Calendar = .current
    ) -> DictationSpeedSummary {
        precondition([14, 30, 90].contains(days))
        let today = calendar.startOfDay(for: now)
        let start = calendar.date(byAdding: .day, value: -(days - 1), to: today)!
        var daily = (0..<days).map {
            DailyDictationSpeed(day: calendar.date(byAdding: .day, value: $0, to: start)!)
        }
        let indices = Dictionary(uniqueKeysWithValues: daily.enumerated().map { ($0.element.day, $0.offset) })
        var totalWords = 0
        var totalSeconds = 0.0
        for dictation in dictations {
            let timed = rate(words: dictation.wordCount, seconds: dictation.durationSeconds) != nil
            if timed {
                totalWords += dictation.wordCount
                totalSeconds += dictation.durationSeconds
            }
            guard let index = indices[calendar.startOfDay(for: dictation.createdAt)] else { continue }
            daily[index].words += dictation.wordCount
            daily[index].dictations += 1
            if timed {
                daily[index].timedWords += dictation.wordCount
                daily[index].seconds += dictation.durationSeconds
                daily[index].timedDictations += 1
            }
        }
        var segment = 0
        for index in daily.indices {
            if daily[index].wpm == nil { segment += 1 }
            daily[index].segment = segment
        }
        let latest = dictations.max { $0.createdAt < $1.createdAt }
        return DictationSpeedSummary(
            days: days, daily: daily,
            averageWPM: rate(
                words: daily.reduce(0) { $0 + $1.timedWords },
                seconds: daily.reduce(0) { $0 + $1.seconds }
            ),
            lifetimeWPM: rate(words: totalWords, seconds: totalSeconds),
            latestWPM: latest.flatMap { rate(words: $0.wordCount, seconds: $0.durationSeconds) }
        )
    }
}

import CursayCore
import Foundation
import XCTest

final class DictationSpeedTests: XCTestCase {
    struct Fixture: Decodable {
        struct Row: Decodable {
            let created_at: String
            let word_count: Int
            let duration_seconds: Double
        }
        struct Expected: Decodable {
            let wpm: Double?
            let lifetime_wpm: Double?
            let latest_wpm: Double?
            let words: Int
            let timed_count: Int
            let daily: [String: Double?]
        }
        let name: String
        let now: String
        let timezone: String
        let days: Int
        let rows: [Row]
        let expected: Expected
    }

    func testSharedNativeSpeedContract() throws {
        let root = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
        let fixtures = try JSONDecoder().decode(
            [Fixture].self, from: Data(contentsOf: root.appendingPathComponent("tests/fixtures/dictation_speed.json"))
        )
        let parser = ISO8601DateFormatter()
        for fixture in fixtures {
            var calendar = Calendar(identifier: .gregorian)
            calendar.timeZone = TimeZone(identifier: fixture.timezone)!
            let dictations = fixture.rows.map { row in
                Dictation(
                    createdAt: parser.date(from: row.created_at)!, rawText: "",
                    finalText: Array(repeating: "word", count: row.word_count).joined(separator: " "),
                    mode: .raw, language: "en", durationSeconds: row.duration_seconds, provider: "local", model: "whisper"
                )
            }
            let summary = DictationSpeed.summarize(
                dictations, days: fixture.days, now: parser.date(from: fixture.now)!, calendar: calendar
            )
            assertRate(summary.averageWPM, fixture.expected.wpm, fixture.name)
            assertRate(summary.lifetimeWPM, fixture.expected.lifetime_wpm, fixture.name)
            assertRate(summary.latestWPM, fixture.expected.latest_wpm, fixture.name)
            XCTAssertEqual(summary.words, fixture.expected.words, fixture.name)
            XCTAssertEqual(summary.timedDictations, fixture.expected.timed_count, fixture.name)
            XCTAssertEqual(summary.daily.count, fixture.days)
            let formatter = DateFormatter()
            formatter.calendar = calendar
            formatter.timeZone = calendar.timeZone
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.dateFormat = "yyyy-MM-dd"
            for (day, expected) in fixture.expected.daily {
                let actual = try XCTUnwrap(summary.daily.first { formatter.string(from: $0.day) == day })
                assertRate(actual.wpm, expected, fixture.name + " " + day)
            }
        }
    }

    func testMissingOrInvalidDurationHasNoSpeed() {
        for seconds in [0, -1, Double.infinity, Double.nan] {
            XCTAssertNil(DictationSpeed.rate(words: 100, seconds: seconds))
        }
        XCTAssertNil(DictationSpeed.rate(words: 0, seconds: 60))
        XCTAssertEqual(DictationSpeed.rate(words: 100, seconds: 30), 200)
    }

    private func assertRate(_ actual: Double?, _ expected: Double?, _ name: String) {
        if let expected {
            XCTAssertEqual(actual ?? .nan, expected, accuracy: 0.000001, name)
        } else {
            XCTAssertNil(actual, name)
        }
    }
}

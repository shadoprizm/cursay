import CursayCore
import Foundation
import XCTest

final class HistoryStoreTests: XCTestCase {
    func testSaveLoadSearchAndStats() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("CursayTests-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = try HistoryStore(directory: directory)
        let entry = Dictation(
            createdAt: Date(timeIntervalSince1970: 1_700_000_000),
            rawText: "um hello there",
            finalText: "Hello there.",
            mode: .professional,
            language: "en",
            durationSeconds: 2.5,
            provider: "test",
            model: "test-model",
            fillersRemoved: ["um"]
        )

        try store.save([entry])
        let loaded = try store.load()
        XCTAssertEqual(loaded, [entry])
        XCTAssertEqual(HistoryStore.search("hello", in: loaded), [entry])

        let stats = HistoryStore.stats(for: loaded)
        XCTAssertEqual(stats.dictations, 1)
        XCTAssertEqual(stats.words, 2)
        XCTAssertEqual(stats.seconds, 2.5)
        XCTAssertEqual(stats.fillers.first?.word, "um")
        XCTAssertEqual(stats.fillers.first?.count, 1)
        XCTAssertEqual(stats.cost.formattedTotal, "—")
    }

    func testOlderHistoryWithoutCostStillDecodes() throws {
        let data = """
        [{"id":"00000000-0000-0000-0000-000000000001","createdAt":1700000000,
          "rawText":"hello","finalText":"Hello.","mode":"professional","language":"en",
          "durationSeconds":2.5,"provider":"cursay-local","model":"whisper-base.en",
          "fillersRemoved":[],"recordingPath":null}]
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .secondsSince1970

        let decoded = try decoder.decode([Dictation].self, from: data)

        XCTAssertNil(decoded[0].costUsd)
        XCTAssertEqual(HistoryStore.stats(for: decoded).cost.formattedTotal, "$0.00")
    }
}

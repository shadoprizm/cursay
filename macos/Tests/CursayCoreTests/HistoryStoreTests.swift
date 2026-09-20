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
    }
}

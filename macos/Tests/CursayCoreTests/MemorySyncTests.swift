import XCTest
@testable import CursayCore

final class MemorySyncTests: XCTestCase {
    private func snapshot(account: String = "a", epoch: String = "e", enabled: Bool = true, deleted: String? = nil) throws -> MemorySnapshot {
        let captures = deleted.map { [["id": $0, "deleted_at": "2026-10-10T00:00:00Z"]] } ?? []
        let value: [String: Any] = ["settings": ["account_id": account, "epoch": epoch, "enabled": enabled], "captures": captures,
            "items": [["kind": "vocabulary", "status": "confirmed", "preferred": "Cursay"], ["kind": "vocabulary", "status": "suggested", "preferred": "Guess"]], "cursor": 1, "has_more": false]
        return try JSONDecoder().decode(MemorySnapshot.self, from: JSONSerialization.data(withJSONObject: value))
    }
    private func entry() -> Dictation { Dictation(rawText: "hello", finalText: "Hello", mode: .raw, language: "en", durationSeconds: 1, provider: "test", model: "test") }
    func testNoCaptureUntilAccountConsent() throws {
        var state = MemoryOutboxState(); state.enqueue(entry()); XCTAssertTrue(state.pending.isEmpty)
        state.reconcile(try snapshot()); state.enqueue(entry()); XCTAssertEqual(state.pending.count, 1)
        XCTAssertEqual(state.vocabulary, ["Cursay"])
    }
    func testAccountChangeAndForgetDiscardPendingContent() throws {
        var state = MemoryOutboxState(); state.reconcile(try snapshot()); state.enqueue(entry())
        state.reconcile(try snapshot(account: "b")); XCTAssertTrue(state.pending.isEmpty)
        state.enqueue(entry()); state.reconcile(try snapshot(account: "b", epoch: "new")); XCTAssertTrue(state.pending.isEmpty)
    }
    func testTombstonesApplyBeforeUploadAndPauseClearsPending() throws {
        var state = MemoryOutboxState(); state.reconcile(try snapshot()); let value = entry(); state.enqueue(value)
        state.reconcile(try snapshot(deleted: value.id.uuidString.lowercased())); XCTAssertTrue(state.pending.isEmpty)
        state.enqueue(entry()); state.reconcile(try snapshot(enabled: false)); XCTAssertTrue(state.pending.isEmpty)
    }
    func testLocalDeletionWinsOverQueuedCapture() throws {
        var state = MemoryOutboxState(); state.reconcile(try snapshot()); let value = entry(); state.enqueue(value)
        state.delete(value.id); state.enqueue(value); XCTAssertTrue(state.pending.isEmpty); XCTAssertEqual(state.deletions.count, 1)
    }
}

final class MemoryPollScheduleTests: XCTestCase {
    func testIdleBackoffAndActivityReset() {
        var schedule = MemoryPollSchedule()
        var now: TimeInterval = 100
        XCTAssertTrue(schedule.isDue(at: now))
        for delay: TimeInterval in [60, 120, 300, 900, 900] {
            schedule.completed(at: now, changed: false)
            XCTAssertFalse(schedule.isDue(at: now + delay - 1))
            XCTAssertTrue(schedule.isDue(at: now + delay))
            now += delay
        }
        schedule.completed(at: now, changed: true)
        XCTAssertTrue(schedule.isDue(at: now + 60))
        schedule.reset()
        XCTAssertTrue(schedule.isDue(at: now))
    }
}

private actor MockMemoryTransport: MemoryTransport {
    var pages: [Data]
    var cursors: [Int64] = []
    var fails = false
    init(pages: [Data]) { self.pages = pages }
    func memoryRequest(method: String, body: Data?, cursor: Int64) async throws -> Data {
        cursors.append(cursor)
        if fails { throw CloudClientError.invalidResponse }
        if pages.count > 1 { return pages.removeFirst() }
        return pages[0]
    }
    func setFailure(_ value: Bool) { fails = value }
}

final class MemoryTransportTests: XCTestCase {
    private func page(cursor: Int = 0, more: Bool = false) throws -> Data {
        try JSONSerialization.data(withJSONObject: [
            "settings": ["account_id": "a", "epoch": "e", "enabled": true],
            "captures": [], "items": [["kind": "vocabulary", "status": "confirmed", "preferred": "Cursay"]],
            "cursor": cursor, "has_more": more,
        ])
    }
    private func directory() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: url) }
        return url
    }
    func testCompactBootstrapDoesNotRefetchAndBackgroundSkips() async throws {
        let transport = MockMemoryTransport(pages: [try page()])
        let sync = MemorySync(client: transport, directory: try directory())
        _ = await sync.sync()
        _ = await sync.sync(background: true)
        let cursors = await transport.cursors
        XCTAssertEqual(cursors, [0])
        let words = await sync.approvedVocabulary()
        XCTAssertEqual(words, ["Cursay"])
        _ = await sync.sync() // Explicit retry/reconnect bypasses backoff.
        let forcedCursors = await transport.cursors
        XCTAssertEqual(forcedCursors, [0, 0])
    }
    func testPaginationUsesLastSuccessfulCursor() async throws {
        let transport = MockMemoryTransport(pages: [try page(cursor: 5, more: true), try page(cursor: 9)])
        let sync = MemorySync(client: transport, directory: try directory())
        _ = await sync.sync()
        let cursors = await transport.cursors
        XCTAssertEqual(cursors, [0, 5])
        _ = await sync.sync()
        let resumed = await transport.cursors
        XCTAssertEqual(resumed, [0, 5, 9])
    }
    func testBrokenPaginationFailsRatherThanLooping() async throws {
        let transport = MockMemoryTransport(pages: [try page(cursor: 5, more: true)])
        let sync = MemorySync(client: transport, directory: try directory())
        let result = await sync.sync()
        XCTAssertEqual(result, "Memory sync pending. Local dictation is available.")
        let cursors = await transport.cursors
        XCTAssertEqual(cursors, [0, 5])
    }
    func testOfflineQueueSurvivesRestart() async throws {
        let transport = MockMemoryTransport(pages: [try page()])
        let dir = try directory()
        let sync = MemorySync(client: transport, directory: dir)
        _ = await sync.sync()
        let scope = await sync.captureScope()
        await transport.setFailure(true)
        let entry = Dictation(rawText: "fixture", finalText: "Fixture", mode: .raw, language: "en", durationSeconds: 1, provider: "test", model: "test")
        _ = await sync.record(entry, expectedScope: scope)
        let state = try JSONDecoder().decode(MemoryOutboxState.self, from: Data(contentsOf: dir.appendingPathComponent("memory-outbox.json")))
        XCTAssertEqual(state.pending.count, 1)
        await transport.setFailure(false)
        let restarted = MemorySync(client: transport, directory: dir)
        _ = await restarted.sync()
        let uploaded = try JSONDecoder().decode(MemoryOutboxState.self, from: Data(contentsOf: dir.appendingPathComponent("memory-outbox.json")))
        XCTAssertTrue(uploaded.pending.isEmpty)
    }
}

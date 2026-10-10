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

import Foundation

public struct MemoryCapture: Codable, Equatable, Sendable {
    public let id: String
    public let epoch: String
    public let revision: Int
    public let original_text: String
    public let final_text: String
    public let mode: String
    public let platform: String
    public let created_at: String
    public let project_id: String?
}

public struct MemorySnapshot: Decodable, Sendable {
    public struct Settings: Decodable, Sendable { public let account_id: String; public let epoch: String; public let enabled: Bool }
    public struct Capture: Decodable, Sendable { public let id: String; public let deleted_at: String? }
    public struct Item: Decodable, Sendable { public let kind: String; public let status: String; public let preferred: String? }
    public let settings: Settings
    public let captures: [Capture]
    public let items: [Item]
    public let cursor: Int64
    public let has_more: Bool
}

// An account/epoch-bound outbox is separate from original local history.
// Historical dictations are never enrolled implicitly.
public struct MemoryOutboxState: Codable, Sendable {
    public var account: String?
    public var epoch: String?
    public var enabled = false
    public var cursor: Int64 = 0
    public var pending: [MemoryCapture] = []
    public var deletions: [String] = []
    public var vocabulary: [String] = []
    public init() {}
    public mutating func reconcile(_ snapshot: MemorySnapshot) {
        if account != snapshot.settings.account_id || epoch != snapshot.settings.epoch {
            pending = []; deletions = []; vocabulary = []; cursor = 0
        }
        account = snapshot.settings.account_id; epoch = snapshot.settings.epoch; enabled = snapshot.settings.enabled
        let deleted = Set(snapshot.captures.filter { $0.deleted_at != nil }.map(\.id))
        pending.removeAll { deleted.contains($0.id) }
        deletions.removeAll { deleted.contains($0) }
        if !enabled { pending = [] }
        vocabulary = snapshot.items.filter { $0.kind == "vocabulary" && $0.status == "confirmed" }.compactMap(\.preferred).filter { $0.count <= 100 }
        cursor = snapshot.cursor
    }
    public mutating func enqueue(_ dictation: Dictation) {
        guard enabled, let epoch else { return }
        let id = dictation.id.uuidString.lowercased()
        guard !deletions.contains(id), !pending.contains(where: { $0.id == id }) else { return }
        pending.append(MemoryCapture(id: id, epoch: epoch, revision: 1, original_text: dictation.rawText, final_text: dictation.finalText,
            mode: dictation.mode.rawValue, platform: "macos", created_at: ISO8601DateFormatter().string(from: dictation.createdAt), project_id: nil))
    }
    public mutating func delete(_ id: UUID) {
        let value = id.uuidString.lowercased(); pending.removeAll { $0.id == value }
        if account != nil && !deletions.contains(value) { deletions.append(value) }
    }
}

// Monotonic uptime avoids wall-clock changes suppressing background sync.
public struct MemoryPollSchedule: Sendable {
    private var step = 0
    private var due: TimeInterval = 0
    public init() {}
    public func isDue(at now: TimeInterval) -> Bool { now >= due }
    public mutating func reset() { step = 0; due = 0 }
    public mutating func completed(at now: TimeInterval, changed: Bool) {
        if changed { step = 0 }
        let delays: [TimeInterval] = [60, 120, 300, 900]
        due = now + delays[step]
        step = min(step + 1, delays.count - 1)
    }
}

public protocol MemoryTransport: Sendable {
    func memoryRequest(method: String, body: Data?, cursor: Int64) async throws -> Data
}
extension CloudClient: MemoryTransport {}

public actor MemorySync {
    private let client: any MemoryTransport
    private let fileURL: URL
    private var state: MemoryOutboxState
    private var syncing = false
    private var generation = 0
    private var schedule = MemoryPollSchedule()
    private var rerun = false
    private var lastStatus = "Memory sync pending"
    public init(client: any MemoryTransport, directory: URL) {
        self.client = client; fileURL = directory.appendingPathComponent("memory-outbox.json")
        state = (try? JSONDecoder().decode(MemoryOutboxState.self, from: Data(contentsOf: fileURL))) ?? MemoryOutboxState()
    }
    public func captureScope() -> String? {
        guard state.enabled, let account=state.account, let epoch=state.epoch else { return nil }
        return "\(account):\(epoch)"
    }
    public func approvedVocabulary() -> [String] { state.vocabulary }
    private func persist() throws {
        try FileManager.default.createDirectory(at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try JSONEncoder().encode(state).write(to: fileURL, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: fileURL.path)
    }
    public func reset() throws { generation += 1; schedule.reset(); state = MemoryOutboxState(); try persist() }
    public func record(_ entry: Dictation, expectedScope: String?) async -> String {
        guard let expectedScope, expectedScope == captureScope() else { return "Capture kept locally: Memory consent or account changed." }
        state.enqueue(entry)
        do { try persist() } catch { return "Memory queue could not be saved. Dictation was delivered." }
        return await sync()
    }
    public func delete(_ id: UUID) async -> String {
        state.delete(id)
        do { try persist() } catch { return "Memory deletion is pending; queue could not be saved." }
        return await sync()
    }
    public func sync(background: Bool = false) async -> String {
        if background && !schedule.isDue(at: ProcessInfo.processInfo.systemUptime) { return lastStatus }
        if !background { schedule.reset() }
        guard !syncing else { rerun = rerun || !background; return "Memory sync in progress" }
        let oldCursor = state.cursor, oldAccount = state.account, oldEpoch = state.epoch
        let oldEnabled = state.enabled, oldVocabulary = state.vocabulary
        var sent = false
        let turn = generation
        syncing = true
        defer {
            schedule.completed(at: ProcessInfo.processInfo.systemUptime, changed: sent || oldCursor != state.cursor || oldAccount != state.account || oldEpoch != state.epoch || oldEnabled != state.enabled || oldVocabulary != state.vocabulary)
            syncing = false
            if rerun { rerun = false; Task { _ = await self.sync() } }
        }
        do {
            // Refresh account/epoch and apply tombstones before any upload.
            var page = try JSONDecoder().decode(MemorySnapshot.self, from: await client.memoryRequest(method: "GET", body: nil, cursor: state.cursor))
            guard turn == generation else { return "Memory sync canceled" }
            let changed = state.account != page.settings.account_id || state.epoch != page.settings.epoch
            state.reconcile(page)
            if changed && oldAccount != nil {
                page = try JSONDecoder().decode(MemorySnapshot.self, from: await client.memoryRequest(method: "GET", body: nil, cursor: 0))
                guard turn == generation else { return "Memory sync canceled" }
                state.reconcile(page)
            }
            while page.has_more {
                let previousCursor = state.cursor
                page = try JSONDecoder().decode(MemorySnapshot.self, from: await client.memoryRequest(method: "GET", body: nil, cursor: state.cursor))
                guard turn == generation else { return "Memory sync canceled" }
                guard page.cursor > previousCursor else { throw CloudClientError.invalidResponse }
                state.reconcile(page)
            }
            try persist()
            for id in state.deletions {
                _ = try await client.memoryRequest(method: "POST", body: JSONSerialization.data(withJSONObject: ["action": "delete", "id": id]), cursor: 0)
                guard turn == generation else { return "Memory sync canceled" }
                sent = true
                state.deletions.removeAll { $0 == id }; try persist()
            }
            guard state.enabled else { lastStatus = "Memory off — enable it in the workspace"; return lastStatus }
            for entry in state.pending {
                guard state.pending.contains(entry), !state.deletions.contains(entry.id) else { continue }
                struct Save: Encodable { let action = "save"; let capture: MemoryCapture }
                do {
                    _ = try await client.memoryRequest(method: "POST", body: JSONEncoder().encode(Save(capture: entry)), cursor: 0)
                    guard turn == generation else { return "Memory sync canceled" }
                    sent = true
                    state.pending.removeAll { $0 == entry }; try persist()
                } catch let CloudClientError.service(_, code, _) where code == "sync_conflict" {
                    guard turn == generation else { return "Memory sync canceled" }
                    sent = true
                    state.pending.removeAll { $0 == entry }; try persist()
                }
            }
            lastStatus = "Memory synced · \(state.vocabulary.count) approved words"
            return lastStatus
        } catch let CloudClientError.service(_, code, _) where code == "memory_not_available" {
            lastStatus = "Account Memory is unavailable on the server. Local dictation is still available."
            return lastStatus
        } catch { lastStatus = "Memory sync pending. Local dictation is available."; return lastStatus }
    }
}

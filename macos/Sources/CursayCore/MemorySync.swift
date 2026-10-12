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

public actor MemorySync {
    private let client: CloudClient
    private let fileURL: URL
    private var state: MemoryOutboxState
    private var syncing = false
    private var generation = 0
    public init(client: CloudClient, directory: URL) {
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
    public func reset() throws { generation += 1; state = MemoryOutboxState(); try persist() }
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
    public func sync() async -> String {
        guard !syncing else { return "Memory sync in progress" }
        let turn = generation
        syncing = true; defer { syncing = false }
        do {
            // Refresh account/epoch and apply tombstones before any upload.
            var page = try JSONDecoder().decode(MemorySnapshot.self, from: await client.memoryRequest(cursor: state.cursor))
            guard turn == generation else { return "Memory sync canceled" }
            let changed = state.account != page.settings.account_id || state.epoch != page.settings.epoch
            state.reconcile(page)
            if changed {
                page = try JSONDecoder().decode(MemorySnapshot.self, from: await client.memoryRequest())
                guard turn == generation else { return "Memory sync canceled" }
                state.reconcile(page)
            }
            while page.has_more {
                page = try JSONDecoder().decode(MemorySnapshot.self, from: await client.memoryRequest(cursor: state.cursor))
                guard turn == generation else { return "Memory sync canceled" }
                state.reconcile(page)
            }
            try persist()
            for id in state.deletions {
                _ = try await client.memoryRequest(method: "POST", body: JSONSerialization.data(withJSONObject: ["action": "delete", "id": id]))
                guard turn == generation else { return "Memory sync canceled" }
                state.deletions.removeAll { $0 == id }; try persist()
            }
            guard state.enabled else { return "Memory off — enable it in the workspace" }
            for entry in state.pending {
                struct Save: Encodable { let action = "save"; let capture: MemoryCapture }
                do {
                    _ = try await client.memoryRequest(method: "POST", body: JSONEncoder().encode(Save(capture: entry)))
                    guard turn == generation else { return "Memory sync canceled" }
                    state.pending.removeAll { $0.id == entry.id }; try persist()
                } catch let CloudClientError.service(_, code, _) where code == "sync_conflict" {
                    guard turn == generation else { return "Memory sync canceled" }
                    state.pending.removeAll { $0.id == entry.id }; try persist()
                }
            }
            return "Memory synced · \(state.vocabulary.count) approved words"
        } catch { return "Memory sync pending. Local dictation is available." }
    }
}

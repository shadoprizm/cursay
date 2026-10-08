import Foundation
import Security

public enum CloudClientError: LocalizedError {
    case invalidResponse
    case service(statusCode: Int, code: String?, message: String)
    case notLinked
    case keychain(OSStatus)

    public var errorDescription: String? {
        switch self {
        case .invalidResponse: return "Cursay Cloud returned an invalid response."
        case let .service(_, _, message): return message
        case .notLinked: return "Link this Mac to a Cursay Pro account."
        case let .keychain(status): return "Cursay could not use Keychain (\(status)). Tokens were not stored elsewhere."
        }
    }
}

public struct DeviceAuthorization: Decodable, Sendable {
    public let deviceCode: String
    public let userCode: String
    public let verificationUri: URL
    public let verificationUriComplete: URL
    public let expiresIn: Int
    public let interval: Int
}

public struct CloudAccount: Decodable, Sendable {
    public let plan: String
    public let status: String
    public let entitlement: Bool
    public let deviceCount: Int
    public let deviceLimit: Int
    public let allowanceSeconds: Int
    public let usedSeconds: Int
    public let remainingSeconds: Int
    public let periodEndsAt: String?
}

public struct CloudTokens: Codable, Sendable {
    public let accessToken: String
    public let accessExpiresAt: Date
    public let refreshToken: String
    public let refreshExpiresAt: Date
    public let deviceId: String
}

public struct KeychainTokenStore: Sendable {
    private let service = "io.github.shadoprizm.Cursay.cloud"
    private let account = "device-tokens"

    public init() {}

    public func load() throws -> CloudTokens? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = item as? Data else { throw CloudClientError.keychain(status) }
        return try JSONDecoder().decode(CloudTokens.self, from: data)
    }

    public func save(_ tokens: CloudTokens) throws {
        let data = try JSONEncoder().encode(tokens)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var insertion = query
            attributes.forEach { insertion[$0.key] = $0.value }
            let addStatus = SecItemAdd(insertion as CFDictionary, nil)
            guard addStatus == errSecSuccess else { throw CloudClientError.keychain(addStatus) }
        } else if status != errSecSuccess {
            throw CloudClientError.keychain(status)
        }
    }

    public func clear() throws {
        let status = SecItemDelete([
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ] as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw CloudClientError.keychain(status) }
    }
}

public actor CloudClient {
    private struct TokenResponse: Decodable {
        let accessToken: String
        let expiresIn: Int
        let refreshToken: String
        let refreshExpiresIn: Int
        let deviceId: String?
    }
    private struct PolishResponse: Decodable { let text: String }
    private struct ErrorEnvelope: Decodable {
        struct Detail: Decodable { let code: String?; let message: String }
        let error: Detail
    }

    private let baseURL: URL
    private let store: KeychainTokenStore
    private let transcriptionClient = TranscriptionClient()
    private let decoder: JSONDecoder

    public init(baseURL: URL, store: KeychainTokenStore = KeychainTokenStore()) {
        self.baseURL = baseURL
        self.store = store
        decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    public func isLinked() throws -> Bool { try store.load() != nil }

    public func beginLink(deviceName: String = Host.current().localizedName ?? "Mac") async throws -> DeviceAuthorization {
        try await request("/api/v1/device/authorizations", method: "POST", body: ["device_name": deviceName, "platform": "macos"])
    }

    public func pollLink(deviceCode: String) async throws -> Bool {
        do {
            let response: TokenResponse = try await request("/api/v1/device/token", method: "POST", body: ["device_code": deviceCode])
            let now = Date()
            try store.save(CloudTokens(
                accessToken: response.accessToken,
                accessExpiresAt: now.addingTimeInterval(TimeInterval(response.expiresIn)),
                refreshToken: response.refreshToken,
                refreshExpiresAt: now.addingTimeInterval(TimeInterval(response.refreshExpiresIn)),
                deviceId: response.deviceId ?? ""
            ))
            return true
        } catch let CloudClientError.service(_, code, _) where code == "authorization_pending" {
            return false
        }
    }

    public func account() async throws -> CloudAccount {
        let tokens = try await validTokens()
        return try await authorizedRequest("/api/v1/account", tokens: tokens)
    }

    public func transcribe(
        audioURL: URL, language: String, preflight: CloudTranscriptionPreflight? = nil
    ) async throws -> TranscriptionResult {
        if let preflight {
            try await preflight.requireAccess { try await self.account() }
        } else {
            try await account().requireTranscriptionAccess()
        }
        var tokens = try await validTokens()
        let idempotencyKey = UUID().uuidString
        do {
            return try await transcriptionClient.transcribe(
                audioURL: audioURL,
                endpoint: baseURL.appendingPathComponent("api/v1/audio/transcriptions").absoluteString,
                model: "cursay-cloud",
                language: language,
                bearerToken: tokens.accessToken,
                idempotencyKey: idempotencyKey
            )
        } catch let TranscriptionError.service(statusCode, _) where statusCode == 401 {
            tokens = try await refresh(tokens)
            return try await transcriptionClient.transcribe(
                audioURL: audioURL,
                endpoint: baseURL.appendingPathComponent("api/v1/audio/transcriptions").absoluteString,
                model: "cursay-cloud",
                language: language,
                bearerToken: tokens.accessToken,
                idempotencyKey: idempotencyKey
            )
        }
    }

    public func polish(text: String, style: DictationMode, grant: String) async throws -> String {
        let tokens = try await validTokens()
        let response: PolishResponse = try await authorizedRequest(
            "/api/v1/polish", method: "POST",
            body: ["cleaned_text": text, "style": style.rawValue, "polish_grant": grant], tokens: tokens
        )
        return response.text
    }

    public func revokeAndSignOut() async throws {
        if let tokens = try store.load() {
            let _: [String: Bool]? = try? await authorizedRequest(
                "/api/v1/devices/\(tokens.deviceId)", method: "DELETE", tokens: tokens
            )
        }
        try store.clear()
    }

    private func validTokens() async throws -> CloudTokens {
        guard let tokens = try store.load() else { throw CloudClientError.notLinked }
        if tokens.accessExpiresAt <= Date().addingTimeInterval(30) { return try await refresh(tokens) }
        return tokens
    }

    private func refresh(_ current: CloudTokens) async throws -> CloudTokens {
        guard current.refreshExpiresAt > Date() else { try store.clear(); throw CloudClientError.notLinked }
        let response: TokenResponse = try await request(
            "/api/v1/device/refresh", method: "POST", body: ["refresh_token": current.refreshToken]
        )
        let now = Date()
        let tokens = CloudTokens(
            accessToken: response.accessToken,
            accessExpiresAt: now.addingTimeInterval(TimeInterval(response.expiresIn)),
            refreshToken: response.refreshToken,
            refreshExpiresAt: now.addingTimeInterval(TimeInterval(response.refreshExpiresIn)),
            deviceId: current.deviceId
        )
        try store.save(tokens)
        return tokens
    }

    private func authorizedRequest<T: Decodable>(
        _ path: String, method: String = "GET", body: [String: String]? = nil, tokens: CloudTokens
    ) async throws -> T {
        try await request(path, method: method, body: body, bearerToken: tokens.accessToken)
    }

    private func request<T: Decodable>(
        _ path: String, method: String = "GET", body: [String: String]? = nil, bearerToken: String? = nil
    ) async throws -> T {
        guard let url = URL(string: path, relativeTo: baseURL) else { throw CloudClientError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 90
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if let bearerToken { request.setValue("Bearer \(bearerToken)", forHTTPHeaderField: "Authorization") }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw CloudClientError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let detail = try? decoder.decode(ErrorEnvelope.self, from: data).error
            throw CloudClientError.service(
                statusCode: http.statusCode, code: detail?.code,
                message: detail?.message ?? "Cursay Cloud returned HTTP \(http.statusCode)."
            )
        }
        do { return try decoder.decode(T.self, from: data) } catch { throw CloudClientError.invalidResponse }
    }
}

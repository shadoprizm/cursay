import Foundation

public enum CloudAccess: Equatable, Sendable {
    case available
    case upgradeRequired
    case allowanceExhausted

    public var message: String {
        switch self {
        case .available: return "Cursay Cloud is ready."
        case .upgradeRequired: return "Upgrade to Cursay Pro to use managed cloud transcription and Cloud Smart Polish."
        case .allowanceExhausted: return "Your cloud allowance is used up. Use Local Whisper or wait for your allowance to renew."
        }
    }
}

public extension CloudAccount {
    var access: CloudAccess {
        guard entitlement, ["trial", "pro"].contains(plan), allowanceSeconds > 0 else { return .upgradeRequired }
        return remainingSeconds > 0 ? .available : .allowanceExhausted
    }

    func requireTranscriptionAccess() throws {
        switch access {
        case .available: return
        case .upgradeRequired:
            throw CloudClientError.service(statusCode: 402, code: "subscription_required", message: access.message)
        case .allowanceExhausted:
            throw CloudClientError.service(statusCode: 429, code: "quota_exhausted", message: access.message)
        }
    }
}

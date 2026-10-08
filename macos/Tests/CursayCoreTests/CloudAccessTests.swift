import CursayCore
import XCTest

final class CloudAccessTests: XCTestCase {
    private func account(plan: String, entitled: Bool, remaining: Int, allowance: Int = 90_000) throws -> CloudAccount {
        let payload: [String: Any] = [
            "plan": plan, "status": "active", "entitlement": entitled,
            "device_count": 1, "device_limit": 3, "allowance_seconds": allowance,
            "used_seconds": max(0, allowance - remaining), "remaining_seconds": remaining,
        ]
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(CloudAccount.self, from: JSONSerialization.data(withJSONObject: payload))
    }

    func testFreeAccountRequiresUpgradeEvenThoughDeviceIsLinked() throws {
        let free = try account(plan: "free", entitled: false, remaining: 0, allowance: 0)
        XCTAssertEqual(free.access, .upgradeRequired)
        XCTAssertThrowsError(try free.requireTranscriptionAccess()) { error in
            guard case CloudClientError.service(402, "subscription_required", _) = error else {
                return XCTFail("Expected an upgrade requirement")
            }
        }
    }

    func testExpiredTrialAndPaidAccountsAreDenied() throws {
        for plan in ["trial", "pro"] {
            XCTAssertEqual(try account(plan: plan, entitled: false, remaining: 60).access, .upgradeRequired)
        }
    }

    func testActiveTrialAndProAccountsAreAvailable() throws {
        for plan in ["trial", "pro"] {
            let eligible = try account(plan: plan, entitled: true, remaining: 60)
            XCTAssertEqual(eligible.access, .available)
            XCTAssertNoThrow(try eligible.requireTranscriptionAccess())
        }
    }

    func testExhaustedAllowanceDoesNotAskPaidUserToUpgrade() throws {
        let exhausted = try account(plan: "pro", entitled: true, remaining: 0)
        XCTAssertEqual(exhausted.access, .allowanceExhausted)
        XCTAssertThrowsError(try exhausted.requireTranscriptionAccess()) { error in
            guard case CloudClientError.service(429, "quota_exhausted", _) = error else {
                return XCTFail("Expected exhausted allowance")
            }
        }
    }

    func testInconsistentFreeEntitlementFailsClosed() throws {
        XCTAssertEqual(try account(plan: "free", entitled: true, remaining: 60).access, .upgradeRequired)
        XCTAssertEqual(try account(plan: "pro", entitled: true, remaining: 60, allowance: 0).access, .upgradeRequired)
    }
}

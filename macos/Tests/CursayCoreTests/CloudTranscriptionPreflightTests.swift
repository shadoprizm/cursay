import Foundation
import XCTest
@testable import CursayCore

final class CloudTranscriptionPreflightTests: XCTestCase {
    private func account(allowed: Bool = true) throws -> CloudAccount {
        let data = Data("""
        {"plan":"pro","status":"active","entitlement":\(allowed),"deviceCount":1,
         "deviceLimit":3,"allowanceSeconds":90000,"usedSeconds":0,"remainingSeconds":90000}
        """.utf8)
        return try JSONDecoder().decode(CloudAccount.self, from: data)
    }

    func testFreshCheckIsReusedWithoutAnotherRequest() async throws {
        let account = try account()
        let preflight = CloudTranscriptionPreflight { account }
        try await preflight.requireAccess {
            XCTFail("A fresh check should already be running during recording")
            throw CloudClientError.invalidResponse
        }
    }

    func testDeniedAccessIsStillRejectedBeforeUpload() async throws {
        let account = try account(allowed: false)
        let preflight = CloudTranscriptionPreflight { account }
        do {
            try await preflight.requireAccess { account }
            XCTFail("Free or expired access must not permit an upload")
        } catch let CloudClientError.service(statusCode, code, _) {
            XCTAssertEqual(statusCode, 402)
            XCTAssertEqual(code, "subscription_required")
        }
    }

    func testLongRecordingRechecksAccessAndRejectsExpiredPlan() async throws {
        let active = try account()
        let expired = try account(allowed: false)
        // The first clock read timestamps the completed check; the second simulates
        // releasing the shortcut after a long recording.
        let clock = PreflightClock()
        let preflight = CloudTranscriptionPreflight(now: { clock.next() }) { active }
        do {
            try await preflight.requireAccess { expired }
            XCTFail("A long recording must check the current plan")
        } catch let CloudClientError.service(statusCode, _, _) {
            XCTAssertEqual(statusCode, 402)
        }
    }

    func testFailedAccountCheckCannotAuthorizeAnUpload() async throws {
        let preflight = CloudTranscriptionPreflight { throw CloudClientError.notLinked }
        do {
            try await preflight.requireAccess {
                XCTFail("A failed check should propagate to the existing local fallback")
                throw CloudClientError.invalidResponse
            }
            XCTFail("A missing cloud link must not permit an upload")
        } catch CloudClientError.notLinked {}
    }
}

private final class PreflightClock: @unchecked Sendable {
    private let lock = NSLock()
    private var reads = 0

    func next() -> Date {
        lock.lock()
        defer { lock.unlock() }
        reads += 1
        return Date(timeIntervalSince1970: reads == 1 ? 100 : 130)
    }
}

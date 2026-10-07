import CursayCore
import XCTest

final class PricingTests: XCTestCase {
    func testXaiCostIsEstimatedFromDuration() {
        let entry = Dictation(
            rawText: "hello",
            finalText: "Hello.",
            mode: .professional,
            language: "en",
            durationSeconds: 360,
            provider: "xai",
            model: "grok-voice-transcribe-2.0"
        )

        let summary = TranscriptionPricing.summarize([entry])

        XCTAssertEqual(summary.usd, 0.01, accuracy: 0.000_001)
        XCTAssertEqual(summary.formattedTotal, "$0.010")
        XCTAssertTrue(summary.complete)
    }

    func testReportedCostTakesPrecedence() {
        let entry = Dictation(
            rawText: "hello",
            finalText: "Hello.",
            mode: .professional,
            language: "en",
            durationSeconds: 360,
            provider: "xai",
            model: "grok-voice-transcribe-2.0",
            costUsd: 0.025
        )

        let summary = TranscriptionPricing.summarize([entry])

        XCTAssertEqual(summary.usd, 0.025, accuracy: 0.000_001)
        XCTAssertEqual(summary.breakdown[0].detail, "Provider reported")
    }

    func testUsageTicksAreConvertedToDollars() {
        let result = TranscriptionResult(
            text: "Hello.",
            usage: .init(costInUsdTicks: 250_000_000)
        )

        XCTAssertEqual(result.reportedCostUsd ?? -1, 0.025, accuracy: 0.000_001)
    }

    func testPartiallyReportedUnknownProviderIsMarkedIncomplete() {
        let reported = Dictation(
            rawText: "one", finalText: "One.", mode: .professional, language: "en",
            durationSeconds: 30, provider: "custom", model: "unknown", costUsd: 0.02
        )
        let unknown = Dictation(
            rawText: "two", finalText: "Two.", mode: .professional, language: "en",
            durationSeconds: 30, provider: "custom", model: "unknown"
        )

        let summary = TranscriptionPricing.summarize([reported, unknown])

        XCTAssertFalse(summary.complete)
        XCTAssertEqual(summary.formattedTotal, "$0.020+")
    }
}

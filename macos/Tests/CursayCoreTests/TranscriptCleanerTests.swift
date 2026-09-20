import CursayCore
import XCTest

final class TranscriptCleanerTests: XCTestCase {
    func testProfessionalRemovesFillersAndAddsPunctuation() {
        let (text, metadata) = TranscriptCleaner.clean(
            "um, send the report to Jordan by five",
            mode: .professional,
            removeFillers: true
        )
        XCTAssertEqual(text, "Send the report to Jordan by five.")
        XCTAssertEqual(metadata.fillersRemoved.map { $0.lowercased() }, ["um"])
    }

    func testRawPreservesWords() {
        let (text, metadata) = TranscriptCleaner.clean("  uh keep this exactly  ", mode: .raw)
        XCTAssertEqual(text, "uh keep this exactly")
        XCTAssertTrue(metadata.fillersRemoved.isEmpty)
    }

    func testCodeConvertsSpokenSymbols() {
        let (text, _) = TranscriptCleaner.clean(
            "print open paren hello close paren new line",
            mode: .code,
            removeFillers: false
        )
        XCTAssertEqual(text, "print(hello)\n")
    }
}

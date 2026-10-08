import CoreGraphics
import XCTest
@testable import CursayMac

final class GlobalHotKeyTests: XCTestCase {
    func testPressRepeatAndRelease() {
        var state = OptionSpaceState()
        XCTAssertEqual(state.handle(type: .keyDown, keyCode: 49, flags: .maskAlternate).transition, .pressed)
        let repeated = state.handle(type: .keyDown, keyCode: 49, flags: .maskAlternate)
        XCTAssertTrue(repeated.consumed)
        XCTAssertNil(repeated.transition)
        let released = state.handle(type: .keyUp, keyCode: 49, flags: .maskAlternate)
        XCTAssertTrue(released.consumed)
        XCTAssertEqual(released.transition, .released)
        XCTAssertFalse(state.isHeld)
    }

    func testOptionReleasedBeforeSpaceStopsExactlyOnce() {
        var state = OptionSpaceState()
        _ = state.handle(type: .keyDown, keyCode: 49, flags: .maskAlternate)
        XCTAssertEqual(state.handle(type: .flagsChanged, keyCode: 58, flags: []).transition, .released)
        XCTAssertNil(state.handle(type: .keyDown, keyCode: 49, flags: []).transition)
        let keyUp = state.handle(type: .keyUp, keyCode: 49, flags: [])
        XCTAssertTrue(keyUp.consumed)
        XCTAssertNil(keyUp.transition)
        XCTAssertEqual(state.handle(type: .keyDown, keyCode: 49, flags: .maskAlternate).transition, .pressed)
    }

    func testUnrelatedKeysAndShortcutsAreNotConsumed() {
        for flags: CGEventFlags in [[], .maskControl, [.maskAlternate, .maskCommand], [.maskAlternate, .maskShift]] {
            var state = OptionSpaceState()
            XCTAssertFalse(state.handle(type: .keyDown, keyCode: 49, flags: flags).consumed)
            XCTAssertFalse(state.isHeld)
        }
        var state = OptionSpaceState()
        XCTAssertFalse(state.handle(type: .keyDown, keyCode: 0, flags: .maskAlternate).consumed)
    }

    func testCapsLockAndFnDoNotPreventShortcut() {
        var state = OptionSpaceState()
        XCTAssertEqual(state.handle(type: .keyDown, keyCode: 49, flags: [.maskAlternate, .maskAlphaShift, .maskSecondaryFn]).transition, .pressed)
    }

    func testSleepOrDisabledTapReleasesAndCanStartAgain() {
        var state = OptionSpaceState()
        _ = state.handle(type: .keyDown, keyCode: 49, flags: .maskAlternate)
        XCTAssertEqual(state.reset(), .released)
        XCTAssertNil(state.reset())
        XCTAssertFalse(state.handle(type: .keyUp, keyCode: 49, flags: []).consumed)
        XCTAssertEqual(state.handle(type: .keyDown, keyCode: 49, flags: .maskAlternate).transition, .pressed)
    }
}

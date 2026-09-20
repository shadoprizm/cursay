import AppKit
import ApplicationServices
import Foundation

@MainActor
final class PasteController {
    var isAccessibilityTrusted: Bool {
        AXIsProcessTrusted()
    }

    @discardableResult
    func requestAccessibilityAccess() -> Bool {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        return AXIsProcessTrustedWithOptions(options)
    }

    @discardableResult
    func copy(_ text: String) -> Bool {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        return pasteboard.setString(text, forType: .string)
    }

    func paste(_ text: String, into application: NSRunningApplication?) async -> Bool {
        guard copy(text) else { return false }
        guard let application else { return false }
        guard isAccessibilityTrusted else {
            requestAccessibilityAccess()
            return false
        }

        application.activate(options: [.activateIgnoringOtherApps])
        try? await Task.sleep(nanoseconds: 140_000_000)
        guard let keyDown = CGEvent(keyboardEventSource: nil, virtualKey: 9, keyDown: true),
              let keyUp = CGEvent(keyboardEventSource: nil, virtualKey: 9, keyDown: false) else {
            return false
        }
        keyDown.flags = .maskCommand
        keyUp.flags = .maskCommand
        keyDown.post(tap: .cghidEventTap)
        keyUp.post(tap: .cghidEventTap)
        return true
    }
}

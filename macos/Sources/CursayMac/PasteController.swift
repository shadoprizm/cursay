import AppKit
import ApplicationServices
import Carbon.HIToolbox
import Foundation
import os

struct PasteTarget {
    let application: NSRunningApplication
    let focusedElement: AXUIElement?
}

@MainActor
final class PasteController {
    private let logger = Logger(subsystem: "io.github.shadoprizm.Cursay", category: "paste")
    private var lastExternalTarget: PasteTarget?
    private var activationObserver: NSObjectProtocol?
    private var deactivationObserver: NSObjectProtocol?

    init() {
        rememberIfExternal(NSWorkspace.shared.frontmostApplication)

        let notifications = NSWorkspace.shared.notificationCenter
        activationObserver = notifications.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            let application = notification.userInfo?[NSWorkspace.applicationUserInfoKey]
                as? NSRunningApplication
            Task { @MainActor [weak self] in
                self?.rememberIfExternal(application)
            }
        }
        deactivationObserver = notifications.addObserver(
            forName: NSWorkspace.didDeactivateApplicationNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            let application = notification.userInfo?[NSWorkspace.applicationUserInfoKey]
                as? NSRunningApplication
            Task { @MainActor [weak self] in
                // Capture the control that was focused immediately before the
                // user clicked Cursay's window or menu-bar recording control.
                self?.rememberIfExternal(application)
            }
        }
    }

    deinit {
        let notifications = NSWorkspace.shared.notificationCenter
        if let activationObserver {
            notifications.removeObserver(activationObserver)
        }
        if let deactivationObserver {
            notifications.removeObserver(deactivationObserver)
        }
    }

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
        guard pasteboard.setString(text, forType: .string) else { return false }
        return pasteboard.string(forType: .string) == text
    }

    func captureTarget() -> PasteTarget? {
        if let application = NSWorkspace.shared.frontmostApplication,
           isExternal(application) {
            let target = makeTarget(for: application)
            lastExternalTarget = target
            logger.notice("Captured active paste target bundle=\(application.bundleIdentifier ?? "unknown", privacy: .public) focusedElement=\(target.focusedElement != nil, privacy: .public)")
            return target
        }
        let target = lastExternalTarget.flatMap { $0.application.isTerminated ? nil : $0 }
        logger.notice("Using remembered paste target bundle=\(target?.application.bundleIdentifier ?? "none", privacy: .public) focusedElement=\(target?.focusedElement != nil, privacy: .public)")
        return target
    }

    private func rememberIfExternal(_ application: NSRunningApplication?) {
        guard let application, isExternal(application) else { return }
        lastExternalTarget = makeTarget(for: application)
    }

    private func isExternal(_ application: NSRunningApplication) -> Bool {
        application.bundleIdentifier != Bundle.main.bundleIdentifier
            && !application.isTerminated
    }

    private func makeTarget(for application: NSRunningApplication) -> PasteTarget {
        PasteTarget(
            application: application,
            focusedElement: focusedElement(in: application)
        )
    }

    func paste(_ text: String, into target: PasteTarget?) async -> Bool {
        guard copy(text) else {
            logger.error("Paste cancelled because clipboard verification failed")
            return false
        }
        guard let target, !target.application.isTerminated else {
            logger.error("Paste cancelled because no live target application was captured")
            return false
        }
        guard isAccessibilityTrusted else {
            logger.error("Paste cancelled because Accessibility permission is not active")
            requestAccessibilityAccess()
            return false
        }

        let bundleIdentifier = target.application.bundleIdentifier ?? "unknown"
        guard await activate(target.application) else {
            logger.error("Paste target activation failed bundle=\(bundleIdentifier, privacy: .public)")
            return false
        }
        logger.notice("Paste target activated bundle=\(bundleIdentifier, privacy: .public)")

        if let capturedElement = target.focusedElement {
            let focusResult = AXUIElementSetAttributeValue(
                capturedElement,
                kAXFocusedAttribute as CFString,
                kCFBooleanTrue
            )
            logger.notice("Restored captured text control focus result=\(focusResult.rawValue, privacy: .public) role=\(self.role(of: capturedElement), privacy: .public)")
            try? await Task.sleep(nanoseconds: 75_000_000)
        } else if let currentElement = focusedElement(in: target.application) {
            logger.notice("Using current focused control role=\(self.role(of: currentElement), privacy: .public)")
        } else {
            logger.warning("Target app exposes no focused Accessibility control; sending Command+V to the app")
        }

        let posted = await postCommandV()
        logger.notice("Command+V event sequence posted=\(posted, privacy: .public)")
        return posted
    }

    private func activate(_ application: NSRunningApplication) async -> Bool {
        if !application.isActive, !application.activate(options: []) {
            return false
        }

        // Activation is a request on modern macOS, not a synchronous state
        // change. Wait for the requested application to actually become the
        // frontmost app instead of relying on a fixed delay.
        for _ in 0..<40 {
            let frontmostPID = NSWorkspace.shared.frontmostApplication?.processIdentifier
            if application.isActive && frontmostPID == application.processIdentifier {
                return true
            }
            try? await Task.sleep(nanoseconds: 25_000_000)
        }
        return false
    }

    private func focusedElement(in application: NSRunningApplication) -> AXUIElement? {
        let applicationElement = AXUIElementCreateApplication(application.processIdentifier)
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            applicationElement,
            kAXFocusedUIElementAttribute as CFString,
            &value
        ) == .success,
        let value,
        CFGetTypeID(value) == AXUIElementGetTypeID() else {
            return nil
        }
        return unsafeBitCast(value, to: AXUIElement.self)
    }

    private func role(of element: AXUIElement) -> String {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            element,
            kAXRoleAttribute as CFString,
            &value
        ) == .success else {
            return "unknown"
        }
        return value as? String ?? "unknown"
    }

    private func postCommandV() async -> Bool {
        let source = CGEventSource(stateID: .hidSystemState)
        guard let commandDown = CGEvent(
            keyboardEventSource: source,
            virtualKey: CGKeyCode(kVK_Command),
            keyDown: true
        ),
        let keyDown = CGEvent(
            keyboardEventSource: source,
            virtualKey: CGKeyCode(kVK_ANSI_V),
            keyDown: true
        ),
        let keyUp = CGEvent(
            keyboardEventSource: source,
            virtualKey: CGKeyCode(kVK_ANSI_V),
            keyDown: false
        ),
        let commandUp = CGEvent(
            keyboardEventSource: source,
            virtualKey: CGKeyCode(kVK_Command),
            keyDown: false
        ) else {
            return false
        }
        commandDown.flags = .maskCommand
        keyDown.flags = .maskCommand
        keyUp.flags = .maskCommand
        commandUp.flags = []
        commandDown.post(tap: .cghidEventTap)
        try? await Task.sleep(nanoseconds: 12_000_000)
        keyDown.post(tap: .cghidEventTap)
        try? await Task.sleep(nanoseconds: 12_000_000)
        keyUp.post(tap: .cghidEventTap)
        try? await Task.sleep(nanoseconds: 12_000_000)
        commandUp.post(tap: .cghidEventTap)
        return true
    }
}

import AppKit
import Carbon.HIToolbox
import Foundation
import os

// Keep Space consumed until its key-up, even if Option is released first.
// Otherwise push-to-talk can stay recording or insert a space into the target.
struct OptionSpaceState {
    enum Transition { case pressed, released }
    private(set) var isHeld = false
    private var consumesSpace = false

    mutating func handle(
        type: CGEventType, keyCode: Int64, flags: CGEventFlags
    ) -> (consumed: Bool, transition: Transition?) {
        let modifiers = flags.intersection([.maskAlternate, .maskControl, .maskCommand, .maskShift])
        if type == .flagsChanged {
            if isHeld && modifiers != .maskAlternate {
                isHeld = false
                return (false, .released)
            }
            return (false, nil)
        }
        guard keyCode == Int64(kVK_Space) else { return (false, nil) }
        if type == .keyDown {
            if consumesSpace { return (true, nil) }
            guard modifiers == .maskAlternate else { return (false, nil) }
            isHeld = true
            consumesSpace = true
            return (true, .pressed)
        }
        if type == .keyUp && consumesSpace {
            let wasHeld = isHeld
            isHeld = false
            consumesSpace = false
            return (true, wasHeld ? .released : nil)
        }
        return (false, nil)
    }

    mutating func reset() -> Transition? {
        let wasHeld = isHeld
        isHeld = false
        consumesSpace = false
        return wasHeld ? .released : nil
    }
}

private func cursayOptionSpaceHandler(
    _ proxy: CGEventTapProxy, _ type: CGEventType, _ event: CGEvent,
    _ userData: UnsafeMutableRawPointer?
) -> Unmanaged<CGEvent>? {
    guard let userData else { return Unmanaged.passUnretained(event) }
    let manager = Unmanaged<GlobalHotKey>.fromOpaque(userData).takeUnretainedValue()
    return manager.handleKeyboardEvent(type: type, event: event)
        ? nil : Unmanaged.passUnretained(event)
}

private func cursayHotKeyHandler(
    _ nextHandler: EventHandlerCallRef?,
    _ event: EventRef?,
    _ userData: UnsafeMutableRawPointer?
) -> OSStatus {
    guard let event, let userData else { return noErr }
    var hotKeyID = EventHotKeyID()
    guard GetEventParameter(event, EventParamName(kEventParamDirectObject),
        EventParamType(typeEventHotKeyID), nil, MemoryLayout<EventHotKeyID>.size,
        nil, &hotKeyID) == noErr, hotKeyID.signature == 0x43525359 else {
        return OSStatus(eventNotHandledErr)
    }
    let manager = Unmanaged<GlobalHotKey>.fromOpaque(userData).takeUnretainedValue()
    let kind = GetEventKind(event)
    DispatchQueue.main.async {
        if kind == UInt32(kEventHotKeyPressed) {
            manager.handlePressed()
        } else if kind == UInt32(kEventHotKeyReleased) {
            manager.handleReleased()
        }
    }
    return noErr
}

final class GlobalHotKey {
    private let logger = Logger(subsystem: "io.github.shadoprizm.Cursay", category: "shortcut")
    private var hotKeyRef: EventHotKeyRef?
    private var handlerRef: EventHandlerRef?
    private var eventTap: CFMachPort?
    private var eventSource: CFRunLoopSource?
    private var localMonitor: Any?
    private var workspaceObservers: [NSObjectProtocol] = []
    private var optionSpace = OptionSpaceState()
    private(set) var isRegistered = false
    var onPressed: (() -> Void)?
    var onReleased: (() -> Void)?

    func register(_ preferred: ShortcutChoice) throws -> ShortcutChoice {
        unregister()
        if preferred == .optionSpace {
            try registerOptionSpace()
            return preferred
        }
        var events = [
            EventTypeSpec(
                eventClass: OSType(kEventClassKeyboard),
                eventKind: UInt32(kEventHotKeyPressed)
            ),
            EventTypeSpec(
                eventClass: OSType(kEventClassKeyboard),
                eventKind: UInt32(kEventHotKeyReleased)
            ),
        ]
        let pointer = Unmanaged.passUnretained(self).toOpaque()
        let handlerStatus = InstallEventHandler(
            GetApplicationEventTarget(),
            cursayHotKeyHandler,
            events.count,
            &events,
            pointer,
            &handlerRef
        )
        guard handlerStatus == noErr else {
            throw NSError(
                domain: NSOSStatusErrorDomain,
                code: Int(handlerStatus),
                userInfo: [NSLocalizedDescriptionKey: "Cursay could not install the global shortcut handler."]
            )
        }

        var candidates = [preferred]
        if preferred == .controlSpace {
            candidates.append(.controlOptionSpace)
        }
        var lastStatus = OSStatus(eventHotKeyExistsErr)
        for (index, candidate) in candidates.enumerated() {
            var candidateRef: EventHotKeyRef?
            let hotKeyID = EventHotKeyID(signature: fourCharacterCode("CRSY"), id: UInt32(index + 1))
            lastStatus = RegisterEventHotKey(
                UInt32(kVK_Space),
                modifiers(for: candidate),
                hotKeyID,
                GetApplicationEventTarget(),
                0,
                &candidateRef
            )
            if lastStatus == noErr {
                hotKeyRef = candidateRef
                isRegistered = true
                return candidate
            }
        }
        unregister()
        throw NSError(
            domain: NSOSStatusErrorDomain,
            code: Int(lastStatus),
            userInfo: [NSLocalizedDescriptionKey: "Cursay could not reserve a global push-to-talk shortcut."]
        )
    }

    func unregister() {
        if let transition = optionSpace.reset() { deliver(transition) }
        if let localMonitor { NSEvent.removeMonitor(localMonitor) }
        localMonitor = nil
        for observer in workspaceObservers {
            NSWorkspace.shared.notificationCenter.removeObserver(observer)
        }
        workspaceObservers.removeAll()
        if let eventTap {
            CGEvent.tapEnable(tap: eventTap, enable: false)
            CFMachPortInvalidate(eventTap)
        }
        if let eventSource { CFRunLoopRemoveSource(CFRunLoopGetMain(), eventSource, .commonModes) }
        eventSource = nil
        eventTap = nil
        if let hotKeyRef {
            UnregisterEventHotKey(hotKeyRef)
        }
        if let handlerRef {
            RemoveEventHandler(handlerRef)
        }
        hotKeyRef = nil
        handlerRef = nil
        isRegistered = false
    }

    private func registerOptionSpace() throws {
        let mask = [CGEventType.keyDown, .keyUp, .flagsChanged]
            .reduce(CGEventMask(0)) { $0 | (CGEventMask(1) << $1.rawValue) }
        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap, place: .headInsertEventTap, options: .defaultTap,
            eventsOfInterest: mask, callback: cursayOptionSpaceHandler,
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else {
            throw NSError(domain: "Cursay.Shortcut", code: 1, userInfo: [
                NSLocalizedDescriptionKey: "Option + Space needs Cursay enabled in System Settings → Privacy & Security → Accessibility. You can also choose Ctrl + Option + Space."
            ])
        }
        guard let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0) else {
            CFMachPortInvalidate(tap)
            throw NSError(domain: "Cursay.Shortcut", code: 2, userInfo: [
                NSLocalizedDescriptionKey: "Cursay could not start the Option + Space handler."
            ])
        }
        eventTap = tap
        eventSource = source
        CFRunLoopAddSource(CFRunLoopGetMain(), source, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)

        // App-directed events do not pass through the session tap. Handle the
        // same shortcut when Cursay itself receives those events, too.
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .keyUp, .flagsChanged]) { [weak self] event in
            guard let self, let cgEvent = event.cgEvent else { return event }
            return self.handleKeyboardEvent(type: cgEvent.type, event: cgEvent) ? nil : event
        }
        let center = NSWorkspace.shared.notificationCenter
        workspaceObservers = [
            center.addObserver(forName: NSWorkspace.willSleepNotification, object: nil, queue: .main) { [weak self] _ in
                guard let self else { return }
                if let transition = self.optionSpace.reset() { self.deliver(transition) }
            },
            center.addObserver(forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { [weak self] _ in
                guard let tap = self?.eventTap else { return }
                CGEvent.tapEnable(tap: tap, enable: true)
            },
        ]
        isRegistered = true
        logger.notice("Option + Space keyboard handler enabled")
    }

    fileprivate func handleKeyboardEvent(type: CGEventType, event: CGEvent) -> Bool {
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
            if let transition = optionSpace.reset() { deliver(transition) }
            if let eventTap { CGEvent.tapEnable(tap: eventTap, enable: true) }
            logger.notice("Option + Space keyboard handler recovered")
            return false
        }
        let result = optionSpace.handle(type: type, keyCode: event.getIntegerValueField(.keyboardEventKeycode), flags: event.flags)
        if let transition = result.transition { deliver(transition) }
        return result.consumed
    }

    private func deliver(_ transition: OptionSpaceState.Transition) {
        // Keep audio startup and transcription out of the system event callback.
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            switch transition {
            case .pressed:
                self.logger.notice("Option + Space pressed")
                self.handlePressed()
            case .released:
                self.logger.notice("Option + Space released")
                self.handleReleased()
            }
        }
    }

    fileprivate func handlePressed() {
        onPressed?()
    }

    fileprivate func handleReleased() {
        onReleased?()
    }

    deinit {
        unregister()
    }

    private func fourCharacterCode(_ value: String) -> OSType {
        value.utf8.reduce(0) { ($0 << 8) + OSType($1) }
    }

    private func modifiers(for choice: ShortcutChoice) -> UInt32 {
        switch choice {
        case .controlSpace: return UInt32(controlKey)
        case .controlOptionSpace: return UInt32(controlKey | optionKey)
        case .optionSpace: return UInt32(optionKey)
        case .commandShiftSpace: return UInt32(cmdKey | shiftKey)
        }
    }
}

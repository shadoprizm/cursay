import Carbon.HIToolbox
import Foundation

private func cursayHotKeyHandler(
    _ nextHandler: EventHandlerCallRef?,
    _ event: EventRef?,
    _ userData: UnsafeMutableRawPointer?
) -> OSStatus {
    guard let event, let userData else { return noErr }
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
    private var hotKeyRef: EventHotKeyRef?
    private var handlerRef: EventHandlerRef?
    private(set) var isRegistered = false
    var onPressed: (() -> Void)?
    var onReleased: (() -> Void)?

    func register(_ preferred: ShortcutChoice) throws -> ShortcutChoice {
        unregister()
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

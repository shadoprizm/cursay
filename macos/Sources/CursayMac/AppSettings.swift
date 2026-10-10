import Combine
import CursayCore
import Foundation

enum AppAppearance: String, CaseIterable, Identifiable {
    case system
    case light
    case dark

    var id: String { rawValue }
    var displayName: String { rawValue.capitalized }
}

enum ShortcutChoice: String, CaseIterable, Identifiable {
    case controlSpace
    case controlOptionSpace
    case optionSpace
    case commandShiftSpace

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .controlSpace: return "Ctrl + Space"
        case .controlOptionSpace: return "Ctrl + Option + Space"
        case .optionSpace: return "Option + Space"
        case .commandShiftSpace: return "Command + Shift + Space"
        }
    }
}

@MainActor
final class AppSettings: ObservableObject {
    private enum Key {
        static let mode = "mode"
        static let appearance = "appearance"
        static let language = "language"
        static let endpoint = "sttEndpoint"
        static let model = "sttModel"
        static let provider = "sttProvider"
        static let smartPolish = "smartPolish"
        static let polishEndpoint = "polishEndpoint"
        static let polishModel = "polishModel"
        static let cloudFallback = "cloudLocalFallback"
        static let shortcut = "shortcut"
        static let autoPaste = "autoPaste"
        static let removeFillers = "removeFillers"
        static let preserveRecordings = "preserveRecordings"
    }

    private let defaults: UserDefaults

    @Published var mode: DictationMode { didSet { defaults.set(mode.rawValue, forKey: Key.mode) } }
    @Published var appearance: AppAppearance { didSet { defaults.set(appearance.rawValue, forKey: Key.appearance) } }
    @Published var language: String { didSet { defaults.set(language, forKey: Key.language) } }
    @Published var endpoint: String { didSet { defaults.set(endpoint, forKey: Key.endpoint) } }
    @Published var model: String { didSet { defaults.set(model, forKey: Key.model) } }
    @Published var provider: TranscriptionProvider { didSet { defaults.set(provider.rawValue, forKey: Key.provider) } }
    @Published var smartPolish: Bool { didSet { defaults.set(smartPolish, forKey: Key.smartPolish) } }
    @Published var polishEndpoint: String { didSet { defaults.set(polishEndpoint, forKey: Key.polishEndpoint) } }
    @Published var polishModel: String { didSet { defaults.set(polishModel, forKey: Key.polishModel) } }
    @Published var cloudLocalFallback: Bool { didSet { defaults.set(cloudLocalFallback, forKey: Key.cloudFallback) } }
    @Published var shortcut: ShortcutChoice { didSet { defaults.set(shortcut.rawValue, forKey: Key.shortcut) } }
    @Published var autoPaste: Bool { didSet { defaults.set(autoPaste, forKey: Key.autoPaste) } }
    @Published var removeFillers: Bool { didSet { defaults.set(removeFillers, forKey: Key.removeFillers) } }
    @Published var preserveRecordings: Bool {
        didSet { defaults.set(preserveRecordings, forKey: Key.preserveRecordings) }
    }
    @Published var memorySync: Bool { didSet { defaults.set(memorySync, forKey: "memorySync") } }
    @Published var privateCapture: Bool { didSet { defaults.set(privateCapture, forKey: "privateCapture") } }
    @Published var excludedMemoryApps: String { didSet { defaults.set(excludedMemoryApps, forKey: "excludedMemoryApps") } }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        let savedEndpoint = defaults.string(forKey: Key.endpoint) ?? "http://127.0.0.1:8765/v1/audio/transcriptions"
        let savedModel = defaults.string(forKey: Key.model) ?? "whisper-base.en"
        mode = DictationMode(rawValue: defaults.string(forKey: Key.mode) ?? "") ?? .professional
        appearance = AppAppearance(rawValue: defaults.string(forKey: Key.appearance) ?? "") ?? .system
        language = defaults.string(forKey: Key.language) ?? "en"
        endpoint = savedEndpoint
        model = savedModel
        if let saved = defaults.string(forKey: Key.provider), let parsed = TranscriptionProvider(rawValue: saved) {
            provider = parsed
        } else {
            provider = savedEndpoint.hasPrefix("http://127.0.0.1:") && savedModel == "whisper-base.en" ? .local : .custom
        }
        smartPolish = defaults.object(forKey: Key.smartPolish) as? Bool ?? false
        polishEndpoint = defaults.string(forKey: Key.polishEndpoint) ?? "http://127.0.0.1:8082/v1/chat/completions"
        polishModel = defaults.string(forKey: Key.polishModel) ?? "local-polish-model"
        cloudLocalFallback = defaults.object(forKey: Key.cloudFallback) as? Bool ?? true
        shortcut = ShortcutChoice(rawValue: defaults.string(forKey: Key.shortcut) ?? "") ?? .controlSpace
        autoPaste = defaults.object(forKey: Key.autoPaste) as? Bool ?? true
        removeFillers = defaults.object(forKey: Key.removeFillers) as? Bool ?? true
        preserveRecordings = defaults.object(forKey: Key.preserveRecordings) as? Bool ?? false
        memorySync = defaults.bool(forKey: "memorySync")
        privateCapture = defaults.bool(forKey: "privateCapture")
        excludedMemoryApps = defaults.string(forKey: "excludedMemoryApps") ?? ""
    }
}

import Combine
import CursayCore
import Foundation

@MainActor
final class AppSettings: ObservableObject {
    private enum Key {
        static let mode = "mode"
        static let language = "language"
        static let endpoint = "sttEndpoint"
        static let model = "sttModel"
        static let autoPaste = "autoPaste"
        static let removeFillers = "removeFillers"
        static let preserveRecordings = "preserveRecordings"
    }

    private let defaults: UserDefaults

    @Published var mode: DictationMode { didSet { defaults.set(mode.rawValue, forKey: Key.mode) } }
    @Published var language: String { didSet { defaults.set(language, forKey: Key.language) } }
    @Published var endpoint: String { didSet { defaults.set(endpoint, forKey: Key.endpoint) } }
    @Published var model: String { didSet { defaults.set(model, forKey: Key.model) } }
    @Published var autoPaste: Bool { didSet { defaults.set(autoPaste, forKey: Key.autoPaste) } }
    @Published var removeFillers: Bool { didSet { defaults.set(removeFillers, forKey: Key.removeFillers) } }
    @Published var preserveRecordings: Bool {
        didSet { defaults.set(preserveRecordings, forKey: Key.preserveRecordings) }
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        mode = DictationMode(rawValue: defaults.string(forKey: Key.mode) ?? "") ?? .professional
        language = defaults.string(forKey: Key.language) ?? "en"
        endpoint = defaults.string(forKey: Key.endpoint) ?? "http://127.0.0.1:8765/v1/audio/transcriptions"
        model = defaults.string(forKey: Key.model) ?? "whisper-base.en"
        autoPaste = defaults.object(forKey: Key.autoPaste) as? Bool ?? true
        removeFillers = defaults.object(forKey: Key.removeFillers) as? Bool ?? true
        preserveRecordings = defaults.object(forKey: Key.preserveRecordings) as? Bool ?? false
    }
}

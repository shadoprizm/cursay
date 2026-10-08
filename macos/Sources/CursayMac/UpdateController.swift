import Foundation
import Sparkle

@MainActor
final class UpdateController {
    private let controller: SPUStandardUpdaterController?

    init(bundle: Bundle = .main) {
        let feed = bundle.object(forInfoDictionaryKey: "SUFeedURL") as? String
        let publicKey = bundle.object(forInfoDictionaryKey: "SUPublicEDKey") as? String
        let configured = !(feed ?? "").isEmpty && !(publicKey ?? "").isEmpty
        controller = configured
            ? SPUStandardUpdaterController(startingUpdater: true, updaterDelegate: nil, userDriverDelegate: nil)
            : nil
    }

    var canCheckForUpdates: Bool { controller?.updater.canCheckForUpdates ?? false }

    func checkForUpdates() {
        controller?.checkForUpdates(nil)
    }
}

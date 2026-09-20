import AppKit
import SwiftUI

@main
struct CursayMacApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup("Cursay", id: "main") {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 820, minHeight: 560)
        }
        .defaultSize(width: 1040, height: 700)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }

        MenuBarExtra {
            MenuBarView()
                .environmentObject(model)
        } label: {
            Image(systemName: model.phase.isRecording ? "waveform.circle.fill" : "waveform.circle")
        }
    }
}

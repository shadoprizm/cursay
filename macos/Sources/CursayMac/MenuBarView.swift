import AppKit
import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(model.phase.statusText)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)

            Button(model.phase.isRecording ? "Stop recording" : "Start recording") {
                model.toggleRecording()
            }
            .keyboardShortcut("r")
            .disabled(model.phase == .transcribing)

            if !model.latestText.isEmpty {
                Button("Copy latest dictation") {
                    model.copy(model.latestText)
                }
            }

            Divider()

            Button("Open Cursay") {
                openWindow(id: "main")
                NSApp.activate(ignoringOtherApps: true)
            }
            .keyboardShortcut("o")

            Button("Quit Cursay") {
                NSApp.terminate(nil)
            }
            .keyboardShortcut("q")
        }
        .padding(4)
        .frame(width: 250)
    }
}

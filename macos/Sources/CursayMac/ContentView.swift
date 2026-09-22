import AppKit
import CursayCore
import SwiftUI

private enum AppSection: String, CaseIterable, Identifiable {
    case dictate
    case history
    case insights
    case settings

    var id: String { rawValue }

    var title: String { rawValue.capitalized }

    var icon: String {
        switch self {
        case .dictate: return "waveform"
        case .history: return "clock.arrow.circlepath"
        case .insights: return "chart.bar.xaxis"
        case .settings: return "gearshape"
        }
    }
}

struct ContentView: View {
    @EnvironmentObject private var model: AppModel
    @State private var selection: AppSection? = .dictate

    var body: some View {
        NavigationSplitView {
            List(AppSection.allCases, selection: $selection) { section in
                Label(section.title, systemImage: section.icon)
                    .tag(section)
            }
            .navigationTitle("Cursay")
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    Label(
                        model.shortcutRegistered ? model.shortcutLabel : "Shortcut unavailable",
                        systemImage: model.shortcutRegistered ? "keyboard" : "exclamationmark.triangle"
                    )
                    .font(.caption.weight(.semibold))
                    Text("Private dictation for your Mac")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
            }
        } detail: {
            switch selection ?? .dictate {
            case .dictate:
                DashboardView(settings: model.settings)
            case .history:
                HistoryView()
            case .insights:
                InsightsView()
            case .settings:
                SettingsView(settings: model.settings)
            }
        }
        .navigationSplitViewStyle(.balanced)
        .tint(Color(red: 0.21, green: 0.72, blue: 0.57))
    }
}

private struct DashboardView: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject var settings: AppSettings

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                hero
                latestResult
                privacyCard
            }
            .padding(30)
            .frame(maxWidth: 920)
            .frame(maxWidth: .infinity)
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .navigationTitle("Dictate")
    }

    private var hero: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Speak naturally. Get clean text.")
                        .font(.system(size: 29, weight: .bold, design: .rounded))
                    Text("Hold \(model.shortcutLabel) anywhere, speak, then release to transcribe and paste.")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: model.phase.isRecording ? "waveform.circle.fill" : "waveform.circle")
                    .font(.system(size: 44))
                    .foregroundStyle(model.phase.isRecording ? .red : .mint)
            }

            HStack(spacing: 14) {
                Button {
                    model.toggleRecording()
                } label: {
                    Label(
                        model.phase.isRecording ? "Stop recording" : "Start recording",
                        systemImage: model.phase.isRecording ? "stop.fill" : "mic.fill"
                    )
                    .font(.headline)
                    .frame(minWidth: 170)
                    .padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
                .tint(model.phase.isRecording ? .red : .mint)
                .disabled(model.phase == .transcribing)

                Picker("Writing style", selection: $settings.mode) {
                    ForEach(DictationMode.allCases) { mode in
                        Text(mode.displayName).tag(mode)
                    }
                }
                .pickerStyle(.menu)
                .frame(width: 190)
            }

            Label(model.phase.statusText, systemImage: statusIcon)
                .font(.callout.weight(.semibold))
                .foregroundStyle(statusColor)
                .padding(.horizontal, 12)
                .padding(.vertical, 7)
                .background(statusColor.opacity(0.12), in: Capsule())
        }
        .padding(26)
        .background(
            LinearGradient(
                colors: [Color.mint.opacity(0.16), Color.blue.opacity(0.08)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 22, style: .continuous)
        )
        .overlay {
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Color.mint.opacity(0.22))
        }
    }

    private var latestResult: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Latest dictation")
                        .font(.title3.weight(.semibold))
                    Text("Your final text is always copied to the clipboard.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Copy") {
                    model.copy(model.latestText)
                }
                .disabled(model.latestText.isEmpty)
            }
            Text(model.latestText.isEmpty ? "Your next dictation will appear here." : model.latestText)
                .textSelection(.enabled)
                .foregroundStyle(model.latestText.isEmpty ? .secondary : .primary)
                .frame(maxWidth: .infinity, minHeight: 90, alignment: .topLeading)
                .padding(14)
                .background(Color(nsColor: .textBackgroundColor).opacity(0.7), in: RoundedRectangle(cornerRadius: 12))
        }
        .cursayCard()
    }

    private var privacyCard: some View {
        HStack(spacing: 14) {
            Image(systemName: "lock.shield.fill")
                .font(.title)
                .foregroundStyle(.mint)
            VStack(alignment: .leading, spacing: 3) {
                Text("Designed for privacy")
                    .font(.headline)
                Text("History stays in ~/Library/Application Support/Cursay. Audio is deleted unless you choose to keep it.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
        .cursayCard()
    }

    private var statusIcon: String {
        switch model.phase {
        case .ready: return "checkmark.circle.fill"
        case .recording: return "record.circle.fill"
        case .transcribing: return "ellipsis.circle.fill"
        case .complete: return "checkmark.circle.fill"
        case .failed: return "exclamationmark.triangle.fill"
        }
    }

    private var statusColor: Color {
        switch model.phase {
        case .recording, .failed: return .red
        case .transcribing: return .orange
        default: return .mint
        }
    }
}

private struct HistoryView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        Group {
            if model.filteredHistory.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "waveform")
                        .font(.system(size: 38))
                        .foregroundStyle(.secondary)
                    Text(model.searchQuery.isEmpty ? "No dictations yet" : "No matching dictations")
                        .font(.title2.weight(.semibold))
                    Text(model.searchQuery.isEmpty ? "Your private history will appear here." : "Try a different search.")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(model.filteredHistory) { item in
                    VStack(alignment: .leading, spacing: 7) {
                        Text(item.finalText)
                            .textSelection(.enabled)
                            .lineLimit(4)
                        HStack {
                            Text(item.createdAt, style: .date)
                            Text(item.createdAt, style: .time)
                            Text("•")
                            Text(item.mode.displayName)
                            Text("•")
                            Text("\(item.wordCount) words")
                        }
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 6)
                    .contextMenu {
                        Button("Copy") { model.copy(item.finalText) }
                        Divider()
                        Button("Delete", role: .destructive) { model.delete(item) }
                    }
                }
            }
        }
        .searchable(text: $model.searchQuery, prompt: "Search your dictations")
        .navigationTitle("History")
        .toolbar {
            if !model.history.isEmpty {
                Button("Clear History", role: .destructive) {
                    model.clearHistory()
                }
            }
        }
    }
}

private struct InsightsView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack(spacing: 14) {
                    metric("Dictations", value: "\(model.stats.dictations)", icon: "waveform")
                    metric("Words", value: "\(model.stats.words)", icon: "text.word.spacing")
                    metric("Minutes", value: String(format: "%.1f", model.stats.seconds / 60), icon: "clock")
                }

                VStack(alignment: .leading, spacing: 10) {
                    Text("Filler words removed")
                        .font(.title3.weight(.semibold))
                    if model.stats.fillers.isEmpty {
                        Text("No filler words have been removed yet.")
                            .foregroundStyle(.secondary)
                    } else {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 110), spacing: 8)], alignment: .leading, spacing: 8) {
                            ForEach(model.stats.fillers) { filler in
                                Text("\(filler.word)  \(filler.count)")
                                    .font(.callout.weight(.medium))
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 6)
                                    .background(.mint.opacity(0.12), in: Capsule())
                            }
                        }
                    }
                }
                .cursayCard()
            }
            .padding(30)
            .frame(maxWidth: 920)
            .frame(maxWidth: .infinity, alignment: .top)
        }
        .navigationTitle("Insights")
    }

    private func metric(_ title: String, value: String, icon: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon)
                .foregroundStyle(.mint)
            Text(value)
                .font(.system(size: 30, weight: .bold, design: .rounded))
            Text(title)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .cursayCard()
    }
}

private struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject var settings: AppSettings

    var body: some View {
        Form {
            Section("Dictation") {
                Picker("Writing style", selection: $settings.mode) {
                    ForEach(DictationMode.allCases) { mode in
                        Text(mode.displayName).tag(mode)
                    }
                }
                TextField("Language", text: $settings.language)
                    .frame(maxWidth: 180)
                Toggle("Remove filler words", isOn: $settings.removeFillers)
                Toggle("Paste automatically", isOn: $settings.autoPaste)
                Toggle("Keep audio recordings", isOn: $settings.preserveRecordings)
            }

            Section("Transcription service") {
                TextField("Endpoint", text: $settings.endpoint)
                    .textFieldStyle(.roundedBorder)
                TextField("Model", text: $settings.model)
                    .textFieldStyle(.roundedBorder)
                LabeledContent("Status") {
                    HStack(spacing: 7) {
                        Circle()
                            .fill(model.backendState == .available ? .green : model.backendState == .checking ? .orange : .red)
                            .frame(width: 8, height: 8)
                        Text(model.backendState.label)
                    }
                }
                Button("Check connection") {
                    Task { await model.checkBackend() }
                }
            }

            Section("Mac integration") {
                LabeledContent("Global shortcut", value: model.shortcutRegistered ? model.shortcutLabel : "Unavailable")
                LabeledContent("Microphone", value: model.microphoneStatus)
                LabeledContent("Automatic paste", value: model.pasteController.isAccessibilityTrusted ? "Allowed" : "Needs Accessibility access")
                if !model.pasteController.isAccessibilityTrusted {
                    Button("Allow Accessibility access") {
                        model.requestAccessibilityAccess()
                    }
                }
                Toggle(
                    "Launch at login",
                    isOn: Binding(
                        get: { model.launchAtLogin },
                        set: { model.setLaunchAtLogin($0) }
                    )
                )
            }

            Section("Privacy") {
                Text("Text history is stored only on this Mac. Audio is deleted after transcription unless Keep audio recordings is enabled.")
                    .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .padding(20)
        .navigationTitle("Settings")
    }
}

private extension View {
    func cursayCard() -> some View {
        padding(18)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(Color.primary.opacity(0.07))
            }
    }
}

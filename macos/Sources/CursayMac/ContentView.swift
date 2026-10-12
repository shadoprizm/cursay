import AppKit
import Charts
import CursayCore
import SwiftUI

private enum AppSection: String, CaseIterable, Identifiable {
    case dictate
    case history
    case insights
    case memory
    case settings

    var id: String { rawValue }

    var title: String { rawValue.capitalized }

    var icon: String {
        switch self {
        case .dictate: return "waveform"
        case .history: return "clock.arrow.circlepath"
        case .insights: return "chart.bar.xaxis"
        case .memory: return "brain.head.profile"
        case .settings: return "gearshape"
        }
    }
}

struct ContentView: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject var settings: AppSettings
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
                    Text("Version \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "Development")")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    if let revision = Bundle.main.object(forInfoDictionaryKey: "CursaySourceRevision") as? String {
                        Text("Build \(revision.prefix(7))")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
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
            case .memory:
                MemoryView(settings: model.settings)
            case .settings:
                SettingsView(settings: model.settings)
            }
        }
        .navigationSplitViewStyle(.balanced)
        .tint(Color(red: 0.21, green: 0.72, blue: 0.57))
        .preferredColorScheme(preferredColorScheme)
    }

    private var preferredColorScheme: ColorScheme? {
        switch settings.appearance {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

private struct DashboardView: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject var settings: AppSettings

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                hero
                if let reason = model.lastFallbackReason {
                    Label(reason, systemImage: "arrow.triangle.2.circlepath")
                        .foregroundStyle(.orange)
                        .cursayCard()
                }
                latestResult
                privacyCard
            }
            .padding(30)
            .frame(maxWidth: 920)
            .frame(maxWidth: .infinity)
        }
        .background(Color(nsColor: .windowBackgroundColor))
        .navigationTitle("Cursay")
        .navigationSubtitle("Dictate")
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

            Toggle("Smart Polish", isOn: $settings.smartPolish)
                .toggleStyle(.switch)
            Text(settings.provider == .cloud ? (model.cloudAccess == .available ? "Cloud Smart Polish is included in Pro." : "Cloud Smart Polish requires an active Pro plan or trial.") : "Uses your configured compatible text endpoint.")
                .font(.caption)
                .foregroundStyle(.secondary)

            if let notice = model.cloudAccessNotice {
                Label(notice, systemImage: "lock.fill")
                    .font(.callout)
                HStack {
                    if model.cloudAccess == .upgradeRequired {
                        Button("Upgrade to Pro") { model.openCloudUpgrade() }
                            .buttonStyle(.borderedProminent)
                    }
                    Button("Use Local Whisper") { model.selectProvider(.local) }
                }
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
                Text(settings.provider == .cloud
                    ? "History stays on this Mac. Audio is sent only for the request and is not stored by Cursay Cloud."
                    : "History stays in ~/Library/Application Support/Cursay. Audio is deleted unless you choose to keep it.")
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
                            Text("•")
                            Text(item.wordsPerMinute.map { String(format: "%.1f WPM", $0) } ?? "Speed unavailable")
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
        .navigationTitle("Cursay")
        .navigationSubtitle("History")
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
    @State private var speedDays = 30

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack(spacing: 14) {
                    metric("Dictations", value: "\(model.stats.dictations)", icon: "waveform")
                    metric("Words", value: "\(model.stats.words)", icon: "text.word.spacing")
                    metric("Minutes", value: String(format: "%.1f", model.stats.seconds / 60), icon: "clock")
                    metric("Est. cost", value: model.stats.cost.formattedTotal, icon: "dollarsign.circle")
                }

                speedCard

                VStack(alignment: .leading, spacing: 10) {
                    Text("Transcription cost")
                        .font(.title3.weight(.semibold))
                    if model.stats.cost.breakdown.isEmpty {
                        Text("Cost details will appear after your first dictation.")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(model.stats.cost.breakdown) { item in
                            HStack(alignment: .firstTextBaseline) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("\(item.provider) · \(item.model)")
                                    Text("\(String(format: "%.1f", item.seconds / 60)) min · \(item.detail)")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(item.costUsd.map { CostSummary.formatUSD($0) } ?? "Unavailable")
                                    .fontWeight(.semibold)
                            }
                            if let sourceURL = item.sourceURL {
                                Link("View provider pricing", destination: sourceURL)
                                    .font(.caption)
                            }
                        }
                        Text("Estimates use recorded audio duration; your provider invoice is the final authority.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .cursayCard()

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
        .navigationTitle("Cursay")
        .navigationSubtitle("Insights")
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

    private func speedLabel(_ value: Double?) -> String {
        value.map { String(format: "%.1f", $0) } ?? "—"
    }

    private var speedCard: some View {
        let summary = DictationSpeed.summarize(model.history, days: speedDays)
        let maximum = max(50, ceil((summary.daily.compactMap(\.wpm).max() ?? 0) / 50) * 50)
        return VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Dictation speed").font(.title3.weight(.semibold))
                Spacer()
                Picker("Time period", selection: $speedDays) {
                    Text("Last 14 days").tag(14)
                    Text("Last 30 days").tag(30)
                    Text("Last 90 days").tag(90)
                }
                .labelsHidden()
                .frame(width: 160)
            }
            HStack(spacing: 14) {
                metric("Period average WPM", value: speedLabel(summary.averageWPM), icon: "speedometer")
                metric("All-time WPM", value: speedLabel(summary.lifetimeWPM), icon: "chart.line.uptrend.xyaxis")
                metric("Latest session WPM", value: speedLabel(summary.latestWPM), icon: "waveform")
            }
            Chart(summary.daily) { day in
                if let wpm = day.wpm {
                    LineMark(
                        x: .value("Day", day.day), y: .value("WPM", wpm),
                        series: .value("Run", day.segment)
                    )
                    .foregroundStyle(.mint)
                    PointMark(x: .value("Day", day.day), y: .value("WPM", wpm))
                        .foregroundStyle(.mint)
                        .accessibilityLabel(day.day.formatted(date: .abbreviated, time: .omitted))
                        .accessibilityValue(String(format: "%.1f words per minute", wpm))
                }
            }
            .chartXScale(domain: summary.daily.first!.day...summary.daily.last!.day)
            .chartYScale(domain: 0...maximum)
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 3)) {
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                }
            }
            .frame(height: 190)
            .overlay {
                if summary.averageWPM == nil {
                    Text("No timed dictations in this period.").foregroundStyle(.secondary)
                }
            }
            Text("\(summary.words.formatted()) words in the last \(speedDays) days · \(summary.timedDictations) sessions with speed data")
                .foregroundStyle(.secondary)
            Text("Final words ÷ recording minutes, including pauses. Transcription and polish wait time is excluded. Sessions without words or recording time are excluded from speed averages.")
                .font(.caption)
                .foregroundStyle(.secondary)
            DisclosureGroup("Daily breakdown") {
                ForEach(summary.daily.reversed().filter { $0.dictations > 0 }) { day in
                    HStack {
                        Text(day.day, style: .date)
                        Spacer()
                        Text("\(day.words) words · \(day.dictations) dictations")
                        Text(day.wpm.map { String(format: "%.1f WPM", $0) } ?? "Speed unavailable")
                    }
                    .font(.caption)
                    .padding(.vertical, 3)
                }
            }
        }
        .cursayCard()
    }
}

private struct MemoryView: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject var settings: AppSettings

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 12) {
                    Label("Your learning workspace", systemImage: "brain.head.profile")
                        .font(.title2.weight(.semibold))
                    Text("Saved thoughts, Ask Cursay, daily and weekly reviews, projects, and approved vocabulary live in your account workspace. This Mac captures and syncs future dictations when you opt in.")
                    Link("Open learning workspace", destination: URL(string: "https://cursay.com/app")!)
                        .buttonStyle(.borderedProminent)
                    Text("The workspace shows which account features are available. Local WPM and history work without an account.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                .cursayCard()
                VStack(alignment: .leading, spacing: 12) {
                    LabeledContent("Account", value: model.cloudStatus)
                    LabeledContent("Memory sync", value: model.memoryStatus)
                    Toggle("Sync future dictations", isOn: $settings.memorySync)
                        .onChange(of: settings.memorySync) { enabled in
                            if enabled { Task { await model.syncMemory() } }
                        }
                    HStack {
                        if !model.cloudLinked {
                            Button("Link this Mac") { model.linkCloudDevice() }
                        }
                        Button("Sync now") { Task { await model.syncMemory() } }
                    }
                    Text("Requires a linked account and separate Memory consent in the workspace. Existing history is not imported. Private capture and excluded apps stay private. Manage those options in Settings.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                .cursayCard()
            }
            .padding(30)
            .frame(maxWidth: 920)
            .frame(maxWidth: .infinity, alignment: .top)
        }
        .navigationTitle("Cursay")
        .navigationSubtitle("Memory")
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
                Picker("Provider", selection: Binding(
                    get: { settings.provider },
                    set: { model.selectProvider($0) }
                )) {
                    ForEach(TranscriptionProvider.allCases) { provider in
                        Text(provider.displayName).tag(provider)
                    }
                }
                if settings.provider == .custom {
                    TextField("Endpoint", text: $settings.endpoint)
                        .textFieldStyle(.roundedBorder)
                    TextField("Model", text: $settings.model)
                        .textFieldStyle(.roundedBorder)
                }
                if settings.provider == .cloud {
                    if let notice = model.cloudAccessNotice {
                        Text(notice).foregroundStyle(.secondary)
                    }
                    if model.cloudAccess == .upgradeRequired {
                        Button("Upgrade to Pro") { model.openCloudUpgrade() }
                            .buttonStyle(.borderedProminent)
                    }
                    Toggle("Fall back to Local Whisper", isOn: $settings.cloudLocalFallback)
                    Text("Managed cloud requires an active Pro plan or trial. No overage charges.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                LabeledContent("Status") {
                    HStack(spacing: 7) {
                        Circle()
                            .fill(model.backendState == .available ? .green : model.backendState == .checking ? .orange : .red)
                            .frame(width: 8, height: 8)
                        Text(model.backendState.label)
                    }
                }
                if let detail = model.backendState.detail {
                    Text(detail)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Button("Check connection") {
                    Task { await model.checkBackend() }
                }
            }

            Section("Smart Polish") {
                Toggle("Enable Smart Polish", isOn: $settings.smartPolish)
                if settings.provider != .cloud {
                    TextField("Compatible text endpoint", text: $settings.polishEndpoint)
                        .textFieldStyle(.roundedBorder)
                    TextField("Polish model", text: $settings.polishModel)
                        .textFieldStyle(.roundedBorder)
                }
                Text("Professional, Casual, and Prompt can be polished. Code and Raw are never rewritten.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Cursay Pro") {
                LabeledContent("Account", value: model.cloudStatus)
                if !model.cloudUsage.isEmpty {
                    Text(model.cloudUsage).foregroundStyle(.secondary)
                }
                HStack {
                    if !model.cloudLinked {
                        Button("Link this Mac") { model.linkCloudDevice() }
                    }
                    Link(model.cloudAccess == .upgradeRequired ? "Upgrade to Pro" : "Manage billing", destination: URL(string: "https://cursay.com/account")!)
                    if model.cloudLinked {
                        Button("Sign out and revoke", role: .destructive) { model.signOutCloud() }
                    }
                }
            }

            Section("Mac integration") {
                Picker("Appearance", selection: $settings.appearance) {
                    ForEach(AppAppearance.allCases) { appearance in
                        Text(appearance.displayName).tag(appearance)
                    }
                }
                Picker(
                    "Global shortcut",
                    selection: Binding(
                        get: { settings.shortcut },
                        set: { model.setShortcut($0) }
                    )
                ) {
                    ForEach(ShortcutChoice.allCases) { shortcut in
                        Text(shortcut.displayName).tag(shortcut)
                    }
                }
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
                Button("Check for updates…") { model.checkForUpdates() }
                    .disabled(!model.updates.canCheckForUpdates)
            }

            Section("Privacy") {
                Toggle("Private capture (no history or Memory)", isOn: $settings.privateCapture)
                Toggle("Sync future dictations to account Memory", isOn: $settings.memorySync)
                    .onChange(of: settings.memorySync) { enabled in if enabled { Task { await model.syncMemory() } } }
                TextField("Excluded app bundle IDs (comma separated)", text: $settings.excludedMemoryApps)
                LabeledContent("Memory", value: model.memoryStatus)
                HStack {
                    Link("Open Memory workspace", destination: URL(string: "https://cursay.com/app")!)
                    Button("Sync now") { Task { await model.syncMemory() } }
                }
                Text("Memory requires separate consent in the workspace and a linked account. Only future captures sync; existing history is not imported. Excluded apps and private capture retain no history or audio. If app identity is unavailable while exclusions are configured, capture stays private.")
                    .font(.caption).foregroundStyle(.secondary)
                Text("Local history stays on this Mac unless you enable account Memory. Audio is deleted after transcription unless Keep audio recordings is enabled for a non-private capture.")
                    .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .padding(20)
        .navigationTitle("Cursay")
        .navigationSubtitle("Settings")
        .alert("Cursay Cloud requires Pro", isPresented: $model.showCloudUpgradePrompt) {
            Button("Upgrade to Pro") { model.openCloudUpgrade() }
            Button("Use Local Whisper") { model.selectProvider(.local) }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Start a Pro trial or upgrade to use managed cloud transcription and Cloud Smart Polish. Local Whisper stays free and unlimited.")
        }
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

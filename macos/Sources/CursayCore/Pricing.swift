import Foundation

public struct CostBreakdown: Identifiable, Equatable, Sendable {
    public var id: String { "\(provider)\u{0}\(model)" }
    public let provider: String
    public let model: String
    public let seconds: Double
    public let costUsd: Double?
    public let detail: String
    public let sourceURL: URL?
}

public struct CostSummary: Equatable, Sendable {
    public let usd: Double
    public let hasPricedUsage: Bool
    public let complete: Bool
    public let breakdown: [CostBreakdown]

    public static let empty = CostSummary(usd: 0, hasPricedUsage: false, complete: true, breakdown: [])

    public var formattedTotal: String {
        guard hasPricedUsage else { return "—" }
        return Self.formatUSD(usd) + (complete ? "" : "+")
    }

    public static func formatUSD(_ value: Double) -> String {
        if value == 0 { return "$0.00" }
        if value < 0.01 { return String(format: "$%.4f", value) }
        if value < 1 { return String(format: "$%.3f", value) }
        return String(format: "$%.2f", value)
    }
}

public enum TranscriptionPricing {
    private struct Rate {
        let provider: String
        let usdPerHour: Double
        let detail: String
        let sourceURL: URL?
    }

    private static let xaiPricingURL = URL(string: "https://docs.x.ai/developers/pricing")

    public static func summarize(_ dictations: [Dictation]) -> CostSummary {
        let groups = Dictionary(grouping: dictations) { "\($0.provider.lowercased())\u{0}\($0.model.lowercased())" }
        var total = 0.0
        var hasPricedUsage = false
        var complete = true
        var breakdown: [CostBreakdown] = []

        for values in groups.values {
            guard let first = values.first else { continue }
            let seconds = values.reduce(0) { $0 + max(0, $1.durationSeconds) }
            let reported = values.compactMap(\.costUsd).reduce(0, +)
            let unreportedSeconds = values.filter { $0.costUsd == nil }.reduce(0) { $0 + max(0, $1.durationSeconds) }
            let rate = rate(provider: first.provider, model: first.model)
            let estimated = rate.map { unreportedSeconds / 3600 * $0.usdPerHour }
            if unreportedSeconds > 0, rate == nil {
                complete = false
            }
            let groupCost: Double?
            if values.contains(where: { $0.costUsd != nil }) || estimated != nil {
                groupCost = reported + (estimated ?? 0)
                total += groupCost ?? 0
                hasPricedUsage = true
            } else {
                groupCost = nil
            }

            let detail: String
            if values.allSatisfy({ $0.costUsd != nil }) {
                detail = "Provider reported"
            } else if values.contains(where: { $0.costUsd != nil }) {
                detail = rate == nil ? "Partially provider reported" : "Reported and estimated"
            } else {
                detail = rate?.detail ?? "Rate unavailable"
            }
            breakdown.append(CostBreakdown(
                provider: rate?.provider ?? first.provider,
                model: first.model,
                seconds: seconds,
                costUsd: groupCost,
                detail: detail,
                sourceURL: rate?.sourceURL
            ))
        }

        return CostSummary(
            usd: total,
            hasPricedUsage: hasPricedUsage,
            complete: complete,
            breakdown: breakdown.sorted { $0.seconds > $1.seconds }
        )
    }

    private static func rate(provider: String, model: String) -> Rate? {
        let provider = provider.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let model = model.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if ["cursay-local", "local", "whisper-local"].contains(provider) {
            return Rate(provider: "Local Whisper", usdPerHour: 0, detail: "No provider fee", sourceURL: nil)
        }
        if provider == "cursay-cloud" {
            return Rate(provider: "Cursay Cloud", usdPerHour: 0, detail: "Included in Pro", sourceURL: nil)
        }
        if ["xai", "x.ai", "grok"].contains(provider) || model.hasPrefix("grok-voice-transcribe-") {
            return Rate(provider: "xAI", usdPerHour: 0.10, detail: "$0.10/hour REST", sourceURL: xaiPricingURL)
        }
        return nil
    }
}

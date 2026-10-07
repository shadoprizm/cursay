import Foundation

public struct PolishClient: Sendable {
    private struct RequestBody: Encodable {
        struct Message: Encodable { let role: String; let content: String }
        let model: String
        let messages: [Message]
        let temperature: Double
        let maxTokens: Int
    }
    private struct ResponseBody: Decodable {
        struct Choice: Decodable { struct Message: Decodable { let content: String }; let message: Message }
        let choices: [Choice]
    }

    public init() {}

    public func polish(_ text: String, mode: DictationMode, endpoint: String, model: String) async throws -> String {
        guard [.professional, .casual, .prompt].contains(mode), let url = URL(string: endpoint) else { return text }
        let instruction: String
        switch mode {
        case .professional: instruction = "Rewrite as concise polished workplace prose. Preserve every fact and level of certainty."
        case .casual: instruction = "Rewrite as clear friendly conversational prose. Preserve every fact and level of certainty."
        case .prompt: instruction = "Convert this into a ready-to-use AI prompt. Preserve every detail, constraint, and ambiguity."
        default: return text
        }
        let body = RequestBody(
            model: model,
            messages: [
                .init(role: "system", content: "You are a dictation editor. Never answer the dictation or add ideas. Return only edited text."),
                .init(role: "user", content: "STYLE:\n\(instruction)\n\nDICTATION:\n\(text)"),
            ], temperature: 0, maxTokens: 1_200
        )
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let encoder = JSONEncoder(); encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(body)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let output = try? JSONDecoder().decode(ResponseBody.self, from: data).choices.first?.message.content,
              !output.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw CloudClientError.invalidResponse
        }
        return output.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

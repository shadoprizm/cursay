import Foundation

public enum TranscriptionError: LocalizedError {
    case invalidEndpoint
    case invalidResponse
    case service(statusCode: Int, message: String)
    case noSpeech

    public var errorDescription: String? {
        switch self {
        case .invalidEndpoint:
            return "The transcription endpoint is not a valid HTTP URL."
        case .invalidResponse:
            return "The speech service returned an invalid response."
        case let .service(statusCode, message):
            return "The speech service returned HTTP \(statusCode): \(message)"
        case .noSpeech:
            return "No speech was detected. Check the microphone and try again."
        }
    }
}

public struct TranscriptionClient: Sendable {
    public init() {}

    public func transcribe(
        audioURL: URL,
        endpoint: String,
        model: String,
        language: String
    ) async throws -> TranscriptionResult {
        guard let url = URL(string: endpoint),
              let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https" else {
            throw TranscriptionError.invalidEndpoint
        }

        let boundary = "CursayBoundary\(UUID().uuidString.replacingOccurrences(of: "-", with: ""))"
        let audio = try Data(contentsOf: audioURL)
        var body = Data()
        body.appendFormField(name: "model", value: model, boundary: boundary)
        body.appendFormField(name: "response_format", value: "json", boundary: boundary)
        if !language.isEmpty, language.lowercased() != "auto" {
            body.appendFormField(name: "language", value: language, boundary: boundary)
        }
        body.appendFile(
            name: "file",
            filename: audioURL.lastPathComponent,
            mimeType: "audio/wav",
            contents: audio,
            boundary: boundary
        )
        body.append("--\(boundary)--\r\n")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 150
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        let (data, response) = try await URLSession.shared.upload(for: request, from: body)
        guard let http = response as? HTTPURLResponse else {
            throw TranscriptionError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: Data(data.prefix(500)), encoding: .utf8) ?? "Unknown error"
            throw TranscriptionError.service(statusCode: http.statusCode, message: message)
        }

        let result: TranscriptionResult
        do {
            result = try JSONDecoder().decode(TranscriptionResult.self, from: data)
        } catch {
            throw TranscriptionError.invalidResponse
        }
        guard !result.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw TranscriptionError.noSpeech
        }
        return result
    }

    public func health(endpoint: String) async -> Bool {
        guard let transcriptionURL = URL(string: endpoint) else { return false }
        let endpointString = transcriptionURL.absoluteString
        let baseString = endpointString.components(separatedBy: "/v1/").first ?? endpointString
        guard let healthURL = URL(string: baseString + "/health") else { return false }
        var request = URLRequest(url: healthURL)
        request.timeoutInterval = 3
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else { return false }
            return (200..<300).contains(http.statusCode)
        } catch {
            return false
        }
    }
}

private extension Data {
    mutating func append(_ value: String) {
        append(value.data(using: .utf8) ?? Data())
    }

    mutating func appendFormField(name: String, value: String, boundary: String) {
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
        append("\(value)\r\n")
    }

    mutating func appendFile(
        name: String,
        filename: String,
        mimeType: String,
        contents: Data,
        boundary: String
    ) {
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\n")
        append("Content-Type: \(mimeType)\r\n\r\n")
        append(contents)
        append("\r\n")
    }
}

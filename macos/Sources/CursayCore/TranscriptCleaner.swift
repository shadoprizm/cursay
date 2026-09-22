import Foundation

public enum TranscriptCleaner {
    private static let fillerPatterns = [
        #"\b(?:um+|uh+|erm+|er+|ah+)\b[,.]?\s*"#,
        #"\b(?:you know|I mean)\b[,.]?\s*"#,
    ]

    private static let codeReplacements: [(String, String)] = [
        (#"\bnew line\b"#, "\n"),
        (#"\btab\b"#, "\t"),
        (#"\bopen paren(?:thesis)?\b"#, "("),
        (#"\bclose paren(?:thesis)?\b"#, ")"),
        (#"\bopen bracket\b"#, "["),
        (#"\bclose bracket\b"#, "]"),
        (#"\bopen brace\b"#, "{"),
        (#"\bclose brace\b"#, "}"),
        (#"\bcolon\b"#, ":"),
        (#"\bsemicolon\b"#, ";"),
        (#"\bcomma\b"#, ","),
        (#"\bdot\b"#, "."),
        (#"\bequals\b"#, "="),
        (#"\bplus\b"#, "+"),
    ]

    public static func clean(
        _ text: String,
        mode: DictationMode = .professional,
        removeFillers: Bool = true
    ) -> (String, TranscriptMetadata) {
        let raw = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard mode != .raw else {
            return (raw, TranscriptMetadata(fillersRemoved: []))
        }

        var result = raw
        var removed: [String] = []
        if removeFillers {
            for pattern in fillerPatterns {
                removed.append(contentsOf: matches(pattern, in: result).map {
                    $0.trimmingCharacters(in: CharacterSet(charactersIn: " ,.\t\n"))
                }.filter { !$0.isEmpty })
                result = replacing(pattern, in: result, with: "")
            }
        }

        result = replacing(#"[ \t]+"#, in: result, with: " ")
        result = replacing(#"\s+([,.!?;:])"#, in: result, with: "$1")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        if mode == .code {
            result = cleanSpokenCode(result)
        } else if !result.isEmpty {
            result = result.prefix(1).uppercased() + String(result.dropFirst())
            let validEndings = CharacterSet(charactersIn: ".!?;:)\"'`")
            if mode == .professional,
               let finalScalar = result.unicodeScalars.last,
               !validEndings.contains(finalScalar) {
                result.append(".")
            }
        }

        return (result, TranscriptMetadata(fillersRemoved: removed))
    }

    private static func cleanSpokenCode(_ text: String) -> String {
        var result = text
        for (pattern, replacement) in codeReplacements {
            result = replacing(pattern, in: result, with: replacement)
        }
        result = replacing(#"[ ]*\n[ ]*"#, in: result, with: "\n")
        result = replacing(#"[ ]*\t[ ]*"#, in: result, with: "\t")
        result = replacing(#"\s+([,.;:)\]}])"#, in: result, with: "$1")
        result = replacing(#"[ \t]+([([{])"#, in: result, with: "$1")
        result = replacing(#"([([{])\s+"#, in: result, with: "$1")
        return result.trimmingCharacters(in: CharacterSet(charactersIn: " \t"))
    }

    private static func regex(_ pattern: String) -> NSRegularExpression? {
        try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive])
    }

    private static func matches(_ pattern: String, in value: String) -> [String] {
        guard let regex = regex(pattern) else { return [] }
        let range = NSRange(value.startIndex..<value.endIndex, in: value)
        return regex.matches(in: value, range: range).compactMap { match in
            guard let swiftRange = Range(match.range, in: value) else { return nil }
            return String(value[swiftRange])
        }
    }

    private static func replacing(_ pattern: String, in value: String, with replacement: String) -> String {
        guard let regex = regex(pattern) else { return value }
        let range = NSRange(value.startIndex..<value.endIndex, in: value)
        return regex.stringByReplacingMatches(in: value, range: range, withTemplate: replacement)
    }
}

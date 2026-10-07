using System.Text.RegularExpressions;

namespace Cursay.Windows;

public static partial class TranscriptCleaner
{
    private static readonly (Regex Pattern, string Replacement)[] CodeReplacements =
    [
        (WordPattern("new line"), "\n"),
        (WordPattern("tab"), "\t"),
        (WordPattern("open paren(?:thesis)?"), "("),
        (WordPattern("close paren(?:thesis)?"), ")"),
        (WordPattern("open bracket"), "["),
        (WordPattern("close bracket"), "]"),
        (WordPattern("open brace"), "{"),
        (WordPattern("close brace"), "}"),
        (WordPattern("colon"), ":"),
        (WordPattern("semicolon"), ";"),
        (WordPattern("comma"), ","),
        (WordPattern("dot"), "."),
        (WordPattern("equals"), "="),
        (WordPattern("plus"), "+"),
    ];

    public static (string Text, TranscriptMetadata Metadata) Clean(
        string text,
        DictationMode mode = DictationMode.Professional,
        bool removeFillers = true)
    {
        var result = text.Trim();
        if (mode == DictationMode.Raw)
        {
            return (result, new TranscriptMetadata([]));
        }

        var removed = new List<string>();
        if (removeFillers)
        {
            foreach (var pattern in new[] { FillerSoundPattern(), FillerPhrasePattern() })
            {
                removed.AddRange(pattern.Matches(result)
                    .Select(match => match.Value.Trim(' ', ',', '.', '\t', '\r', '\n'))
                    .Where(value => value.Length > 0));
                result = pattern.Replace(result, "");
            }
        }

        result = HorizontalSpacePattern().Replace(result, " ");
        result = SpaceBeforePunctuationPattern().Replace(result, "$1").Trim();
        if (mode == DictationMode.Code)
        {
            result = CleanSpokenCode(result);
        }
        else if (result.Length > 0)
        {
            result = char.ToUpper(result[0]) + result[1..];
            if (mode == DictationMode.Professional && !".!?;:)\"'`".Contains(result[^1]))
            {
                result += ".";
            }
        }

        return (result, new TranscriptMetadata(removed));
    }

    private static string CleanSpokenCode(string value)
    {
        foreach (var replacement in CodeReplacements)
        {
            value = replacement.Pattern.Replace(value, replacement.Replacement);
        }

        value = AroundNewlinePattern().Replace(value, "\n");
        value = AroundTabPattern().Replace(value, "\t");
        value = SpaceBeforeCodePunctuationPattern().Replace(value, "$1");
        value = SpaceBeforeOpeningPattern().Replace(value, "$1");
        value = SpaceAfterOpeningPattern().Replace(value, "$1");
        return value.Trim(' ', '\t');
    }

    private static Regex WordPattern(string value) => new($@"\b{value}\b", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    [GeneratedRegex(@"\b(?:um+|uh+|erm+|er+|ah+)\b[,.]?\s*", RegexOptions.IgnoreCase)]
    private static partial Regex FillerSoundPattern();
    [GeneratedRegex(@"\b(?:you know|I mean)\b[,.]?\s*", RegexOptions.IgnoreCase)]
    private static partial Regex FillerPhrasePattern();
    [GeneratedRegex(@"[ \t]+")]
    private static partial Regex HorizontalSpacePattern();
    [GeneratedRegex(@"\s+([,.!?;:])")]
    private static partial Regex SpaceBeforePunctuationPattern();
    [GeneratedRegex(@"[ ]*\n[ ]*")]
    private static partial Regex AroundNewlinePattern();
    [GeneratedRegex(@"[ ]*\t[ ]*")]
    private static partial Regex AroundTabPattern();
    [GeneratedRegex(@"\s+([,.;:)\]}])")]
    private static partial Regex SpaceBeforeCodePunctuationPattern();
    [GeneratedRegex(@"[ \t]+([([{])")]
    private static partial Regex SpaceBeforeOpeningPattern();
    [GeneratedRegex(@"([([{])\s+")]
    private static partial Regex SpaceAfterOpeningPattern();
}

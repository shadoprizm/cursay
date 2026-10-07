using System.Text.Json.Serialization;

namespace Cursay.Windows;

public enum DictationMode
{
    Professional,
    Casual,
    Code,
    Raw,
}

public sealed record TranscriptMetadata(IReadOnlyList<string> FillersRemoved);

public sealed record TranscriptionResult(
    [property: JsonPropertyName("text")] string Text,
    [property: JsonPropertyName("language")] string? Language,
    [property: JsonPropertyName("duration")] double? Duration,
    [property: JsonPropertyName("provider")] string? Provider,
    [property: JsonPropertyName("model")] string? Model);

public sealed record Dictation(
    Guid Id,
    DateTimeOffset CreatedAt,
    string RawText,
    string FinalText,
    DictationMode Mode,
    string Language,
    double DurationSeconds,
    string Provider,
    string Model,
    IReadOnlyList<string> FillersRemoved,
    string? RecordingPath)
{
    public int WordCount => FinalText.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries).Length;

    public static Dictation Create(
        string rawText,
        string finalText,
        DictationMode mode,
        string language,
        double durationSeconds,
        string provider,
        string model,
        IReadOnlyList<string> fillersRemoved,
        string? recordingPath = null) =>
        new(Guid.NewGuid(), DateTimeOffset.Now, rawText, finalText, mode, language, durationSeconds,
            provider, model, fillersRemoved, recordingPath);
}

public sealed record FillerStat(string Word, int Count);

public sealed record HistoryStats(int Dictations, int Words, double Seconds, IReadOnlyList<FillerStat> Fillers);

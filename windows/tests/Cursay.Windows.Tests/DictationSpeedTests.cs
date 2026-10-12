using System.Text.Json;

namespace Cursay.Windows.Tests;

public sealed class DictationSpeedTests
{
    [Fact]
    public void SharedNativeSpeedContract()
    {
        using var document = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "dictation_speed.json")));
        foreach (var fixture in document.RootElement.EnumerateArray())
        {
            var entries = fixture.GetProperty("rows").EnumerateArray().Select(row => new Dictation(
                Guid.NewGuid(), DateTimeOffset.Parse(row.GetProperty("created_at").GetString()!), "",
                string.Join(" ", Enumerable.Repeat("word", row.GetProperty("word_count").GetInt32())),
                DictationMode.Raw, "en", row.GetProperty("duration_seconds").GetDouble(), "local", "whisper", [], null)).ToList();
            var days = fixture.GetProperty("days").GetInt32();
            var result = DictationSpeed.Summarize(entries, days,
                DateTimeOffset.Parse(fixture.GetProperty("now").GetString()!),
                TimeZoneInfo.FindSystemTimeZoneById(fixture.GetProperty("timezone").GetString()!));
            var expected = fixture.GetProperty("expected");
            AssertRate(expected.GetProperty("wpm"), result.AverageWpm);
            AssertRate(expected.GetProperty("lifetime_wpm"), result.LifetimeWpm);
            AssertRate(expected.GetProperty("latest_wpm"), result.LatestWpm);
            Assert.Equal(expected.GetProperty("words").GetInt32(), result.Words);
            Assert.Equal(expected.GetProperty("timed_count").GetInt32(), result.TimedDictations);
            Assert.Equal(days, result.Daily.Count);
            foreach (var day in expected.GetProperty("daily").EnumerateObject())
                AssertRate(day.Value, result.Daily.Single(value => value.Day.ToString("yyyy-MM-dd") == day.Name).Wpm);
        }
    }

    [Fact]
    public void MissingOrInvalidDurationHasNoSpeed()
    {
        foreach (var seconds in new[] { 0, -1, double.PositiveInfinity, double.NaN })
            Assert.Null(DictationSpeed.Rate(100, seconds));
        Assert.Null(DictationSpeed.Rate(0, 60));
        Assert.Equal(200, DictationSpeed.Rate(100, 30));
    }

    private static void AssertRate(JsonElement expected, double? actual)
    {
        if (expected.ValueKind == JsonValueKind.Null) Assert.Null(actual);
        else { Assert.NotNull(actual); Assert.Equal(expected.GetDouble(), actual.Value, 6); }
    }
}

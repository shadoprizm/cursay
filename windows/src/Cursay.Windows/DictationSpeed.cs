namespace Cursay.Windows;

public sealed record DailyDictationSpeed(
    DateOnly Day, int Words = 0, int Dictations = 0, int TimedWords = 0,
    double Seconds = 0, int TimedDictations = 0)
{
    public double? Wpm => DictationSpeed.Rate(TimedWords, Seconds);
}

public sealed record DictationSpeedSummary(
    int Days, IReadOnlyList<DailyDictationSpeed> Daily, double? AverageWpm, double? LifetimeWpm, double? LatestWpm)
{
    public int Words => Daily.Sum(day => day.Words);
    public int TimedDictations => Daily.Sum(day => day.TimedDictations);
}

public static class DictationSpeed
{
    public static double? Rate(int words, double seconds) =>
        words > 0 && seconds > 0 && double.IsFinite(seconds) ? words * 60.0 / seconds : null;

    public static DictationSpeedSummary Summarize(
        IEnumerable<Dictation> dictations, int days = 30, DateTimeOffset? now = null, TimeZoneInfo? timeZone = null)
    {
        if (days is not (14 or 30 or 90)) throw new ArgumentOutOfRangeException(nameof(days));
        var zone = timeZone ?? TimeZoneInfo.Local;
        var today = DateOnly.FromDateTime(TimeZoneInfo.ConvertTime(now ?? DateTimeOffset.Now, zone).DateTime);
        var start = today.AddDays(-(days - 1));
        var daily = Enumerable.Range(0, days).Select(offset => new DailyDictationSpeed(start.AddDays(offset))).ToArray();
        var totalWords = 0;
        var totalSeconds = 0.0;
        Dictation? latest = null;
        foreach (var entry in dictations)
        {
            var timed = Rate(entry.WordCount, entry.DurationSeconds) is not null;
            if (timed) { totalWords += entry.WordCount; totalSeconds += entry.DurationSeconds; }
            if (latest is null || entry.CreatedAt > latest.CreatedAt) latest = entry;
            var day = DateOnly.FromDateTime(TimeZoneInfo.ConvertTime(entry.CreatedAt, zone).DateTime);
            var index = day.DayNumber - start.DayNumber;
            if (index < 0 || index >= days) continue;
            var bucket = daily[index];
            daily[index] = bucket with {
                Words = bucket.Words + entry.WordCount, Dictations = bucket.Dictations + 1,
                TimedWords = bucket.TimedWords + (timed ? entry.WordCount : 0),
                Seconds = bucket.Seconds + (timed ? entry.DurationSeconds : 0),
                TimedDictations = bucket.TimedDictations + (timed ? 1 : 0)
            };
        }
        return new DictationSpeedSummary(days, daily,
            Rate(daily.Sum(day => day.TimedWords), daily.Sum(day => day.Seconds)),
            Rate(totalWords, totalSeconds),
            latest is null ? null : Rate(latest.WordCount, latest.DurationSeconds));
    }
}

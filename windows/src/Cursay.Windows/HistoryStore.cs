using System.Text.Json;

namespace Cursay.Windows;

public sealed class HistoryStore
{
    private readonly string _path;

    public HistoryStore(string? path = null)
    {
        AppPaths.EnsureDirectories();
        _path = path ?? AppPaths.HistoryFile;
    }

    public IReadOnlyList<Dictation> Load()
    {
        if (!File.Exists(_path))
        {
            return [];
        }

        try
        {
            return (JsonSerializer.Deserialize<List<Dictation>>(File.ReadAllText(_path), JsonSupport.Options) ?? [])
                .OrderByDescending(item => item.CreatedAt)
                .ToList();
        }
        catch (JsonException)
        {
            return [];
        }
    }

    public void Save(IEnumerable<Dictation> dictations) =>
        AtomicFile.WriteAllText(_path, JsonSerializer.Serialize(dictations, JsonSupport.Options));

    public static IReadOnlyList<Dictation> Search(string query, IEnumerable<Dictation> dictations)
    {
        var needle = query.Trim();
        return string.IsNullOrEmpty(needle)
            ? dictations.ToList()
            : dictations.Where(item =>
                    item.FinalText.Contains(needle, StringComparison.CurrentCultureIgnoreCase) ||
                    item.RawText.Contains(needle, StringComparison.CurrentCultureIgnoreCase))
                .ToList();
    }

    public static HistoryStats Stats(IEnumerable<Dictation> dictations)
    {
        var items = dictations.ToList();
        var fillers = items
            .SelectMany(item => item.FillersRemoved)
            .GroupBy(word => word.ToLowerInvariant())
            .Select(group => new FillerStat(group.Key, group.Count()))
            .OrderByDescending(item => item.Count)
            .ThenBy(item => item.Word)
            .Take(10)
            .ToList();
        return new HistoryStats(items.Count, items.Sum(item => item.WordCount),
            items.Sum(item => item.DurationSeconds), fillers);
    }
}

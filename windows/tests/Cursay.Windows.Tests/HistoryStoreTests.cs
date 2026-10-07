namespace Cursay.Windows.Tests;

public sealed class HistoryStoreTests
{
    [Fact]
    public void SaveLoadSearchAndStats()
    {
        var directory = Path.Combine(Path.GetTempPath(), $"CursayTests-{Guid.NewGuid():N}");
        var path = Path.Combine(directory, "history.json");
        try
        {
            var store = new HistoryStore(path);
            var entry = new Dictation(
                Guid.NewGuid(),
                DateTimeOffset.FromUnixTimeSeconds(1_700_000_000),
                "um hello there",
                "Hello there.",
                DictationMode.Professional,
                "en",
                2.5,
                "test",
                "test-model",
                ["um"],
                null);

            store.Save([entry]);
            var loaded = store.Load();

            var saved = Assert.Single(loaded);
            Assert.Equal(entry.Id, saved.Id);
            Assert.Equal(entry.FinalText, saved.FinalText);
            Assert.Equal(entry.FillersRemoved, saved.FillersRemoved);
            Assert.Single(HistoryStore.Search("hello", loaded));
            var stats = HistoryStore.Stats(loaded);
            Assert.Equal(1, stats.Dictations);
            Assert.Equal(2, stats.Words);
            Assert.Equal(2.5, stats.Seconds);
            Assert.Equal(new FillerStat("um", 1), Assert.Single(stats.Fillers));
        }
        finally
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, true);
            }
        }
    }
}

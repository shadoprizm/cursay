namespace Cursay.Windows;

internal static class AppPaths
{
    public static readonly string DataDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Cursay");
    public static readonly string RecordingsDirectory = Path.Combine(DataDirectory, "Recordings");
    public static readonly string TemporaryDirectory = Path.Combine(Path.GetTempPath(), "Cursay");
    public static readonly string SettingsFile = Path.Combine(DataDirectory, "settings.json");
    public static readonly string HistoryFile = Path.Combine(DataDirectory, "history.json");
    public static readonly string LogFile = Path.Combine(DataDirectory, "cursay.log");

    public static void EnsureDirectories()
    {
        Directory.CreateDirectory(DataDirectory);
        Directory.CreateDirectory(RecordingsDirectory);
        Directory.CreateDirectory(TemporaryDirectory);
    }
}

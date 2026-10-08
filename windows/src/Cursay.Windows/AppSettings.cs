using System.Text.Json;
using Microsoft.Win32;

namespace Cursay.Windows;

public sealed class AppSettings
{
    public DictationMode Mode { get; set; } = DictationMode.Professional;
    public string Language { get; set; } = "en";
    public string Endpoint { get; set; } = "http://127.0.0.1:8765/v1/audio/transcriptions";
    public string Model { get; set; } = "whisper-base.en";
    public bool AutoPaste { get; set; } = true;
    public bool RemoveFillers { get; set; } = true;
    public bool PreserveRecordings { get; set; }
    public bool StartLocalBackend { get; set; } = true;
    public bool LaunchAtLogin { get; set; }

    public static AppSettings Load(string? path = null)
    {
        AppPaths.EnsureDirectories();
        path ??= AppPaths.SettingsFile;
        try
        {
            var settings = File.Exists(path)
                ? JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(path), JsonSupport.Options) ?? new AppSettings()
                : new AppSettings();
            settings.LaunchAtLogin = IsLaunchAtLoginEnabled();
            return settings;
        }
        catch (JsonException)
        {
            return new AppSettings();
        }
    }

    public void Save(string? path = null)
    {
        AppPaths.EnsureDirectories();
        path ??= AppPaths.SettingsFile;
        AtomicFile.WriteAllText(path, JsonSerializer.Serialize(this, JsonSupport.Options));
        SetLaunchAtLogin(LaunchAtLogin);
    }

    private static void SetLaunchAtLogin(bool enabled)
    {
        using var key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run");
        if (enabled)
        {
            key.SetValue("Cursay", $"\"{Application.ExecutablePath}\" --background");
        }
        else
        {
            key.DeleteValue("Cursay", false);
        }
    }

    private static bool IsLaunchAtLoginEnabled()
    {
        using var key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run");
        return key?.GetValue("Cursay") is string;
    }
}

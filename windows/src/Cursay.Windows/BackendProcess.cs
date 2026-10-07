using System.Diagnostics;

namespace Cursay.Windows;

public sealed class BackendProcess : IDisposable
{
    private Process? _process;

    public bool TryStart()
    {
        if (_process is { HasExited: false })
        {
            return true;
        }

        var executable = Path.Combine(AppContext.BaseDirectory, "backend", "cursay-stt.exe");
        if (!File.Exists(executable))
        {
            return false;
        }

        AppPaths.EnsureDirectories();
        var info = new ProcessStartInfo(executable)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
        };
        info.Environment["CURSAY_MODEL_DIR"] = Path.Combine(AppPaths.DataDirectory, "Models");
        try
        {
            _process = Process.Start(info);
            return _process is not null;
        }
        catch (Exception exception) when (exception is IOException or System.ComponentModel.Win32Exception)
        {
            return false;
        }
    }

    public void Dispose()
    {
        if (_process is { HasExited: false })
        {
            _process.Kill(true);
            _process.WaitForExit(2_000);
        }
        _process?.Dispose();
    }
}

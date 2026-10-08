using NAudio.Wave;

namespace Cursay.Windows;

public sealed class AudioRecorder : IDisposable
{
    private WaveInEvent? _input;
    private WaveFileWriter? _writer;
    private string? _path;
    private DateTimeOffset _startedAt;

    public bool IsRecording => _input is not null;

    public void Start()
    {
        if (IsRecording)
        {
            return;
        }

        AppPaths.EnsureDirectories();
        _path = Path.Combine(AppPaths.TemporaryDirectory, $"dictation-{Guid.NewGuid():N}.wav");
        _input = new WaveInEvent
        {
            DeviceNumber = 0,
            WaveFormat = new WaveFormat(16_000, 16, 1),
            BufferMilliseconds = 50,
        };
        _writer = new WaveFileWriter(_path, _input.WaveFormat);
        _input.DataAvailable += OnDataAvailable;
        _input.StartRecording();
        _startedAt = DateTimeOffset.UtcNow;
    }

    public async Task<(string Path, double Duration)> StopAsync()
    {
        var input = _input ?? throw new InvalidOperationException("There is no recording in progress.");
        var path = _path!;
        var duration = Math.Max(0, (DateTimeOffset.UtcNow - _startedAt).TotalSeconds);
        var stopped = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        void OnStopped(object? sender, StoppedEventArgs eventArgs)
        {
            if (eventArgs.Exception is not null)
            {
                stopped.TrySetException(eventArgs.Exception);
            }
            else
            {
                stopped.TrySetResult();
            }
        }

        input.RecordingStopped += OnStopped;
        input.StopRecording();
        try
        {
            await stopped.Task;
        }
        finally
        {
            input.RecordingStopped -= OnStopped;
            input.DataAvailable -= OnDataAvailable;
            _writer?.Dispose();
            input.Dispose();
            _writer = null;
            _input = null;
            _path = null;
        }

        if (!File.Exists(path) || new FileInfo(path).Length <= 44)
        {
            File.Delete(path);
            throw new InvalidOperationException("No microphone audio was captured.");
        }
        return (path, duration);
    }

    public void Cancel()
    {
        if (_input is null)
        {
            return;
        }
        var path = _path;
        _input.StopRecording();
        _writer?.Dispose();
        _input.Dispose();
        _writer = null;
        _input = null;
        _path = null;
        if (path is not null)
        {
            File.Delete(path);
        }
    }

    private void OnDataAvailable(object? sender, WaveInEventArgs eventArgs) =>
        _writer?.Write(eventArgs.Buffer, 0, eventArgs.BytesRecorded);

    public void Dispose() => Cancel();
}

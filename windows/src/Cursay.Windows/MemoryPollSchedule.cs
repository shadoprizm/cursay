namespace Cursay.Windows;

// Monotonic elapsed time, independent of system clock adjustments.
public sealed class MemoryPollSchedule
{
    private static readonly long[] Delays = [60_000, 120_000, 300_000, 900_000];
    private int _step;
    private long _due;
    public bool IsDue(long now) => now >= _due;
    public void Reset() { _step = 0; _due = 0; }
    public void Completed(long now, bool changed)
    {
        if (changed) _step = 0;
        _due = now + Delays[_step];
        _step = Math.Min(_step + 1, Delays.Length - 1);
    }
}

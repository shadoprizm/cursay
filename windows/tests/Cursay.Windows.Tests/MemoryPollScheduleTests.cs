namespace Cursay.Windows.Tests;

public sealed class MemoryPollScheduleTests
{
    [Fact]
    public void IdleBackoffIsBoundedAndActivityResets()
    {
        var schedule = new MemoryPollSchedule();
        long now = 1000;
        Assert.True(schedule.IsDue(now));
        foreach (long delay in new long[] { 60_000, 120_000, 300_000, 900_000, 900_000 })
        {
            schedule.Completed(now, false);
            Assert.False(schedule.IsDue(now + delay - 1));
            Assert.True(schedule.IsDue(now + delay));
            now += delay;
        }
        schedule.Completed(now, true);
        Assert.True(schedule.IsDue(now + 60_000));
        schedule.Reset();
        Assert.True(schedule.IsDue(now));
    }
}

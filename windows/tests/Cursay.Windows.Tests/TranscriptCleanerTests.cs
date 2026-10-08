namespace Cursay.Windows.Tests;

public sealed class TranscriptCleanerTests
{
    [Fact]
    public void ProfessionalRemovesFillersAndAddsPunctuation()
    {
        var result = TranscriptCleaner.Clean(
            "um, send the report to Jordan by five",
            DictationMode.Professional,
            removeFillers: true);

        Assert.Equal("Send the report to Jordan by five.", result.Text);
        Assert.Equal(["um"], result.Metadata.FillersRemoved.Select(value => value.ToLowerInvariant()));
    }

    [Fact]
    public void RawPreservesWords()
    {
        var result = TranscriptCleaner.Clean("  uh keep this exactly  ", DictationMode.Raw);

        Assert.Equal("uh keep this exactly", result.Text);
        Assert.Empty(result.Metadata.FillersRemoved);
    }

    [Fact]
    public void CodeConvertsSpokenSymbols()
    {
        var result = TranscriptCleaner.Clean(
            "print open paren hello close paren new line",
            DictationMode.Code,
            removeFillers: false);

        Assert.Equal("print(hello)\n", result.Text);
    }
}

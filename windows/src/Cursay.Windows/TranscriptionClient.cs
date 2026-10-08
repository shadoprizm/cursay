using System.Net.Http.Json;
using System.Text.Json;

namespace Cursay.Windows;

public sealed class TranscriptionClient : IDisposable
{
    private readonly HttpClient _client = new() { Timeout = TimeSpan.FromSeconds(180) };

    public async Task<TranscriptionResult> TranscribeAsync(
        string audioPath,
        string endpoint,
        string model,
        string language,
        CancellationToken cancellationToken = default)
    {
        if (!Uri.TryCreate(endpoint, UriKind.Absolute, out var url) ||
            (url.Scheme != Uri.UriSchemeHttp && url.Scheme != Uri.UriSchemeHttps))
        {
            throw new InvalidOperationException("The transcription endpoint is not a valid HTTP URL.");
        }

        await using var file = File.OpenRead(audioPath);
        using var body = new MultipartFormDataContent();
        body.Add(new StringContent(model), "model");
        body.Add(new StringContent("json"), "response_format");
        if (!string.IsNullOrWhiteSpace(language) && !language.Equals("auto", StringComparison.OrdinalIgnoreCase))
        {
            body.Add(new StringContent(language), "language");
        }

        var audio = new StreamContent(file);
        audio.Headers.ContentType = new("audio/wav");
        body.Add(audio, "file", Path.GetFileName(audioPath));
        using var response = await _client.PostAsync(url, body, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            var detail = (await response.Content.ReadAsStringAsync(cancellationToken)).Trim();
            if (detail.Length > 500)
            {
                detail = detail[..500];
            }
            throw new InvalidOperationException(
                $"The speech service returned HTTP {(int)response.StatusCode}: {detail}");
        }

        var result = await response.Content.ReadFromJsonAsync<TranscriptionResult>(
            JsonSupport.Options, cancellationToken);
        if (result is null)
        {
            throw new InvalidOperationException("The speech service returned an invalid response.");
        }
        if (string.IsNullOrWhiteSpace(result.Text))
        {
            throw new InvalidOperationException("No speech was detected. Check the microphone and try again.");
        }
        return result;
    }

    public async Task<bool> IsHealthyAsync(string endpoint, CancellationToken cancellationToken = default)
    {
        try
        {
            var transcriptionUrl = new Uri(endpoint);
            var marker = transcriptionUrl.AbsoluteUri.IndexOf("/v1/", StringComparison.OrdinalIgnoreCase);
            var healthUrl = new Uri((marker >= 0 ? transcriptionUrl.AbsoluteUri[..marker] :
                transcriptionUrl.GetLeftPart(UriPartial.Authority)) + "/health");
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeout.CancelAfter(TimeSpan.FromSeconds(3));
            using var response = await _client.GetAsync(healthUrl, timeout.Token);
            return response.IsSuccessStatusCode;
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException or UriFormatException)
        {
            return false;
        }
    }

    public void Dispose() => _client.Dispose();
}

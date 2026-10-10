using System.Net;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Cursay.Windows;

internal static class ProtectedFile
{
    public static T? Load<T>(string path) => !File.Exists(path) ? default : JsonSerializer.Deserialize<T>(ProtectedData.Unprotect(File.ReadAllBytes(path), null, DataProtectionScope.CurrentUser));
    public static void Save<T>(string path, T value)
    {
        var bytes = ProtectedData.Protect(JsonSerializer.SerializeToUtf8Bytes(value), null, DataProtectionScope.CurrentUser);
        var temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try { File.WriteAllBytes(temporary, bytes); File.Move(temporary, path, true); }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }
}
public sealed record CloudTokens(string AccessToken, DateTimeOffset AccessExpiresAt, string RefreshToken, DateTimeOffset RefreshExpiresAt, string DeviceId);
public sealed class CloudServiceException(int status, string? code, string message) : Exception(message)
{
    public int Status { get; } = status;
    public string? Code { get; } = code;
}
public sealed class CloudClient : IDisposable
{
    private readonly HttpClient _http = new() { BaseAddress = new Uri("https://cursay.com"), Timeout = TimeSpan.FromSeconds(60) };
    private readonly SemaphoreSlim _tokenLock = new(1);
    private long _generation;
    private readonly string _path = Path.Combine(AppPaths.DataDirectory, "cloud-tokens.dpapi");
    private async Task<JsonObject> RequestAsync(string path, HttpMethod method, object? body = null, string? token = null)
    {
        using var request = new HttpRequestMessage(method, path);
        if (body is not null) request.Content = JsonContent.Create(body);
        if (token is not null) request.Headers.Authorization = new("Bearer", token);
        using var response = await _http.SendAsync(request);
        var result = await response.Content.ReadFromJsonAsync<JsonObject>() ?? throw new InvalidOperationException("Cursay returned an invalid response.");
        if (!response.IsSuccessStatusCode) throw new CloudServiceException((int)response.StatusCode, result["error"]?["code"]?.GetValue<string>(), result["error"]?["message"]?.GetValue<string>() ?? "Cursay Cloud is unavailable.");
        return result;
    }
    public Task<JsonObject> BeginLinkAsync() => RequestAsync("/api/v1/device/authorizations", HttpMethod.Post, new { device_name = Environment.MachineName, platform = "windows" });
    public async Task<bool> PollLinkAsync(string code)
    {
        try {
            var turn = Interlocked.Read(ref _generation);
            var result = await RequestAsync("/api/v1/device/token", HttpMethod.Post, new { device_code = code });
            await _tokenLock.WaitAsync();
            try { if(turn!=Interlocked.Read(ref _generation))throw new InvalidOperationException("Linking canceled by sign-out."); SaveTokens(result); return true; }
            finally { _tokenLock.Release(); }
        }
        catch (CloudServiceException e) when (e.Code == "authorization_pending") { return false; }
    }
    private CloudTokens SaveTokens(JsonObject result, string? deviceId = null)
    {
        var now = DateTimeOffset.UtcNow;
        var tokens = new CloudTokens(result["access_token"]!.GetValue<string>(), now.AddSeconds(result["expires_in"]!.GetValue<int>()), result["refresh_token"]!.GetValue<string>(), now.AddSeconds(result["refresh_expires_in"]!.GetValue<int>()), result["device_id"]?.GetValue<string>() ?? deviceId!);
        ProtectedFile.Save(_path, tokens); return tokens;
    }
    public async Task<CloudTokens> TokensAsync(bool forceRefresh = false)
    {
        await _tokenLock.WaitAsync();
        try
        {
            var tokens = ProtectedFile.Load<CloudTokens>(_path) ?? throw new InvalidOperationException("Link this Windows device to your Cursay account.");
            if (tokens.RefreshExpiresAt <= DateTimeOffset.UtcNow) { File.Delete(_path); throw new InvalidOperationException("Cursay sign-in expired. Link this device again."); }
            if(!forceRefresh && tokens.AccessExpiresAt > DateTimeOffset.UtcNow.AddSeconds(30))return tokens;
            var turn=Interlocked.Read(ref _generation);
            var refreshed=await RequestAsync("/api/v1/device/refresh", HttpMethod.Post, new { refresh_token = tokens.RefreshToken });
            if(turn!=Interlocked.Read(ref _generation))throw new InvalidOperationException("Signed out.");
            return SaveTokens(refreshed,tokens.DeviceId);
        }
        finally { _tokenLock.Release(); }
    }
    public async Task<JsonObject> AuthorizedAsync(string path, object? body = null)
    {
        var tokens = await TokensAsync();
        try { return await RequestAsync(path, body is null ? HttpMethod.Get : HttpMethod.Post, body, tokens.AccessToken); }
        catch (CloudServiceException e) when (e.Status == 401) { tokens = await TokensAsync(true); return await RequestAsync(path, body is null ? HttpMethod.Get : HttpMethod.Post, body, tokens.AccessToken); }
    }
    public async Task<TranscriptionResult> TranscribeAsync(TranscriptionClient speech, string path, string language)
    {
        var account = await AuthorizedAsync("/api/v1/account");
        if (account["entitlement"]?.GetValue<bool>() != true || account["plan"]?.GetValue<string>() is not ("pro" or "trial") || (account["allowance_seconds"]?.GetValue<int>() ?? 0)<=0) throw new InvalidOperationException("Cursay Pro or a trial is required for cloud dictation.");
        if((account["remaining_seconds"]?.GetValue<int>()??0)<=0)throw new InvalidOperationException("Your cloud allowance is used up. Use Local Whisper or wait for it to renew.");
        var tokens = await TokensAsync();
        return await speech.TranscribeAsync(path, "https://cursay.com/api/v1/audio/transcriptions", "cursay-cloud", language, bearerToken: tokens.AccessToken, idempotencyKey: Guid.NewGuid().ToString());
    }
    public async Task<bool> RevokeAsync()
    {
        CloudTokens? tokens;
        try { tokens=await TokensAsync(); } catch { tokens=ProtectedFile.Load<CloudTokens>(_path); }
        Interlocked.Increment(ref _generation);
        await _tokenLock.WaitAsync();
        try { tokens=ProtectedFile.Load<CloudTokens>(_path); if(File.Exists(_path))File.Delete(_path); }
        finally { _tokenLock.Release(); }
        if(tokens is null)return true;
        try { var response=await RequestAsync($"/api/v1/devices/{tokens.DeviceId}", HttpMethod.Delete, token: tokens.AccessToken); return response["revoked"]?.GetValue<bool>()==true; }
        catch { return false; }
    }
    public void Dispose() { _http.Dispose(); _tokenLock.Dispose(); }
}

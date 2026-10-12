using System.Text.Json.Nodes;
using System.Text.Json;
using System.Security.Cryptography;

namespace Cursay.Windows;

public sealed class MemorySync(CloudClient cloud)
{
    private readonly string _path = Path.Combine(AppPaths.DataDirectory, "memory-outbox.dpapi");
    private readonly SemaphoreSlim _sync = new(1);
    private readonly object _stateLock = new();
    private JsonObject _state = Load();
    private long _generation;
    private static JsonObject Load()
    {
        try { return ProtectedFile.Load<JsonObject>(Path.Combine(AppPaths.DataDirectory, "memory-outbox.dpapi")) ?? new JsonObject { ["pending"] = new JsonArray(), ["deletions"] = new JsonArray(), ["vocabulary"] = new JsonArray() }; }
        catch(Exception e) when(e is CryptographicException or JsonException or IOException) { return new JsonObject { ["pending"] = new JsonArray(), ["deletions"] = new JsonArray(), ["vocabulary"] = new JsonArray(), ["unreadable"] = true }; }
    }
    private void Save() => ProtectedFile.Save(_path, _state);
    public void Reset() { lock (_stateLock) { _generation++; _state = new JsonObject { ["pending"] = new JsonArray(), ["deletions"] = new JsonArray(), ["vocabulary"] = new JsonArray() }; Save(); } }
    public string Vocabulary { get { lock (_stateLock) return string.Join(", ", _state["vocabulary"]!.AsArray().Select(v => v!.GetValue<string>()).Take(100)); } }
    public string? CaptureScope { get { lock(_stateLock) return _state["enabled"]?.GetValue<bool>() == true ? $"{_state["account"]?.GetValue<string>()}:{_state["epoch"]?.GetValue<string>()}" : null; } }
    public void Enqueue(Dictation entry, string? expectedScope)
    {
        lock (_stateLock)
        {
            if (expectedScope is null || expectedScope != CaptureScope) return;
            var id = entry.Id.ToString();
            if (_state["deletions"]!.AsArray().Any(v => v!.GetValue<string>() == id)) return;
            _state["pending"]!.AsArray().Add(new JsonObject {
                ["id"] = id, ["epoch"] = _state["epoch"]!.GetValue<string>(), ["revision"] = 1,
                ["original_text"] = entry.RawText, ["final_text"] = entry.FinalText,
                ["mode"] = entry.Mode.ToString().ToLowerInvariant(), ["platform"] = "windows",
                ["created_at"] = entry.CreatedAt.ToUniversalTime().ToString("O"), ["project_id"] = null,
            }); Save();
        }
    }
    public void Delete(Guid id)
    {
        lock (_stateLock)
        {
            if (_state["account"] is null) return;
            var value = id.ToString();
            var pending = _state["pending"]!.AsArray();
            foreach (var entry in pending.Where(v => v!["id"]!.GetValue<string>() == value).ToList()) pending.Remove(entry);
            if (!_state["deletions"]!.AsArray().Any(v => v!.GetValue<string>() == value)) _state["deletions"]!.AsArray().Add(value);
            Save();
        }
    }
    public async Task<string> SyncAsync()
    {
        lock(_stateLock){if(_state["unreadable"]?.GetValue<bool>()==true)return "Memory queue could not be opened. Local dictation works. Sign out before linking again.";}
        if (!await _sync.WaitAsync(0)) return "Memory sync in progress";
        try
        {
            long cursor, turn; lock (_stateLock) { cursor = _state["cursor"]?.GetValue<long>() ?? 0; turn = _generation; }
            var page = await cloud.AuthorizedAsync($"/api/v1/memory?cursor={cursor}");
            bool changed;
            lock (_stateLock) { if(turn!=_generation)return "Memory sync canceled"; changed = _state["account"]?.GetValue<string>() != page["settings"]!["account_id"]!.GetValue<string>() || _state["epoch"]?.GetValue<string>() != page["settings"]!["epoch"]!.GetValue<string>(); }
            if (changed) { lock(_stateLock) { if(turn!=_generation)return "Memory sync canceled"; _state = new JsonObject { ["pending"] = new JsonArray(), ["deletions"] = new JsonArray(), ["vocabulary"] = new JsonArray() }; Save(); } page = await cloud.AuthorizedAsync("/api/v1/memory"); }
            while (true)
            {
                lock (_stateLock)
                {
                    if(turn!=_generation)return "Memory sync canceled";
                    _state["account"] = page["settings"]!["account_id"]!.GetValue<string>(); _state["epoch"] = page["settings"]!["epoch"]!.GetValue<string>();
                    _state["enabled"] = page["settings"]!["enabled"]!.GetValue<bool>(); _state["cursor"] = page["cursor"]!.GetValue<long>();
                    var deleted = page["captures"]!.AsArray().Where(c => c!["deleted_at"] is not null).Select(c => c!["id"]!.GetValue<string>()).ToHashSet();
                    var pending = _state["pending"]!.AsArray();
                    foreach (var entry in pending.Where(e => deleted.Contains(e!["id"]!.GetValue<string>())).ToList()) pending.Remove(entry);
                    var deletionQueue = _state["deletions"]!.AsArray();
                    foreach(var id in deletionQueue.Where(v=>deleted.Contains(v!.GetValue<string>())).ToList())deletionQueue.Remove(id);
                    if (!_state["enabled"]!.GetValue<bool>()) pending.Clear();
                    _state["vocabulary"] = new JsonArray(page["items"]!.AsArray().Where(i => i!["kind"]!.GetValue<string>() == "vocabulary" && i["status"]!.GetValue<string>() == "confirmed" && i["preferred"] is not null).Select(i => JsonValue.Create(i!["preferred"]!.GetValue<string>()) as JsonNode).ToArray());
                    cursor = page["cursor"]!.GetValue<long>(); Save();
                }
                if (!page["has_more"]!.GetValue<bool>()) break;
                page = await cloud.AuthorizedAsync($"/api/v1/memory?cursor={cursor}");
            }
            List<string> deletions; List<JsonNode> entries;
            lock (_stateLock) { deletions = _state["deletions"]!.AsArray().Select(v => v!.GetValue<string>()).ToList(); entries = _state["pending"]!.AsArray().Select(v => v!.DeepClone()).ToList(); }
            foreach (var id in deletions)
            {
                lock(_stateLock) { if(turn!=_generation)return "Memory sync canceled"; }
                await cloud.AuthorizedAsync("/api/v1/memory", new { action = "delete", id });
                lock (_stateLock) { if(turn!=_generation)return "Memory sync canceled"; var list = _state["deletions"]!.AsArray(); foreach (var v in list.Where(v => v!.GetValue<string>() == id).ToList()) list.Remove(v); Save(); }
            }
            foreach (var entry in entries)
            {
                lock(_stateLock) { if(turn!=_generation)return "Memory sync canceled"; }
                try { await cloud.AuthorizedAsync("/api/v1/memory", new { action = "save", capture = entry }); }
                catch (CloudServiceException e) when (e.Code == "sync_conflict") { }
                lock (_stateLock) { if(turn!=_generation)return "Memory sync canceled"; var list = _state["pending"]!.AsArray(); foreach (var v in list.Where(v => v!["id"]!.GetValue<string>() == entry["id"]!.GetValue<string>()).ToList()) list.Remove(v); Save(); }
            }
            lock (_stateLock) return _state["enabled"]!.GetValue<bool>() ? "Memory synced" : "Memory off — enable it in the workspace";
        }
        catch { return "Memory sync pending. Local dictation is available."; }
        finally { _sync.Release(); }
    }
}

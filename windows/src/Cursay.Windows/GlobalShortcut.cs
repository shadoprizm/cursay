using System.ComponentModel;
using System.Runtime.InteropServices;

namespace Cursay.Windows;

public sealed class GlobalShortcut : NativeWindow, IDisposable
{
    private const int HotKeyId = 0x4352;
    private const int WmHotKey = 0x0312;
    private const uint ModControl = 0x0002;
    private const uint ModNoRepeat = 0x4000;
    private const uint VkSpace = 0x20;
    private const int VkControl = 0x11;
    private readonly System.Windows.Forms.Timer _releaseTimer = new() { Interval = 20 };
    private bool _held;

    public event EventHandler? Pressed;
    public event EventHandler? Released;

    public GlobalShortcut()
    {
        CreateHandle(new CreateParams());
        if (!RegisterHotKey(Handle, HotKeyId, ModControl | ModNoRepeat, VkSpace))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(),
                "Cursay could not reserve Ctrl + Space. Close the app currently using that shortcut and try again.");
        }
        _releaseTimer.Tick += CheckReleased;
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == WmHotKey && message.WParam.ToInt32() == HotKeyId && !_held)
        {
            _held = true;
            Pressed?.Invoke(this, EventArgs.Empty);
            _releaseTimer.Start();
        }
        base.WndProc(ref message);
    }

    private void CheckReleased(object? sender, EventArgs eventArgs)
    {
        var spaceDown = (GetAsyncKeyState((int)VkSpace) & 0x8000) != 0;
        var controlDown = (GetAsyncKeyState(VkControl) & 0x8000) != 0;
        if (spaceDown && controlDown)
        {
            return;
        }
        _releaseTimer.Stop();
        _held = false;
        Released?.Invoke(this, EventArgs.Empty);
    }

    public void Dispose()
    {
        _releaseTimer.Stop();
        _releaseTimer.Dispose();
        UnregisterHotKey(Handle, HotKeyId);
        DestroyHandle();
        GC.SuppressFinalize(this);
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr window, int id, uint modifiers, uint key);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnregisterHotKey(IntPtr window, int id);
    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int key);
}

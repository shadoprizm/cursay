using System.Runtime.InteropServices;

namespace Cursay.Windows;

public sealed class PasteController
{
    private const uint InputKeyboard = 1;
    private const ushort VkControl = 0x11;
    private const ushort VkV = 0x56;
    private const uint KeyUp = 0x0002;
    private IntPtr _lastTarget;

    public IntPtr CaptureTarget(IntPtr cursayWindow)
    {
        var foreground = GetForegroundWindow();
        if (foreground != IntPtr.Zero && foreground != cursayWindow && IsWindow(foreground))
        {
            _lastTarget = foreground;
            return foreground;
        }
        return IsWindow(_lastTarget) ? _lastTarget : IntPtr.Zero;
    }

    public bool Copy(string text)
    {
        for (var attempt = 0; attempt < 5; attempt++)
        {
            try
            {
                Clipboard.SetText(text);
                return Clipboard.ContainsText() && Clipboard.GetText() == text;
            }
            catch (ExternalException)
            {
                Thread.Sleep(30);
            }
        }
        return false;
    }

    public async Task<bool> PasteAsync(string text, IntPtr target)
    {
        if (!Copy(text) || target == IntPtr.Zero || !IsWindow(target))
        {
            return false;
        }

        ShowWindow(target, 9);
        SetForegroundWindow(target);
        await Task.Delay(80);
        if (GetForegroundWindow() != target || Clipboard.GetText() != text)
        {
            return false;
        }

        var inputs = new[]
        {
            Keyboard(VkControl, 0),
            Keyboard(VkV, 0),
            Keyboard(VkV, KeyUp),
            Keyboard(VkControl, KeyUp),
        };
        return SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<Input>()) == (uint)inputs.Length;
    }

    private static Input Keyboard(ushort key, uint flags) => new()
    {
        Type = InputKeyboard,
        Union = new InputUnion { Keyboard = new KeyboardInput { VirtualKey = key, Flags = flags } },
    };

    [StructLayout(LayoutKind.Sequential)]
    private struct Input { public uint Type; public InputUnion Union; }
    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion { [FieldOffset(0)] public KeyboardInput Keyboard; }
    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardInput
    {
        public ushort VirtualKey;
        public ushort ScanCode;
        public uint Flags;
        public uint Time;
        public UIntPtr ExtraInfo;
    }

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr window, int command);
    [DllImport("user32.dll")]
    private static extern bool IsWindow(IntPtr window);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint count, Input[] inputs, int size);
}

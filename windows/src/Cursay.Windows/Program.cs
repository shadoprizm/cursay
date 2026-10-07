namespace Cursay.Windows;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        using var mutex = new Mutex(true, "Local\\Cursay.Windows.Singleton", out var isFirstInstance);
        if (!isFirstInstance)
        {
            MessageBox.Show("Cursay is already running.", "Cursay", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        ApplicationConfiguration.Initialize();
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
        Application.ThreadException += (_, eventArgs) =>
            MessageBox.Show(eventArgs.Exception.Message, "Cursay", MessageBoxButtons.OK, MessageBoxIcon.Error);
        Application.Run(new MainForm());
        GC.KeepAlive(mutex);
    }
}

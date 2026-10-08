using System.Diagnostics;
using System.Drawing.Drawing2D;

namespace Cursay.Windows;

public sealed class MainForm : Form
{
    private static readonly Color Ink = Color.FromArgb(31, 42, 51);
    private static readonly Color Muted = Color.FromArgb(102, 113, 122);
    private static readonly Color Canvas = Color.FromArgb(247, 249, 248);
    private static readonly Color Mint = Color.FromArgb(32, 168, 130);
    private static readonly Color MintPale = Color.FromArgb(224, 246, 239);

    private readonly AppSettings _settings = AppSettings.Load();
    private readonly HistoryStore _historyStore = new();
    private readonly List<Dictation> _history;
    private readonly AudioRecorder _recorder = new();
    private readonly TranscriptionClient _transcription = new();
    private readonly PasteController _paste = new();
    private readonly BackendProcess _backend = new();
    private readonly Panel _content = new() { Dock = DockStyle.Fill, BackColor = Canvas };
    private readonly Label _status = Label("Ready — hold Ctrl + Space to dictate", 12, FontStyle.Regular, Muted);
    private readonly Label _backendStatus = Label("Speech service: checking…", 9, FontStyle.Regular, Muted);
    private readonly Label _latest = Label("Your latest dictation will appear here.", 14, FontStyle.Regular, Muted);
    private readonly NotifyIcon _tray;
    private readonly System.Windows.Forms.Timer _targetTimer = new() { Interval = 250 };
    private GlobalShortcut? _shortcut;
    private IntPtr _pasteTarget;
    private bool _busy;
    private bool _exitRequested;
    private Button? _recordButton;

    public MainForm()
    {
        AppPaths.EnsureDirectories();
        _history = _historyStore.Load().ToList();
        Text = "Cursay";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(850, 580);
        Size = new Size(1040, 700);
        BackColor = Canvas;
        Font = new Font("Segoe UI", 10);

        var sidebar = BuildSidebar();
        Controls.Add(_content);
        Controls.Add(sidebar);
        ShowDictate();

        var menu = new ContextMenuStrip();
        menu.Items.Add("Open Cursay", null, (_, _) => RestoreWindow());
        menu.Items.Add("Start dictation", null, (_, _) => ToggleRecording());
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Exit", null, (_, _) => ExitApplication());
        _tray = new NotifyIcon
        {
            Icon = SystemIcons.Application,
            Text = "Cursay — Ctrl + Space to dictate",
            Visible = true,
            ContextMenuStrip = menu,
        };
        _tray.DoubleClick += (_, _) => RestoreWindow();

        FormClosing += OnFormClosing;
        Shown += OnShown;
        _targetTimer.Tick += (_, _) => _paste.CaptureTarget(Handle);
        _targetTimer.Start();
    }

    private async void OnShown(object? sender, EventArgs eventArgs)
    {
        try
        {
            _shortcut = new GlobalShortcut();
            _shortcut.Pressed += (_, _) => StartRecording();
            _shortcut.Released += async (_, _) => await StopRecordingAsync();
        }
        catch (Exception exception)
        {
            SetStatus(exception.Message, true);
        }

        if (_settings.StartLocalBackend)
        {
            _backend.TryStart();
        }
        await RefreshBackendStatusAsync(waitForStartup: true);

        if (Environment.GetCommandLineArgs().Contains("--background", StringComparer.OrdinalIgnoreCase))
        {
            Hide();
            ShowInTaskbar = false;
        }
    }

    private Panel BuildSidebar()
    {
        var sidebar = new Panel { Dock = DockStyle.Left, Width = 188, BackColor = Color.White, Padding = new(14, 20, 14, 16) };
        var logo = Label("Cursay", 22, FontStyle.Bold, Ink);
        logo.Dock = DockStyle.Top;
        logo.Height = 60;
        logo.Padding = new Padding(10, 5, 0, 0);
        sidebar.Controls.Add(logo);

        var nav = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            AutoSize = true,
            Padding = new Padding(0, 8, 0, 0),
        };
        nav.Controls.Add(NavButton("●  Dictate", ShowDictate));
        nav.Controls.Add(NavButton("▤  History", ShowHistory));
        nav.Controls.Add(NavButton("↗  Insights", ShowInsights));
        nav.Controls.Add(NavButton("⚙  Settings", ShowSettings));
        sidebar.Controls.Add(nav);

        var privacy = Label("Private by default\nAudio stays on this PC", 9, FontStyle.Regular, Muted);
        privacy.Dock = DockStyle.Bottom;
        privacy.Height = 54;
        privacy.Padding = new Padding(10, 0, 0, 0);
        sidebar.Controls.Add(privacy);
        return sidebar;
    }

    private static Button NavButton(string text, Action action)
    {
        var button = new Button
        {
            Text = text,
            TextAlign = ContentAlignment.MiddleLeft,
            Width = 160,
            Height = 44,
            FlatStyle = FlatStyle.Flat,
            BackColor = Color.White,
            ForeColor = Ink,
            Margin = new Padding(0, 2, 0, 2),
            Padding = new Padding(8, 0, 0, 0),
            Cursor = Cursors.Hand,
        };
        button.FlatAppearance.BorderSize = 0;
        button.FlatAppearance.MouseOverBackColor = MintPale;
        button.Click += (_, _) => action();
        return button;
    }

    private void ShowDictate()
    {
        _content.Controls.Clear();
        var page = Page("Dictate", "Hold Ctrl + Space anywhere, speak naturally, then release.");
        var card = Card(760, 390);
        card.Anchor = AnchorStyles.Top;
        card.Location = new Point(35, 110);

        _status.Location = new Point(30, 28);
        _status.AutoSize = true;
        card.Controls.Add(_status);
        _backendStatus.Location = new Point(30, 58);
        _backendStatus.AutoSize = true;
        card.Controls.Add(_backendStatus);

        var mode = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            Location = new Point(30, 96),
            Width = 180,
        };
        mode.Items.AddRange(Enum.GetNames<DictationMode>());
        mode.SelectedItem = _settings.Mode.ToString();
        mode.SelectedIndexChanged += (_, _) =>
        {
            if (Enum.TryParse<DictationMode>(mode.SelectedItem?.ToString(), out var selected))
            {
                _settings.Mode = selected;
                SaveSettings();
            }
        };
        card.Controls.Add(mode);

        _recordButton = AccentButton(_recorder.IsRecording ? "Release to finish" : "Hold to talk");
        _recordButton.Location = new Point(230, 92);
        _recordButton.MouseDown += (_, _) => StartRecording();
        _recordButton.MouseUp += async (_, _) => await StopRecordingAsync();
        card.Controls.Add(_recordButton);

        var latestTitle = Label("Latest dictation", 10, FontStyle.Bold, Ink);
        latestTitle.Location = new Point(30, 160);
        latestTitle.AutoSize = true;
        card.Controls.Add(latestTitle);
        _latest.Location = new Point(30, 192);
        _latest.Size = new Size(690, 116);
        _latest.AutoEllipsis = true;
        card.Controls.Add(_latest);

        var copy = SecondaryButton("Copy");
        copy.Location = new Point(30, 324);
        copy.Click += (_, _) =>
        {
            if (_latest.ForeColor != Muted && _paste.Copy(_latest.Text))
            {
                SetStatus("Copied to the clipboard");
            }
        };
        card.Controls.Add(copy);
        page.Controls.Add(card);
        _content.Controls.Add(page);
    }

    private void ShowHistory()
    {
        _content.Controls.Clear();
        var page = Page("History", "Search and reuse dictation stored privately on this PC.");
        var search = new TextBox { PlaceholderText = "Search dictations", Location = new Point(35, 104), Width = 430 };
        page.Controls.Add(search);
        var list = new FlowLayoutPanel
        {
            Location = new Point(35, 146),
            Size = new Size(760, 465),
            AutoScroll = true,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right,
        };

        void Render()
        {
            list.Controls.Clear();
            var matches = HistoryStore.Search(search.Text, _history);
            if (matches.Count == 0)
            {
                var empty = Label(search.TextLength == 0 ? "No dictations yet." : "No matching dictations.",
                    14, FontStyle.Regular, Muted);
                empty.AutoSize = true;
                empty.Margin = new Padding(8, 28, 0, 0);
                list.Controls.Add(empty);
                return;
            }
            foreach (var item in matches)
            {
                list.Controls.Add(HistoryCard(item, list.Width - 30, Render));
            }
        }
        search.TextChanged += (_, _) => Render();
        Render();
        page.Controls.Add(list);
        _content.Controls.Add(page);
    }

    private Control HistoryCard(Dictation item, int width, Action render)
    {
        var card = Card(width, 132);
        card.Margin = new Padding(0, 0, 0, 10);
        var text = Label(item.FinalText, 11, FontStyle.Regular, Ink);
        text.Location = new Point(18, 14);
        text.Size = new Size(width - 36, 54);
        text.AutoEllipsis = true;
        card.Controls.Add(text);
        var detail = Label($"{item.CreatedAt.LocalDateTime:g}  •  {item.Mode}  •  {item.WordCount} words",
            9, FontStyle.Regular, Muted);
        detail.Location = new Point(18, 76);
        detail.AutoSize = true;
        card.Controls.Add(detail);
        var copy = SecondaryButton("Copy");
        copy.Size = new Size(70, 30);
        copy.Location = new Point(width - 166, 89);
        copy.Click += (_, _) => _paste.Copy(item.FinalText);
        card.Controls.Add(copy);
        var delete = SecondaryButton("Delete");
        delete.Size = new Size(76, 30);
        delete.Location = new Point(width - 88, 89);
        delete.Click += (_, _) =>
        {
            _history.RemoveAll(entry => entry.Id == item.Id);
            _historyStore.Save(_history);
            render();
        };
        card.Controls.Add(delete);
        return card;
    }

    private void ShowInsights()
    {
        _content.Controls.Clear();
        var page = Page("Insights", "A private summary calculated from local dictation history.");
        var stats = HistoryStore.Stats(_history);
        page.Controls.Add(MetricCard("Dictations", stats.Dictations.ToString(), 35));
        page.Controls.Add(MetricCard("Words", stats.Words.ToString(), 275));
        page.Controls.Add(MetricCard("Minutes", (stats.Seconds / 60).ToString("0.0"), 515));
        var filler = Card(700, 180);
        filler.Location = new Point(35, 300);
        var title = Label("Filler words removed", 13, FontStyle.Bold, Ink);
        title.Location = new Point(22, 20);
        title.AutoSize = true;
        filler.Controls.Add(title);
        var summary = stats.Fillers.Count == 0
            ? "No filler words have been removed yet."
            : string.Join("     ", stats.Fillers.Select(item => $"{item.Word}  {item.Count}"));
        var values = Label(summary, 11, FontStyle.Regular, Muted);
        values.Location = new Point(22, 64);
        values.Size = new Size(650, 90);
        filler.Controls.Add(values);
        page.Controls.Add(filler);
        _content.Controls.Add(page);
    }

    private Panel MetricCard(string title, string value, int x)
    {
        var card = Card(220, 130);
        card.Location = new Point(x, 130);
        var number = Label(value, 25, FontStyle.Bold, Ink);
        number.Location = new Point(20, 20);
        number.AutoSize = true;
        card.Controls.Add(number);
        var caption = Label(title, 10, FontStyle.Regular, Muted);
        caption.Location = new Point(20, 80);
        caption.AutoSize = true;
        card.Controls.Add(caption);
        return card;
    }

    private void ShowSettings()
    {
        _content.Controls.Clear();
        var page = Page("Settings", "Configure dictation, privacy, and the local speech service.");
        var form = new TableLayoutPanel
        {
            Location = new Point(35, 112),
            Width = 730,
            Height = 450,
            ColumnCount = 2,
            RowCount = 9,
            BackColor = Color.White,
            Padding = new Padding(22),
        };
        form.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 210));
        form.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        var endpoint = SettingText(_settings.Endpoint);
        var model = SettingText(_settings.Model);
        var language = SettingText(_settings.Language);
        var autoPaste = SettingCheck("Paste automatically", _settings.AutoPaste);
        var fillers = SettingCheck("Remove filler words", _settings.RemoveFillers);
        var recordings = SettingCheck("Keep audio recordings", _settings.PreserveRecordings);
        var localBackend = SettingCheck("Start local speech service", _settings.StartLocalBackend);
        var launch = SettingCheck("Launch Cursay at sign-in", _settings.LaunchAtLogin);
        AddSetting(form, 0, "Transcription endpoint", endpoint);
        AddSetting(form, 1, "Model", model);
        AddSetting(form, 2, "Language", language);
        AddSetting(form, 3, "Automatic paste", autoPaste);
        AddSetting(form, 4, "Cleanup", fillers);
        AddSetting(form, 5, "Privacy", recordings);
        AddSetting(form, 6, "Local backend", localBackend);
        AddSetting(form, 7, "Startup", launch);
        var save = AccentButton("Save settings");
        save.Click += async (_, _) =>
        {
            _settings.Endpoint = endpoint.Text.Trim();
            _settings.Model = model.Text.Trim();
            _settings.Language = language.Text.Trim();
            _settings.AutoPaste = autoPaste.Checked;
            _settings.RemoveFillers = fillers.Checked;
            _settings.PreserveRecordings = recordings.Checked;
            _settings.StartLocalBackend = localBackend.Checked;
            _settings.LaunchAtLogin = launch.Checked;
            SaveSettings();
            if (_settings.StartLocalBackend)
            {
                _backend.TryStart();
            }
            await RefreshBackendStatusAsync(waitForStartup: false);
            SetStatus("Settings saved");
        };
        form.Controls.Add(save, 1, 8);
        page.Controls.Add(form);
        _content.Controls.Add(page);
    }

    private static void AddSetting(TableLayoutPanel form, int row, string label, Control control)
    {
        form.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        var caption = Label(label, 10, FontStyle.Regular, Ink);
        caption.Dock = DockStyle.Fill;
        caption.TextAlign = ContentAlignment.MiddleLeft;
        form.Controls.Add(caption, 0, row);
        control.Anchor = AnchorStyles.Left | AnchorStyles.Right;
        form.Controls.Add(control, 1, row);
    }

    private static TextBox SettingText(string value) => new() { Text = value, Width = 430 };
    private static CheckBox SettingCheck(string text, bool value) => new() { Text = text, Checked = value, AutoSize = true };

    private void ToggleRecording()
    {
        if (_recorder.IsRecording)
        {
            _ = StopRecordingAsync();
        }
        else
        {
            StartRecording();
        }
    }

    private void StartRecording()
    {
        if (_busy || _recorder.IsRecording)
        {
            return;
        }
        try
        {
            _pasteTarget = _paste.CaptureTarget(Handle);
            _recorder.Start();
            SetStatus("Listening… release Ctrl + Space when you are finished");
            if (_recordButton is not null)
            {
                _recordButton.Text = "Release to finish";
            }
        }
        catch (Exception exception)
        {
            SetStatus($"Microphone unavailable: {exception.Message}", true);
        }
    }

    private async Task StopRecordingAsync()
    {
        if (!_recorder.IsRecording || _busy)
        {
            return;
        }
        _busy = true;
        string? recordingPath = null;
        try
        {
            var recording = await _recorder.StopAsync();
            recordingPath = recording.Path;
            SetStatus("Transcribing and cleaning your words…");
            if (_recordButton is not null)
            {
                _recordButton.Text = "Working…";
                _recordButton.Enabled = false;
            }

            var result = await _transcription.TranscribeAsync(recording.Path, _settings.Endpoint,
                _settings.Model, _settings.Language);
            var cleaned = TranscriptCleaner.Clean(result.Text, _settings.Mode, _settings.RemoveFillers);
            string? preservedPath = null;
            if (_settings.PreserveRecordings)
            {
                preservedPath = Path.Combine(AppPaths.RecordingsDirectory,
                    $"{DateTime.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}.wav");
                File.Move(recording.Path, preservedPath);
                recordingPath = null;
            }

            var entry = Dictation.Create(result.Text.Trim(), cleaned.Text, _settings.Mode,
                result.Language ?? _settings.Language, result.Duration ?? recording.Duration,
                result.Provider ?? "speech service", result.Model ?? _settings.Model,
                cleaned.Metadata.FillersRemoved, preservedPath);
            _history.Insert(0, entry);
            _historyStore.Save(_history);
            _latest.Text = cleaned.Text;
            _latest.ForeColor = Ink;

            var pasted = _settings.AutoPaste && await _paste.PasteAsync(cleaned.Text, _pasteTarget);
            if (!pasted && !_paste.Copy(cleaned.Text))
            {
                throw new InvalidOperationException("Cursay could not update the clipboard.");
            }
            SetStatus(pasted ? "Pasted into your active app" : "Copied to the clipboard");
            _tray.ShowBalloonTip(1800, "Cursay", pasted ? "Dictation pasted" : "Dictation copied", ToolTipIcon.Info);
        }
        catch (Exception exception)
        {
            SetStatus(exception.Message, true);
            _tray.ShowBalloonTip(2500, "Cursay needs attention", exception.Message, ToolTipIcon.Warning);
        }
        finally
        {
            if (recordingPath is not null)
            {
                File.Delete(recordingPath);
            }
            _busy = false;
            _pasteTarget = IntPtr.Zero;
            if (_recordButton is not null)
            {
                _recordButton.Text = "Hold to talk";
                _recordButton.Enabled = true;
            }
        }
    }

    private async Task RefreshBackendStatusAsync(bool waitForStartup)
    {
        var attempts = waitForStartup ? 20 : 1;
        for (var attempt = 0; attempt < attempts; attempt++)
        {
            if (await _transcription.IsHealthyAsync(_settings.Endpoint))
            {
                _backendStatus.Text = "Speech service: connected";
                _backendStatus.ForeColor = Mint;
                return;
            }
            if (attempt + 1 < attempts)
            {
                await Task.Delay(500);
            }
        }
        _backendStatus.Text = "Speech service: unavailable — check Settings";
        _backendStatus.ForeColor = Color.FromArgb(188, 68, 61);
    }

    private void SaveSettings()
    {
        try
        {
            _settings.Save();
        }
        catch (Exception exception)
        {
            SetStatus($"Settings could not be saved: {exception.Message}", true);
        }
    }

    private void SetStatus(string text, bool error = false)
    {
        _status.Text = text;
        _status.ForeColor = error ? Color.FromArgb(188, 68, 61) : Muted;
    }

    private static Panel Page(string title, string subtitle)
    {
        var page = new Panel { Dock = DockStyle.Fill, BackColor = Canvas, AutoScroll = true };
        var heading = Label(title, 24, FontStyle.Bold, Ink);
        heading.Location = new Point(35, 25);
        heading.AutoSize = true;
        page.Controls.Add(heading);
        var description = Label(subtitle, 10, FontStyle.Regular, Muted);
        description.Location = new Point(38, 70);
        description.AutoSize = true;
        page.Controls.Add(description);
        return page;
    }

    private static Panel Card(int width, int height) => new RoundedPanel
    {
        Width = width,
        Height = height,
        BackColor = Color.White,
        Padding = new Padding(10),
    };

    private static Button AccentButton(string text)
    {
        var button = new Button
        {
            Text = text,
            AutoSize = false,
            Size = new Size(170, 40),
            BackColor = Mint,
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
        };
        button.FlatAppearance.BorderSize = 0;
        return button;
    }

    private static Button SecondaryButton(string text)
    {
        var button = new Button
        {
            Text = text,
            Size = new Size(90, 34),
            BackColor = Color.White,
            ForeColor = Ink,
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
        };
        button.FlatAppearance.BorderColor = Color.FromArgb(218, 224, 221);
        return button;
    }

    private static Label Label(string text, float size, FontStyle style, Color color) => new()
    {
        Text = text,
        Font = new Font("Segoe UI", size, style),
        ForeColor = color,
        BackColor = Color.Transparent,
    };

    private void RestoreWindow()
    {
        ShowInTaskbar = true;
        Show();
        WindowState = FormWindowState.Normal;
        Activate();
    }

    private void OnFormClosing(object? sender, FormClosingEventArgs eventArgs)
    {
        if (!_exitRequested && eventArgs.CloseReason == CloseReason.UserClosing)
        {
            eventArgs.Cancel = true;
            Hide();
            ShowInTaskbar = false;
            _tray.ShowBalloonTip(1500, "Cursay is still listening", "Hold Ctrl + Space to dictate.", ToolTipIcon.Info);
        }
    }

    private void ExitApplication()
    {
        _exitRequested = true;
        Close();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _targetTimer.Dispose();
            _shortcut?.Dispose();
            _recorder.Dispose();
            _transcription.Dispose();
            _backend.Dispose();
            _tray.Dispose();
        }
        base.Dispose(disposing);
    }

    private sealed class RoundedPanel : Panel
    {
        protected override void OnResize(EventArgs eventArgs)
        {
            base.OnResize(eventArgs);
            using var path = new GraphicsPath();
            const int radius = 18;
            path.AddArc(0, 0, radius, radius, 180, 90);
            path.AddArc(Width - radius, 0, radius, radius, 270, 90);
            path.AddArc(Width - radius, Height - radius, radius, radius, 0, 90);
            path.AddArc(0, Height - radius, radius, radius, 90, 90);
            path.CloseFigure();
            Region = new Region(path);
        }
    }
}

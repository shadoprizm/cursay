#define MyAppName "Cursay"
#ifndef MyAppVersion
  #define MyAppVersion "1.2.1"
#endif
#define MyAppPublisher "shadoprizm"
#define MyAppURL "https://cursay.com/"
#define MyAppExeName "Cursay.exe"

[Setup]
AppId={{6C71158F-7D33-4E60-82A5-F12F93BFAAB2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL=https://github.com/shadoprizm/cursay/issues
DefaultDirName={localappdata}\Programs\Cursay
DefaultGroupName=Cursay
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\artifacts
OutputBaseFilename=Cursay-{#MyAppVersion}-windows-x64-setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=force
RestartApplications=no
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Cursay Windows installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startup"; Description: "Start Cursay when I sign in"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
Source: "..\artifacts\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Cursay"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Cursay"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Cursay"; ValueData: """{app}\{#MyAppExeName}"" --background"; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Cursay"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM Cursay.exe /F"; Flags: runhidden; RunOnceId: "StopCursay"

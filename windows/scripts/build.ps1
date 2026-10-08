param(
    [string]$Version = "",
    [switch]$SkipBackend,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$WindowsRoot = Split-Path -Parent $PSScriptRoot
$RepositoryRoot = Split-Path -Parent $WindowsRoot
$Artifacts = Join-Path $WindowsRoot "artifacts"
$Publish = Join-Path $Artifacts "publish"
$BackendDist = Join-Path $Artifacts "backend"
$PyInstallerSpec = Join-Path $Artifacts "pyinstaller-spec"

if (-not $Version) {
    $ProjectFile = Get-Content (Join-Path $RepositoryRoot "pyproject.toml") -Raw
    if ($ProjectFile -notmatch '(?m)^version\s*=\s*"([^"]+)"') {
        throw "Could not read the release version from pyproject.toml."
    }
    $Version = $Matches[1]
}

if (Test-Path $Artifacts) {
    Remove-Item $Artifacts -Recurse -Force
}
New-Item $Publish -ItemType Directory -Force | Out-Null
New-Item $PyInstallerSpec -ItemType Directory -Force | Out-Null

dotnet test (Join-Path $WindowsRoot "Cursay.Windows.sln") -c Release
dotnet publish (Join-Path $WindowsRoot "src\Cursay.Windows\Cursay.Windows.csproj") `
    -c Release -r win-x64 --self-contained true `
    -p:Version=$Version -p:PublishSingleFile=true `
    -o $Publish

if (-not $SkipBackend) {
    $VirtualEnvironment = Join-Path $Artifacts "backend-venv"
    python -m venv $VirtualEnvironment
    $Python = Join-Path $VirtualEnvironment "Scripts\python.exe"
    & $Python -m pip install --disable-pip-version-check --require-hashes `
        -r (Join-Path $RepositoryRoot "backend\requirements.lock")
    & $Python -m pip install --disable-pip-version-check "pyinstaller==6.16.0"
    Push-Location (Join-Path $RepositoryRoot "backend")
    try {
        & $Python -m PyInstaller --noconfirm --clean --onedir --name cursay-stt `
            --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers `
            --distpath $BackendDist --workpath (Join-Path $Artifacts "pyinstaller-work") `
            --specpath $PyInstallerSpec windows_server.py
    }
    finally {
        Pop-Location
    }
    New-Item (Join-Path $Publish "backend") -ItemType Directory -Force | Out-Null
    Copy-Item (Join-Path $BackendDist "cursay-stt\*") (Join-Path $Publish "backend") -Recurse -Force
}

if (-not $SkipInstaller) {
    $Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
    if (-not $Iscc) {
        $Iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    }
    if (-not (Test-Path $Iscc)) {
        throw "Inno Setup 6 is required to build the Windows installer."
    }
    & $Iscc "/DMyAppVersion=$Version" (Join-Path $WindowsRoot "installer\Cursay.iss")
}

Get-ChildItem $Artifacts -Filter "Cursay-*.exe" | ForEach-Object {
    $Hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $($_.Name)" | Set-Content "$($_.FullName).sha256" -Encoding ascii
}

Write-Host "Windows artifacts are in $Artifacts"

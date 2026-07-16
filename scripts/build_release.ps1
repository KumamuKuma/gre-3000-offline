[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )

    Write-Host "==> $Label"
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

function Remove-WorkspaceDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$AllowedRoot
    )

    $candidate = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetFullPath($AllowedRoot).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $prefix = $root + [System.IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith(
        $prefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to remove path outside $root`: $candidate"
    }
    if (Test-Path -LiteralPath $candidate) {
        Remove-Item -LiteralPath $candidate -Recurse -Force
    }
}

function Get-PeSubsystem {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    $reader = [System.IO.BinaryReader]::new($stream)
    try {
        if ($reader.ReadUInt16() -ne 0x5A4D) {
            throw "Release executable does not have an MZ header: $Path"
        }
        $reader.BaseStream.Seek(0x3C, [System.IO.SeekOrigin]::Begin) | Out-Null
        $peOffset = $reader.ReadInt32()
        $reader.BaseStream.Seek($peOffset, [System.IO.SeekOrigin]::Begin) | Out-Null
        if ($reader.ReadUInt32() -ne 0x00004550) {
            throw "Release executable does not have a PE header: $Path"
        }
        $reader.BaseStream.Seek(20 + 68, [System.IO.SeekOrigin]::Current) | Out-Null
        return $reader.ReadUInt16()
    }
    finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

function Initialize-NativeWindowInspector {
    if ("GreReleaseWindowInspector" -as [type]) {
        return
    }

    $source = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public sealed class GreReleaseWindowRecord
{
    public IntPtr Handle;
    public int ProcessId;
    public bool Visible;
    public string MainWindowTitle;
    public string WindowClass;
}

public static class GreReleaseWindowInspector
{
    private const uint WmClose = 0x0010;
    private delegate bool EnumWindowsCallback(IntPtr handle, IntPtr extraData);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsCallback callback, IntPtr extraData);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr handle, out uint processId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr handle, StringBuilder text, int maximum);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(IntPtr handle, StringBuilder text, int maximum);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr handle);

    [DllImport("user32.dll")]
    private static extern bool PostMessage(IntPtr handle, uint message, IntPtr wParam, IntPtr lParam);

    public static GreReleaseWindowRecord[] GetWindows(int wantedProcessId)
    {
        var result = new List<GreReleaseWindowRecord>();
        EnumWindows(delegate(IntPtr handle, IntPtr ignored)
        {
            uint processId;
            GetWindowThreadProcessId(handle, out processId);
            if (processId == wantedProcessId)
            {
                var title = new StringBuilder(1024);
                var windowClass = new StringBuilder(256);
                GetWindowText(handle, title, title.Capacity);
                GetClassName(handle, windowClass, windowClass.Capacity);
                result.Add(new GreReleaseWindowRecord
                {
                    Handle = handle,
                    ProcessId = (int)processId,
                    Visible = IsWindowVisible(handle),
                    MainWindowTitle = title.ToString(),
                    WindowClass = windowClass.ToString()
                });
            }
            return true;
        }, IntPtr.Zero);
        return result.ToArray();
    }

    public static bool RequestNormalClose(IntPtr handle)
    {
        return PostMessage(handle, WmClose, IntPtr.Zero, IntPtr.Zero);
    }
}
'@
    Add-Type -TypeDefinition $source
}

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Deploy = Join-Path $RepoRoot ".venv\Scripts\pyside6-deploy.exe"
$Spec = Join-Path $RepoRoot "pysidedeploy.spec"
$Database = Join-Path $RepoRoot "build\generated\words.db"
$AuditJson = Join-Path $RepoRoot "build\audit\report.json"
$AuditHtml = Join-Path $RepoRoot "outputs\词库导入审计报告.html"
$IconSvg = Join-Path $RepoRoot "resources\app.svg"
$IconIco = Join-Path $RepoRoot "resources\app.ico"
$DeployExe = Join-Path $RepoRoot "build\release\GRE 3000 词离线版.exe"
$OutputExe = Join-Path $RepoRoot "outputs\GRE 3000 词离线版.exe"
$Instructions = Join-Path $RepoRoot "outputs\使用说明.txt"
$SmokeProfile = Join-Path $RepoRoot "build\smoke-profile"
$ExpectedTitle = "GRE 3000 词离线版"
$WindowsGuiSubsystem = 2

foreach ($requiredFile in @($Python, $Deploy, $Spec, $IconSvg, $Instructions)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required release input not found: $requiredFile"
    }
}

if ([string]::IsNullOrWhiteSpace($env:GRE_SOURCE_PDF)) {
    $env:GRE_SOURCE_PDF = "D:\桌面\LGU\GRE\张巍GRE镇考3000词-乱序（2026年）.pdf"
}
if (-not (Test-Path -LiteralPath $env:GRE_SOURCE_PDF -PathType Leaf)) {
    throw "GRE source PDF not found: $($env:GRE_SOURCE_PDF)"
}

$ReleaseTemp = Join-Path $RepoRoot "work\release-temp"
$NuitkaCache = Join-Path $RepoRoot "work\nuitka-cache"
New-Item -ItemType Directory -Force -Path $ReleaseTemp | Out-Null
New-Item -ItemType Directory -Force -Path $NuitkaCache | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "outputs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "build\release") | Out-Null
$env:TEMP = $ReleaseTemp
$env:TMP = $ReleaseTemp
$env:NUITKA_CACHE_DIR = $NuitkaCache
$env:QT_QPA_PLATFORM = "offscreen"
# PySide6 6.11.1 opens its INI spec with Python's default text encoding.
# Force UTF-8 so the Chinese application title is parsed consistently on GBK Windows.
$env:PYTHONUTF8 = "1"
Initialize-NativeWindowInspector

Push-Location $RepoRoot
try {
    Invoke-External -Label "full pytest suite" -FilePath $Python -ArgumentList @(
        "-m", "pytest", "-v", "-p", "no:cacheprovider"
    )

    Invoke-External -Label "strict vocabulary import" -FilePath $Python -ArgumentList @(
        "-m", "gre_vocab_app.importer.build",
        "--pdf", $env:GRE_SOURCE_PDF,
        "--output", $Database,
        "--audit-json", $AuditJson,
        "--audit-html", $AuditHtml,
        "--overrides", (Join-Path $RepoRoot "src\gre_vocab_app\importer\overrides.json"),
        "--strict"
    )

    Invoke-External -Label "database and audit verification" -FilePath $Python -ArgumentList @(
        (Join-Path $RepoRoot "scripts\verify_release_artifacts.py"),
        $Database,
        $AuditJson,
        "--expected-records", "3292",
        "--expected-reviewed", "4"
    )

    Invoke-External -Label "SVG to multi-size ICO generation" -FilePath $Python -ArgumentList @(
        (Join-Path $RepoRoot "scripts\generate_icon.py"),
        $IconSvg,
        $IconIco
    )

    if (Test-Path -LiteralPath $DeployExe) {
        Remove-Item -LiteralPath $DeployExe -Force
    }
    if (Test-Path -LiteralPath $OutputExe) {
        Remove-Item -LiteralPath $OutputExe -Force
    }
    $specEncoding = [System.Text.UTF8Encoding]::new($false)
    $specSnapshot = [System.IO.File]::ReadAllText($Spec, $specEncoding)
    try {
        Invoke-External -Label "pyside6-deploy onefile build" -FilePath $Deploy -ArgumentList @(
            "-c", $Spec, "--extra-modules=Sql", "-f", "-v"
        )
    }
    finally {
        # PySide6 6.11.1 rewrites discovered modules and python_path in-place.
        # Preserve the reviewed, portable release configuration in source control.
        [System.IO.File]::WriteAllText($Spec, $specSnapshot, $specEncoding)
    }
    if (-not (Test-Path -LiteralPath $DeployExe -PathType Leaf)) {
        throw "pyside6-deploy returned without the expected executable: $DeployExe"
    }

    Copy-Item -LiteralPath $DeployExe -Destination $OutputExe -Force
    if (-not (Test-Path -LiteralPath $AuditHtml -PathType Leaf)) {
        throw "Strict importer did not generate the audit HTML: $AuditHtml"
    }

    $subsystem = Get-PeSubsystem -Path $OutputExe
    if ($subsystem -ne $WindowsGuiSubsystem) {
        throw "Expected Windows GUI subsystem (2), found $subsystem. A console window may open."
    }

    Remove-WorkspaceDirectory -Path $SmokeProfile -AllowedRoot (Join-Path $RepoRoot "build")
    New-Item -ItemType Directory -Force -Path $SmokeProfile | Out-Null
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    Remove-Item Env:GRE_WORDS_DB -ErrorAction SilentlyContinue
    $env:GRE_APP_DATA_ROOT = $SmokeProfile

    Write-Host "==> native packaged executable smoke"
    $startedAt = Get-Date
    $launcher = Start-Process -FilePath $OutputExe -PassThru
    $mainWindow = $null
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(20)
        while ([DateTime]::UtcNow -lt $deadline) {
            if ($launcher.HasExited) {
                throw "Packaged executable exited before its main window appeared (exit $($launcher.ExitCode))."
            }

            $candidateProcesses = @(Get-Process -Name $launcher.ProcessName -ErrorAction SilentlyContinue |
                Where-Object {
                    try {
                        $_.StartTime -ge $startedAt.AddSeconds(-1)
                    }
                    catch {
                        $false
                    }
                })
            $windows = @(
                foreach ($candidate in $candidateProcesses) {
                    [GreReleaseWindowInspector]::GetWindows($candidate.Id)
                }
            )
            $consoleWindow = $windows |
                Where-Object { $_.WindowClass -eq "ConsoleWindowClass" } |
                Select-Object -First 1
            if ($null -ne $consoleWindow) {
                throw "Packaged executable created an unexpected console window."
            }
            $mainWindow = $windows |
                Where-Object {
                    $_.Visible -and $_.MainWindowTitle -eq $ExpectedTitle
                } |
                Select-Object -First 1
            if ($null -ne $mainWindow) {
                break
            }
            Start-Sleep -Milliseconds 250
        }
        if ($null -eq $mainWindow) {
            throw "Main window '$ExpectedTitle' did not appear within 20 seconds."
        }

        $observedTitle = $mainWindow.MainWindowTitle
        if (-not [GreReleaseWindowInspector]::RequestNormalClose($mainWindow.Handle)) {
            throw "The packaged main window could not be closed normally."
        }
        if (-not $launcher.WaitForExit(10000)) {
            throw "The packaged process did not exit within 10 seconds after a normal window close."
        }
        if ($launcher.ExitCode -ne 0) {
            throw "The packaged process exited with code $($launcher.ExitCode) after smoke close."
        }
        Write-Host (
            "native_smoke title='{0}' profile='{1}' no_console=true subsystem=windows_gui exit=0" -f
            $observedTitle,
            $SmokeProfile
        )
    }
    finally {
        if (-not $launcher.HasExited) {
            if ($null -ne $mainWindow) {
                $null = [GreReleaseWindowInspector]::RequestNormalClose($mainWindow.Handle)
                $null = $launcher.WaitForExit(3000)
            }
            if (-not $launcher.HasExited) {
                Stop-Process -Id $launcher.Id -Force -ErrorAction SilentlyContinue
            }
        }
        $remainingProcesses = @(Get-Process -Name $launcher.ProcessName -ErrorAction SilentlyContinue |
            Where-Object {
                try {
                    $_.StartTime -ge $startedAt.AddSeconds(-1)
                }
                catch {
                    $false
                }
            })
        foreach ($remaining in $remainingProcesses) {
            if (-not $remaining.HasExited) {
                Stop-Process -Id $remaining.Id -Force -ErrorAction SilentlyContinue
            }
        }
        $launcher.Dispose()
    }

    $releaseFile = Get-Item -LiteralPath $OutputExe
    $sha256 = (Get-FileHash -LiteralPath $OutputExe -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host (
        "release_summary path='{0}' sha256={1} size_bytes={2}" -f
        $OutputExe,
        $sha256,
        $releaseFile.Length
    )
}
finally {
    Pop-Location
}

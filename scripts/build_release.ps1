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
            if (wantedProcessId <= 0 || processId == wantedProcessId)
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

function Get-ProcessTreeIds {
    param([Parameter(Mandatory = $true)][int]$RootProcessId)

    $probeOutput = @(& $Python $ReleaseProbe "process-tree" "--pid" $RootProcessId.ToString())
    if ($LASTEXITCODE -ne 0) {
        throw "Native process-tree probe failed with exit code $LASTEXITCODE."
    }
    $line = $probeOutput |
        Where-Object { $_ -match '^process_tree root=\d+ pids=\d+(?:,\d+)*$' } |
        Select-Object -Last 1
    if ($null -eq $line) {
        throw "Native process-tree probe returned no parseable result."
    }
    $match = [regex]::Match(
        [string]$line,
        '^process_tree root=(?<root>\d+) pids=(?<pids>\d+(?:,\d+)*)$'
    )
    if ([int]$match.Groups['root'].Value -ne $RootProcessId) {
        throw "Native process-tree probe returned a different root process."
    }
    Write-Host $line
    return @(
        $match.Groups['pids'].Value.Split(',') |
            ForEach-Object { [int]$_ } |
            Sort-Object -Unique
    )
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
$ReleaseProbe = Join-Path $RepoRoot "scripts\windows_release_probe.py"
$LauncherSource = Join-Path $RepoRoot "scripts\unicode_launcher.py"
$InnerRuntime = Join-Path $RepoRoot "build\release\GRE3000OfflineRuntime.exe"
$LauncherBuild = Join-Path $RepoRoot "build\launcher"
$LauncherExe = Join-Path $LauncherBuild "GRELauncher.exe"
$OutputExe = Join-Path $RepoRoot "outputs\GRE 3000 词离线版.exe"
$Instructions = Join-Path $RepoRoot "outputs\使用说明.txt"
$SmokeProfile = Join-Path $RepoRoot "build\smoke-profile"
$ExpectedTitle = "GRE 3000 词离线版"
$Amd64Machine = "0x8664"
$WindowsGuiSubsystem = "2"

foreach ($requiredFile in @(
    $Python,
    $Deploy,
    $Spec,
    $IconSvg,
    $Instructions,
    $ReleaseProbe,
    $LauncherSource
)) {
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
# Force UTF-8 so every reviewed setting is parsed consistently on GBK Windows.
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

    if (Test-Path -LiteralPath $InnerRuntime) {
        Remove-Item -LiteralPath $InnerRuntime -Force
    }
    if (Test-Path -LiteralPath $OutputExe) {
        Remove-Item -LiteralPath $OutputExe -Force
    }
    $specEncoding = [System.Text.UTF8Encoding]::new($false)
    $specSnapshot = [System.IO.File]::ReadAllText($Spec, $specEncoding)
    try {
        Invoke-External -Label "ASCII Qt runtime onefile build" -FilePath $Deploy -ArgumentList @(
            "-c", $Spec, "--extra-modules=Sql", "-f", "-v"
        )
    }
    finally {
        # PySide6 6.11.1 rewrites discovered modules and python_path in-place.
        # Preserve the reviewed, portable release configuration in source control.
        [System.IO.File]::WriteAllText($Spec, $specSnapshot, $specEncoding)
    }
    if (-not (Test-Path -LiteralPath $InnerRuntime -PathType Leaf)) {
        throw "pyside6-deploy returned without the expected executable: $InnerRuntime"
    }

    if (-not (Test-Path -LiteralPath $AuditHtml -PathType Leaf)) {
        throw "Strict importer did not generate the audit HTML: $AuditHtml"
    }

    Invoke-External -Label "ASCII Qt runtime x64 GUI verification" -FilePath $Python -ArgumentList @(
        $ReleaseProbe,
        "pe",
        "--path", $InnerRuntime,
        "--expected-machine", $Amd64Machine,
        "--expected-subsystem", $WindowsGuiSubsystem
    )

    Remove-WorkspaceDirectory -Path $LauncherBuild -AllowedRoot (Join-Path $RepoRoot "build")
    New-Item -ItemType Directory -Force -Path $LauncherBuild | Out-Null
    $embeddedRuntime = "$InnerRuntime=runtime/GRE3000OfflineRuntime.exe"
    Invoke-External -Label "Unicode-safe stdlib launcher onefile build" -FilePath $Python -ArgumentList @(
        "-m", "nuitka",
        "--onefile",
        "--windows-console-mode=disable",
        "--nofollow-import-to=PySide6",
        "--windows-icon-from-ico=$IconIco",
        "--include-data-files=$embeddedRuntime",
        "--msvc=latest",
        "--assume-yes-for-downloads",
        "--output-dir=$LauncherBuild",
        "--output-filename=GRELauncher.exe",
        $LauncherSource
    )
    if (-not (Test-Path -LiteralPath $LauncherExe -PathType Leaf)) {
        throw "Nuitka returned without the expected launcher: $LauncherExe"
    }
    Copy-Item -LiteralPath $LauncherExe -Destination $OutputExe -Force

    Invoke-External -Label "final Unicode launcher x64 GUI verification" -FilePath $Python -ArgumentList @(
        $ReleaseProbe,
        "pe",
        "--path", $OutputExe,
        "--expected-machine", $Amd64Machine,
        "--expected-subsystem", $WindowsGuiSubsystem
    )

    Remove-WorkspaceDirectory -Path $SmokeProfile -AllowedRoot (Join-Path $RepoRoot "build")
    New-Item -ItemType Directory -Force -Path $SmokeProfile | Out-Null
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    Remove-Item Env:GRE_WORDS_DB -ErrorAction SilentlyContinue
    $env:GRE_APP_DATA_ROOT = $SmokeProfile

    Write-Host "==> native packaged executable smoke"
    $startedAt = Get-Date
    $launcher = Start-Process -FilePath $OutputExe -PassThru
    $mainWindow = $null
    $chainProcessIds = @([int]$launcher.Id)
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(20)
        while ([DateTime]::UtcNow -lt $deadline) {
            if ($launcher.HasExited) {
                throw "Packaged executable exited before its main window appeared (exit $($launcher.ExitCode))."
            }

            foreach ($window in @([GreReleaseWindowInspector]::GetWindows(0))) {
                if (-not $window.Visible -or $window.MainWindowTitle -ne $ExpectedTitle) {
                    continue
                }
                try {
                    $owner = Get-Process -Id $window.ProcessId -ErrorAction Stop
                    if ($owner.StartTime -ge $startedAt.AddSeconds(-1)) {
                        $mainWindow = $window
                        break
                    }
                }
                catch {
                    continue
                }
            }
            if ($null -ne $mainWindow) {
                break
            }
            Start-Sleep -Milliseconds 250
        }
        if ($null -eq $mainWindow) {
            throw "Main window '$ExpectedTitle' did not appear within 20 seconds."
        }

        $observedTitle = $mainWindow.MainWindowTitle
        $guiProcessId = [int]$mainWindow.ProcessId
        $launcherProcessId = [int]$launcher.Id
        $chainProcessIds = @(Get-ProcessTreeIds -RootProcessId $launcherProcessId)
        if ($guiProcessId -notin $chainProcessIds) {
            throw "The titled GUI process $guiProcessId is not a descendant of launcher $launcherProcessId."
        }
        Invoke-External -Label "packaged GUI child x64 verification" -FilePath $Python -ArgumentList @(
            $ReleaseProbe,
            "process-pe",
            "--pid", $guiProcessId.ToString(),
            "--expected-machine", $Amd64Machine,
            "--expected-subsystem", $WindowsGuiSubsystem
        )
        Invoke-External -Label "packaged GUI child no-console verification" -FilePath $Python -ArgumentList @(
            $ReleaseProbe,
            "console",
            "--pid", $guiProcessId.ToString()
        )
        Invoke-External -Label "Unicode launcher no-console verification" -FilePath $Python -ArgumentList @(
            $ReleaseProbe,
            "console",
            "--pid", $launcherProcessId.ToString()
        )
        $closeArguments = @(
            $ReleaseProbe,
            "close-wait",
            "--window-handle", ([Int64]$mainWindow.Handle).ToString()
        )
        foreach ($processId in $chainProcessIds) {
            $closeArguments += @("--pid", ([int]$processId).ToString())
        }
        $closeArguments += @("--timeout", "15")
        Invoke-External -Label "complete packaged process chain normal close" -FilePath $Python -ArgumentList $closeArguments
        $launcher.Refresh()
        Write-Host (
            "native_smoke title='{0}' profile='{1}' gui_pid={2} launcher_pid={3} chain_pids={4} machine=x64 no_console=true subsystem=windows_gui chain_exited=true exit=0" -f
            $observedTitle,
            $SmokeProfile,
            $guiProcessId,
            $launcherProcessId,
            ($chainProcessIds -join ",")
        )
    }
    finally {
        if ($null -ne $mainWindow) {
            $null = [GreReleaseWindowInspector]::RequestNormalClose($mainWindow.Handle)
        }
        try {
            $latestTreeIds = @(Get-ProcessTreeIds -RootProcessId ([int]$launcher.Id))
            $chainProcessIds = @($chainProcessIds + $latestTreeIds | Sort-Object -Unique)
        }
        catch {
            # Preserve the original smoke result; cleanup uses the last safe snapshot.
        }
        Start-Sleep -Milliseconds 250
        foreach ($processId in $chainProcessIds) {
            $remaining = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($null -ne $remaining -and -not $remaining.HasExited) {
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
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

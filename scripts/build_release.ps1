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

function Assert-ReleaseOutputAllowlist {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$ExpectedNames,
        [switch]$RequireAll
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Release output directory not found: $Path"
    }
    $entries = @(Get-ChildItem -LiteralPath $Path -Force)
    $unexpected = @(
        $entries | Where-Object { $_.Name -notin $ExpectedNames }
    )
    if ($unexpected.Count -ne 0) {
        $names = ($unexpected | ForEach-Object { $_.Name }) -join ", "
        throw "Unexpected release output entries: $names"
    }
    if ($RequireAll) {
        $missing = @(
            $ExpectedNames | Where-Object {
                -not (Test-Path -LiteralPath (Join-Path $Path $_) -PathType Leaf)
            }
        )
        if ($missing.Count -ne 0 -or $entries.Count -ne $ExpectedNames.Count) {
            $names = $missing -join ", "
            throw "Release output set is incomplete: $names"
        }
    }
}

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Deploy = Join-Path $RepoRoot ".venv\Scripts\pyside6-deploy.exe"
$Spec = Join-Path $RepoRoot "pysidedeploy.spec"
$Database = Join-Path $RepoRoot "build\generated\words.db"
$AuditJson = Join-Path $RepoRoot "build\audit\report.json"
$StagedAuditHtml = Join-Path $RepoRoot "build\audit\词库导入审计报告.html"
$IconSvg = Join-Path $RepoRoot "resources\app.svg"
$IconIco = Join-Path $RepoRoot "resources\app.ico"
$InstructionsSource = Join-Path $RepoRoot "resources\使用说明.txt"
$ReleaseProbe = Join-Path $RepoRoot "scripts\windows_release_probe.py"
$PublishReleaseSet = Join-Path $RepoRoot "scripts\publish_release_set.py"
$LauncherSource = Join-Path $RepoRoot "scripts\unicode_launcher.py"
$InnerRuntime = Join-Path $RepoRoot "build\release\GRE3000OfflineRuntime.exe"
$LauncherBuild = Join-Path $RepoRoot "build\launcher"
$LauncherExe = Join-Path $LauncherBuild "GRELauncher.exe"
$ReleaseCandidateDirectory = Join-Path $RepoRoot "build\release-candidate"
$ReleaseCandidate = Join-Path $ReleaseCandidateDirectory "GRE 3000 词离线版.exe"
$StagedInstructions = Join-Path $ReleaseCandidateDirectory "使用说明.txt"
$OutputsDirectory = Join-Path $RepoRoot "outputs"
$OutputExe = Join-Path $OutputsDirectory "GRE 3000 词离线版.exe"
$OutputAuditHtml = Join-Path $OutputsDirectory "词库导入审计报告.html"
$OutputInstructions = Join-Path $OutputsDirectory "使用说明.txt"
$ExpectedOutputNames = @(
    "GRE 3000 词离线版.exe",
    "使用说明.txt",
    "词库导入审计报告.html"
)
$SmokeProfile = Join-Path $RepoRoot "build\smoke-profile"
$ExpectedTitle = "GRE 3000 词离线版"
$Amd64Machine = "0x8664"
$WindowsGuiSubsystem = "2"

foreach ($requiredFile in @(
    $Python,
    $Deploy,
    $Spec,
    $IconSvg,
    $InstructionsSource,
    $ReleaseProbe,
    $PublishReleaseSet,
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
New-Item -ItemType Directory -Force -Path $OutputsDirectory | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "build\release") | Out-Null
Assert-ReleaseOutputAllowlist `
    -Path $OutputsDirectory `
    -ExpectedNames $ExpectedOutputNames
$env:TEMP = $ReleaseTemp
$env:TMP = $ReleaseTemp
$env:NUITKA_CACHE_DIR = $NuitkaCache
$env:QT_QPA_PLATFORM = "offscreen"
# PySide6 6.11.1 opens its INI spec with Python's default text encoding.
# Force UTF-8 so every reviewed setting is parsed consistently on GBK Windows.
$env:PYTHONUTF8 = "1"

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
        "--audit-html", $StagedAuditHtml,
        "--overrides", (Join-Path $RepoRoot "src\gre_vocab_app\importer\overrides.json"),
        "--strict"
    )

    Invoke-External -Label "database and audit verification" -FilePath $Python -ArgumentList @(
        (Join-Path $RepoRoot "scripts\verify_release_artifacts.py"),
        $Database,
        $AuditJson,
        "--expected-records", "3292",
        "--expected-reviewed", "5"
    )

    Invoke-External -Label "SVG to multi-size ICO generation" -FilePath $Python -ArgumentList @(
        (Join-Path $RepoRoot "scripts\generate_icon.py"),
        $IconSvg,
        $IconIco
    )

    if (Test-Path -LiteralPath $InnerRuntime) {
        Remove-Item -LiteralPath $InnerRuntime -Force
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

    if (-not (Test-Path -LiteralPath $StagedAuditHtml -PathType Leaf)) {
        throw "Strict importer did not generate the staged audit HTML: $StagedAuditHtml"
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
    Remove-WorkspaceDirectory -Path $ReleaseCandidateDirectory -AllowedRoot (Join-Path $RepoRoot "build")
    New-Item -ItemType Directory -Force -Path $ReleaseCandidateDirectory | Out-Null
    Copy-Item -LiteralPath $LauncherExe -Destination $ReleaseCandidate
    Copy-Item -LiteralPath $InstructionsSource -Destination $StagedInstructions

    Invoke-External -Label "final Unicode candidate x64 GUI verification" -FilePath $Python -ArgumentList @(
        $ReleaseProbe,
        "pe",
        "--path", $ReleaseCandidate,
        "--expected-machine", $Amd64Machine,
        "--expected-subsystem", $WindowsGuiSubsystem
    )

    Remove-WorkspaceDirectory -Path $SmokeProfile -AllowedRoot (Join-Path $RepoRoot "build")
    New-Item -ItemType Directory -Force -Path $SmokeProfile | Out-Null
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    Remove-Item Env:GRE_WORDS_DB -ErrorAction SilentlyContinue
    $env:GRE_APP_DATA_ROOT = $SmokeProfile

    Invoke-External -Label "Job-supervised native packaged executable smoke" -FilePath $Python -ArgumentList @(
        $ReleaseProbe,
        "native-smoke",
        "--path", $ReleaseCandidate,
        "--title", $ExpectedTitle,
        "--timeout", "35",
        "--expected-machine", $Amd64Machine,
        "--expected-subsystem", $WindowsGuiSubsystem
    )

    Invoke-External -Label "transactional release-set publication" -FilePath $Python -ArgumentList @(
        $PublishReleaseSet,
        "--artifact", $ReleaseCandidate, $OutputExe,
        "--artifact", $StagedAuditHtml, $OutputAuditHtml,
        "--artifact", $StagedInstructions, $OutputInstructions
    )

    Assert-ReleaseOutputAllowlist `
        -Path $OutputsDirectory `
        -ExpectedNames $ExpectedOutputNames `
        -RequireAll

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
    if (Test-Path -LiteralPath $ReleaseCandidate) {
        Remove-Item -LiteralPath $ReleaseCandidate -Force
    }
    if (Test-Path -LiteralPath $StagedInstructions) {
        Remove-Item -LiteralPath $StagedInstructions -Force
    }
    Pop-Location
}

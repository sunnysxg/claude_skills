[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$failureCount = 0

function Write-Check {
    param(
        [Parameter(Mandatory)][ValidateSet("OK", "WARN", "FAIL")][string]$State,
        [Parameter(Mandatory)][string]$Message
    )
    Write-Host ("{0,-4} {1}" -f $State, $Message)
    if ($State -eq "FAIL") {
        $script:failureCount += 1
    }
}

function Find-CommandPath {
    param([Parameter(Mandatory)][string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command -Name $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) {
            return $command.Source
        }
    }
    return $null
}

function Find-BrowserPath {
    $candidates = @()
    if ($env:LOCALAPPDATA) {
        $candidates += Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe"
        $candidates += Join-Path $env:LOCALAPPDATA "Microsoft\Edge\Application\msedge.exe"
        $candidates += Join-Path $env:LOCALAPPDATA "BraveSoftware\Brave-Browser\Application\brave.exe"
    }
    if ($env:ProgramFiles) {
        $candidates += Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"
        $candidates += Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"
        $candidates += Join-Path $env:ProgramFiles "BraveSoftware\Brave-Browser\Application\brave.exe"
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if ($programFilesX86) {
        $candidates += Join-Path $programFilesX86 "Google\Chrome\Application\chrome.exe"
        $candidates += Join-Path $programFilesX86 "Microsoft\Edge\Application\msedge.exe"
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

foreach ($relativePath in @("references\fonts.css", "references\mmd-config.json")) {
    $path = Join-Path $skillDir $relativePath
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        Write-Check OK $path
    } else {
        Write-Check FAIL "missing file: $path"
    }
}

$renderer = $null
if ($env:MMD_EXPLAIN_MMDC) {
    if (Test-Path -LiteralPath $env:MMD_EXPLAIN_MMDC -PathType Leaf) {
        $renderer = [System.IO.Path]::GetFullPath($env:MMD_EXPLAIN_MMDC)
    } else {
        $renderer = Find-CommandPath @($env:MMD_EXPLAIN_MMDC)
    }
    if (-not $renderer) {
        Write-Check FAIL "MMD_EXPLAIN_MMDC is not a file or command: $env:MMD_EXPLAIN_MMDC"
    }
} else {
    $renderer = Find-CommandPath @("mmdc.cmd", "mmdc")
    if (-not $renderer) {
        $npx = Find-CommandPath @("npx.cmd", "npx")
        if ($npx) {
            $renderer = "$npx -y @mermaid-js/mermaid-cli"
        }
    }
}
if ($renderer) {
    Write-Check OK "renderer: $renderer"
} elseif (-not $env:MMD_EXPLAIN_MMDC) {
    Write-Check FAIL "no renderer found (MMD_EXPLAIN_MMDC, mmdc, or npx)"
}

$browser = $null
if ($env:PUPPETEER_EXECUTABLE_PATH) {
    if (Test-Path -LiteralPath $env:PUPPETEER_EXECUTABLE_PATH -PathType Leaf) {
        $browser = [System.IO.Path]::GetFullPath($env:PUPPETEER_EXECUTABLE_PATH)
        Write-Check OK "browser override: $browser"
    } else {
        Write-Check FAIL "PUPPETEER_EXECUTABLE_PATH does not exist: $env:PUPPETEER_EXECUTABLE_PATH"
    }
} else {
    $browser = Find-BrowserPath
    if ($browser) {
        Write-Check OK "system browser: $browser"
    } else {
        Write-Check WARN "no system browser found; a Puppeteer-managed browser may still work"
    }
}

try {
    Add-Type -AssemblyName System.Drawing
    $fontCollection = New-Object System.Drawing.Text.InstalledFontCollection
    $fontNames = @($fontCollection.Families | ForEach-Object { $_.Name })
    $fontCollection.Dispose()

    $cjkFonts = @("Noto Sans CJK SC", "Noto Sans SC", "Microsoft YaHei", "Microsoft YaHei UI")
    $emojiFonts = @("Noto Color Emoji", "Segoe UI Emoji")
    $cjkMatch = $cjkFonts | Where-Object { $fontNames -contains $_ } | Select-Object -First 1
    $emojiMatch = $emojiFonts | Where-Object { $fontNames -contains $_ } | Select-Object -First 1

    if ($cjkMatch) {
        Write-Check OK "CJK font: $cjkMatch"
    } else {
        Write-Check WARN "no preferred CJK font found"
    }
    if ($emojiMatch) {
        Write-Check OK "emoji font: $emojiMatch"
    } else {
        Write-Check WARN "no preferred emoji font found"
    }
} catch {
    Write-Check WARN "font enumeration unavailable: $($_.Exception.Message)"
}

if ($failureCount -gt 0) {
    exit 1
}
Write-Check OK "mmd-explain Windows environment is ready"

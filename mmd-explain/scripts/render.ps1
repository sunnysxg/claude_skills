[CmdletBinding()]
param(
    [Parameter(Mandatory)][Alias("i")][string]$InputPath,
    [Alias("o")][string]$OutputPath,
    [Alias("w")][ValidateRange(1, 20000)][int]$Width = 2400,
    [ValidateRange(1, 20000)][int]$Height = 2400,
    [Alias("s")][ValidateRange(0.1, 10.0)][double]$Scale = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

$inputFile = (Resolve-Path -LiteralPath $InputPath -ErrorAction Stop).Path
if (-not $OutputPath) {
    $outputFile = [System.IO.Path]::ChangeExtension($inputFile, ".png")
} elseif ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $outputFile = [System.IO.Path]::GetFullPath($OutputPath)
} else {
    $outputFile = [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $OutputPath))
}

$outputDirectory = Split-Path -Parent $outputFile
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$cssFile = Join-Path $skillDir "references\fonts.css"
$configFile = Join-Path $skillDir "references\mmd-config.json"
foreach ($required in @($cssFile, $configFile)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing renderer configuration: $required"
    }
}

$rendererKind = $null
$rendererCommand = $null
if ($env:MMD_EXPLAIN_MMDC) {
    if (Test-Path -LiteralPath $env:MMD_EXPLAIN_MMDC -PathType Leaf) {
        $rendererCommand = [System.IO.Path]::GetFullPath($env:MMD_EXPLAIN_MMDC)
    } else {
        $rendererCommand = Find-CommandPath @($env:MMD_EXPLAIN_MMDC)
    }
    if (-not $rendererCommand) {
        throw "MMD_EXPLAIN_MMDC is not a file or command: $env:MMD_EXPLAIN_MMDC"
    }
    $rendererKind = "mmdc"
} else {
    $rendererCommand = Find-CommandPath @("mmdc.cmd", "mmdc")
    if ($rendererCommand) {
        $rendererKind = "mmdc"
    } else {
        $rendererCommand = Find-CommandPath @("npx.cmd", "npx")
        if ($rendererCommand) {
            $rendererKind = "npx"
        }
    }
}
if (-not $rendererCommand) {
    throw "No renderer found. Run doctor.ps1 and install mmdc or npx."
}

if ($env:PUPPETEER_EXECUTABLE_PATH) {
    if (-not (Test-Path -LiteralPath $env:PUPPETEER_EXECUTABLE_PATH -PathType Leaf)) {
        throw "PUPPETEER_EXECUTABLE_PATH does not exist: $env:PUPPETEER_EXECUTABLE_PATH"
    }
} else {
    $browserPath = Find-BrowserPath
    if ($browserPath) {
        $env:PUPPETEER_EXECUTABLE_PATH = $browserPath
    }
}

$scaleText = $Scale.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$renderArgs = @(
    "-i", $inputFile,
    "-o", $outputFile,
    "-w", [string]$Width,
    "-H", [string]$Height,
    "-s", $scaleText,
    "-c", $configFile,
    "-C", $cssFile,
    "-b", "white",
    "-q"
)

if ($rendererKind -eq "npx") {
    & $rendererCommand "-y" "@mermaid-js/mermaid-cli" @renderArgs
} else {
    & $rendererCommand @renderArgs
}
if ($LASTEXITCODE -ne 0) {
    throw "Mermaid renderer failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $outputFile -PathType Leaf)) {
    throw "Renderer exited successfully but did not create: $outputFile"
}
Write-Output $outputFile

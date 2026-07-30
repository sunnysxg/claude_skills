[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$syncScript = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "sync_skills.ps1"))
$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$tempRoot = Join-Path $tempBase ("claude-skills-sync-rules-" + [System.Guid]::NewGuid().ToString("N"))
$utf8 = New-Object System.Text.UTF8Encoding($false)
$testCount = 0

function Write-Utf8 {
    param(
        [Parameter(Mandatory)][string]$PathValue,
        [AllowEmptyString()][string]$Content
    )

    $parent = Split-Path -Parent $PathValue
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($PathValue, $Content, $script:utf8)
}

function Assert-True {
    param(
        [Parameter(Mandatory)][bool]$Condition,
        [Parameter(Mandatory)][string]$Message
    )

    if (-not $Condition) {
        throw "ASSERTION FAILED: $Message"
    }
    $script:testCount += 1
}

function Invoke-SyncRules {
    param(
        [ValidateSet("Sync", "Doctor")][string]$Command,
        [switch]$DryRun
    )

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $syncScript,
        "-Command", $Command,
        "-Scope", "Rules",
        "-ManifestPath", $manifestPath,
        "-LocalConfigPath", $localConfigPath
    )
    if ($DryRun) {
        $arguments += "-DryRun"
    }
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & powershell @arguments 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

try {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    $sourceRoot = Join-Path $tempRoot "source"
    $commonPath = Join-Path $sourceRoot "global\COMMON.md"
    $cursorPath = Join-Path $tempRoot "cursor\rules\claude-skills-common.mdc"
    $codexPath = Join-Path $tempRoot "codex\AGENTS.md"
    $manifestPath = Join-Path $tempRoot "manifest.json"
    $localConfigPath = Join-Path $tempRoot "local.json"

    $cjkRule = "- " + [char]0x89C4 + [char]0x5219 + [char]0x4E00
    $newCjkRule = "- " + [char]0x65B0 + [char]0x89C4 + [char]0x5219
    Write-Utf8 $commonPath "# Common`n`n$cjkRule`n- Rule two`n"
    $manifest = [ordered]@{
        version = 1
        supported_platforms = @("windows", "linux")
        source_root = $sourceRoot
        native_clients = [ordered]@{}
        clients = [ordered]@{
            cursor = [ordered]@{
                root = (Join-Path $tempRoot "cursor\skills")
                enabled_by_default = $true
                windows_link_type = "junction"
                unix_link_type = "symlink"
            }
            codex = [ordered]@{
                root = (Join-Path $tempRoot "codex\skills")
                enabled_by_default = $true
                windows_link_type = "junction"
                unix_link_type = "symlink"
            }
        }
        managed_rules = @(
            [ordered]@{
                name = "global-common"
                source = "global/COMMON.md"
                platforms = @("windows", "linux")
                targets = @(
                    [ordered]@{
                        client = "cursor"
                        path = $cursorPath
                        mode = "cursor_mdc"
                    },
                    [ordered]@{
                        client = "codex"
                        path = $codexPath
                        mode = "managed_block"
                        legacy_exact_content = "@skills/global/AGENTS.md"
                    }
                )
            }
        )
        skills = @()
        aliases = @()
    }
    Write-Utf8 $manifestPath ($manifest | ConvertTo-Json -Depth 10)
    Write-Utf8 $localConfigPath (@{
        machine_id = "test-host"
        clients = @{
            cursor = @{ enabled = $true }
            codex = @{ enabled = $true }
        }
        skills = @{}
    } | ConvertTo-Json -Depth 6)

    $result = Invoke-SyncRules -Command Sync -DryRun
    Assert-True ($result.ExitCode -eq 0) "dry-run should succeed: $($result.Output)"
    Assert-True (-not (Test-Path -LiteralPath $cursorPath)) "dry-run must not create Cursor rule"
    Assert-True (-not (Test-Path -LiteralPath $codexPath)) "dry-run must not create Codex rule"

    $result = Invoke-SyncRules -Command Doctor
    Assert-True ($result.ExitCode -eq 1) "Doctor should fail while rule targets are missing"

    $result = Invoke-SyncRules -Command Sync
    Assert-True ($result.ExitCode -eq 0) "initial Sync should create both rule targets"
    $cursorContent = [System.IO.File]::ReadAllText($cursorPath)
    $codexContent = [System.IO.File]::ReadAllText($codexPath)
    Assert-True ($cursorContent.StartsWith("---`n")) "Cursor rule must start with MDC frontmatter"
    Assert-True ($cursorContent.Contains("alwaysApply: true")) "Cursor rule must always apply"
    Assert-True ($cursorContent.Contains("<!-- BEGIN claude_skills:global-common -->")) "Cursor rule must contain managed markers"
    Assert-True ($codexContent.Contains($cjkRule)) "Codex block must contain COMMON body"

    $cursorHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $cursorPath).Hash
    $codexHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $codexPath).Hash
    $cursorTime = (Get-Item -LiteralPath $cursorPath).LastWriteTimeUtc
    $codexTime = (Get-Item -LiteralPath $codexPath).LastWriteTimeUtc
    Start-Sleep -Milliseconds 1100
    $result = Invoke-SyncRules -Command Sync
    Assert-True ($result.ExitCode -eq 0) "second Sync should succeed"
    Assert-True ((Get-FileHash -Algorithm SHA256 -LiteralPath $cursorPath).Hash -eq $cursorHash) "second Sync must not change Cursor content"
    Assert-True ((Get-FileHash -Algorithm SHA256 -LiteralPath $codexPath).Hash -eq $codexHash) "second Sync must not change Codex content"
    Assert-True ((Get-Item -LiteralPath $cursorPath).LastWriteTimeUtc -eq $cursorTime) "second Sync must not rewrite Cursor file"
    Assert-True ((Get-Item -LiteralPath $codexPath).LastWriteTimeUtc -eq $codexTime) "second Sync must not rewrite Codex file"

    $begin = "<!-- BEGIN claude_skills:global-common -->"
    $end = "<!-- END claude_skills:global-common -->"
    $blockStart = $codexContent.IndexOf($begin, [System.StringComparison]::Ordinal)
    $blockEnd = $codexContent.IndexOf($end, [System.StringComparison]::Ordinal) + $end.Length
    $block = $codexContent.Substring($blockStart, $blockEnd - $blockStart)
    $prefix = "local prefix with trailing spaces  `r`n`r`n"
    $suffix = "`r`n`r`nlocal suffix with trailing spaces  "
    Write-Utf8 $codexPath ($prefix + $block.Replace("`n", "`r`n") + $suffix)
    Write-Utf8 $commonPath "# Common v2`n`n$newCjkRule`n"

    $result = Invoke-SyncRules -Command Doctor
    Assert-True ($result.ExitCode -eq 1) "Doctor should detect stale generated rules"
    $result = Invoke-SyncRules -Command Sync
    Assert-True ($result.ExitCode -eq 0) "Sync should update stale generated rules: $($result.Output)"
    $updatedCodex = [System.IO.File]::ReadAllText($codexPath)
    Assert-True ($updatedCodex.StartsWith($prefix)) "Codex prefix outside managed block must be preserved"
    Assert-True ($updatedCodex.EndsWith($suffix)) "Codex suffix outside managed block must be preserved"
    Assert-True ($updatedCodex.Contains($newCjkRule)) "Codex managed body must update from COMMON"

    Write-Utf8 $codexPath "@skills/global/AGENTS.md`r`n"
    $result = Invoke-SyncRules -Command Sync
    Assert-True ($result.ExitCode -eq 0) "exact legacy Codex bootstrap should migrate"
    $migratedCodex = [System.IO.File]::ReadAllText($codexPath)
    Assert-True (-not $migratedCodex.Contains("@skills/global/AGENTS.md")) "legacy bootstrap must be removed"
    Assert-True ($migratedCodex.Contains($newCjkRule)) "migrated Codex file must contain COMMON"

    Write-Utf8 $codexPath "$begin`nmissing end marker`n"
    $malformedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $codexPath).Hash
    $result = Invoke-SyncRules -Command Sync
    Assert-True ($result.ExitCode -eq 1) "malformed markers must block Sync"
    Assert-True ((Get-FileHash -Algorithm SHA256 -LiteralPath $codexPath).Hash -eq $malformedHash) "malformed target must not be overwritten"

    Write-Utf8 $codexPath "@skills/global/AGENTS.md`n"
    Write-Utf8 $cursorPath "unmanaged user file`n"
    $unmanagedCursorHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $cursorPath).Hash
    $blockedCodexHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $codexPath).Hash
    $result = Invoke-SyncRules -Command Sync
    Assert-True ($result.ExitCode -eq 1) "unmanaged dedicated Cursor file must be treated as a conflict"
    Assert-True ((Get-FileHash -Algorithm SHA256 -LiteralPath $cursorPath).Hash -eq $unmanagedCursorHash) "unmanaged Cursor file must not be overwritten"
    Assert-True ((Get-FileHash -Algorithm SHA256 -LiteralPath $codexPath).Hash -eq $blockedCodexHash) "a rule conflict must prevent partial writes to other targets"

    Write-Host "PASS: $testCount assertions"
} finally {
    $resolvedTempRoot = [System.IO.Path]::GetFullPath($tempRoot)
    if ($resolvedTempRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase) -and
        [System.IO.Path]::GetFileName($resolvedTempRoot).StartsWith("claude-skills-sync-rules-")) {
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

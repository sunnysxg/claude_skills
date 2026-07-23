[CmdletBinding()]
param(
    [ValidateSet("Sync", "Doctor")]
    [string]$Command = "Sync",

    [string[]]$Client,

    [switch]$DryRun,

    [switch]$RepairLinks,

    [string]$ManifestPath,

    [string]$LocalConfigPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $ManifestPath) {
    $ManifestPath = Join-Path $repoRoot "skills.manifest.json"
}
if (-not $LocalConfigPath) {
    $LocalConfigPath = Join-Path $repoRoot "sync.local.json"
}

function Expand-PortablePath {
    param(
        [Parameter(Mandatory)]
        [string]$PathValue,
        [Parameter(Mandatory)]
        [string]$BasePath
    )

    $userProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    if ($PathValue -eq "~") {
        return [System.IO.Path]::GetFullPath($userProfile)
    }
    if ($PathValue.StartsWith("~/") -or $PathValue.StartsWith("~\")) {
        $suffix = $PathValue.Substring(2).Replace("/", [System.IO.Path]::DirectorySeparatorChar)
        return [System.IO.Path]::GetFullPath((Join-Path $userProfile $suffix))
    }
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $PathValue))
}

function Normalize-MachineId {
    param([string]$Value)

    $normalized = $Value.Trim().ToLowerInvariant() -replace "[^a-z0-9._-]", "-"
    $normalized = $normalized.Trim([char[]]@("-", ".", "_"))
    if (-not $normalized) {
        throw "machine_id is empty after normalization"
    }
    if ($normalized.Length -gt 64) {
        throw "machine_id must be 64 characters or fewer"
    }
    return $normalized
}

function Get-ObjectProperty {
    param(
        [Parameter(Mandatory)]
        [object]$Object,
        [Parameter(Mandatory)]
        [string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Get-NormalizedPath {
    param([Parameter(Mandatory)][string]$PathValue)

    return [System.IO.Path]::GetFullPath($PathValue).TrimEnd([char[]]@(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ))
}

function Get-LinkTarget {
    param([Parameter(Mandatory)][System.IO.FileSystemInfo]$Item)

    if (-not ($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        return $null
    }
    $rawTarget = @($Item.Target) | Select-Object -First 1
    if (-not $rawTarget) {
        return $null
    }
    if (-not [System.IO.Path]::IsPathRooted($rawTarget)) {
        $rawTarget = Join-Path (Split-Path -Parent $Item.FullName) $rawTarget
    }
    return Get-NormalizedPath $rawTarget
}

function Test-SamePath {
    param(
        [Parameter(Mandatory)][string]$Left,
        [Parameter(Mandatory)][string]$Right
    )

    return [string]::Equals(
        (Get-NormalizedPath $Left),
        (Get-NormalizedPath $Right),
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Assert-SafeClientRoot {
    param(
        [Parameter(Mandatory)][string]$ClientRoot,
        [Parameter(Mandatory)][string]$SourceRoot
    )

    $normalizedRoot = Get-NormalizedPath $ClientRoot
    $volumeRoot = Get-NormalizedPath ([System.IO.Path]::GetPathRoot($normalizedRoot))
    if (Test-SamePath $normalizedRoot $volumeRoot) {
        throw "Refusing to use a filesystem root as a client root: $normalizedRoot"
    }

    $userProfile = Get-NormalizedPath ([Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile))
    if (Test-SamePath $normalizedRoot $userProfile) {
        throw "Refusing to use the user profile itself as a client root: $normalizedRoot"
    }

    $normalizedSource = Get-NormalizedPath $SourceRoot
    $sourcePrefix = $normalizedSource + [System.IO.Path]::DirectorySeparatorChar
    if ((Test-SamePath $normalizedRoot $normalizedSource) -or
        $normalizedRoot.StartsWith($sourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to create client links inside the source repository: $normalizedRoot"
    }
}

function Remove-ExistingLink {
    param([Parameter(Mandatory)][string]$LinkPath)

    $item = Get-Item -LiteralPath $LinkPath -Force -ErrorAction Stop
    if (-not ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "Refusing to remove a non-link path: $LinkPath"
    }
    if ($item.PSIsContainer) {
        [System.IO.Directory]::Delete($item.FullName)
    } else {
        [System.IO.File]::Delete($item.FullName)
    }
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "Manifest not found: $ManifestPath"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.version -ne 1) {
    throw "Unsupported manifest version: $($manifest.version)"
}
if (@($manifest.supported_platforms) -notcontains "windows") {
    throw "Manifest does not declare Windows support"
}
$platformName = "windows"

$localConfig = $null
if (Test-Path -LiteralPath $LocalConfigPath -PathType Leaf) {
    $localConfig = Get-Content -LiteralPath $LocalConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

$machineIdSource = [Environment]::MachineName
if ($localConfig) {
    $configuredMachineId = Get-ObjectProperty $localConfig "machine_id"
    if ($configuredMachineId) {
        $machineIdSource = [string]$configuredMachineId
    }
}
$machineId = Normalize-MachineId $machineIdSource

function Test-EntryPlatform {
    param(
        [Parameter(Mandatory)]
        [object]$Entry
    )

    $platforms = @(Get-ObjectProperty $Entry "platforms")
    if ($platforms.Count -eq 0) {
        throw "Entry must declare at least one platform: $($Entry.name)"
    }
    foreach ($platform in $platforms) {
        if (@($manifest.supported_platforms) -notcontains [string]$platform) {
            throw "Entry declares an unsupported platform: $($Entry.name) -> $platform"
        }
    }
    return $platforms -contains $platformName
}

function Test-LocalSkillEnabled {
    param(
        [Parameter(Mandatory)]
        [string]$SkillName
    )

    if (-not $localConfig) {
        return $true
    }
    $localSkills = Get-ObjectProperty $localConfig "skills"
    if (-not $localSkills) {
        return $true
    }
    $override = Get-ObjectProperty $localSkills $SkillName
    if (-not $override) {
        return $true
    }
    $enabled = Get-ObjectProperty $override "enabled"
    if ($null -eq $enabled) {
        return $true
    }
    return [bool]$enabled
}

$clientNames = @($manifest.clients.PSObject.Properties.Name)
if ($Client -and $Client.Count -gt 0) {
    $selectedClients = @($Client | ForEach-Object { $_ -split "," } | Where-Object { $_ })
} else {
    $selectedClients = @()
    foreach ($clientName in $clientNames) {
        $definition = Get-ObjectProperty $manifest.clients $clientName
        $enabled = [bool]$definition.enabled_by_default
        if ($localConfig) {
            $localClients = Get-ObjectProperty $localConfig "clients"
            if ($localClients) {
                $override = Get-ObjectProperty $localClients $clientName
                if ($override) {
                    $overrideEnabled = Get-ObjectProperty $override "enabled"
                    if ($null -ne $overrideEnabled) {
                        $enabled = [bool]$overrideEnabled
                    }
                }
            }
        }
        if ($enabled) {
            $selectedClients += $clientName
        }
    }
}

if ($selectedClients.Count -eq 0) {
    throw "No clients are enabled or selected"
}

foreach ($clientName in $selectedClients) {
    if ($clientNames -notcontains $clientName) {
        throw "Client is not declared in the manifest: $clientName"
    }
}

$sourceRoot = Expand-PortablePath -PathValue ([string]$manifest.source_root) -BasePath $repoRoot
$declaredEntries = @()
$seenNames = @{}
$canonicalSkillNames = @{}

foreach ($skill in @($manifest.skills)) {
    $name = [string]$skill.name
    if ($name -notmatch "^[a-z0-9][a-z0-9-]{0,63}$") {
        throw "Invalid skill name: $name"
    }
    if ($seenNames.ContainsKey($name)) {
        throw "Duplicate skill or alias name: $name"
    }
    $seenNames[$name] = $true
    $canonicalSkillNames[$name] = $true

    $sourcePath = Expand-PortablePath -PathValue ([string]$skill.source) -BasePath $sourceRoot
    if (-not (Test-Path -LiteralPath (Join-Path $sourcePath "SKILL.md") -PathType Leaf)) {
        throw "Skill is missing SKILL.md: $name ($sourcePath)"
    }
    if ((Test-EntryPlatform $skill) -and (Test-LocalSkillEnabled $name)) {
        $declaredEntries += [PSCustomObject]@{
            Name = $name
            SourcePath = $sourcePath
            Targets = @($skill.targets)
            Kind = "skill"
        }
    }
}

foreach ($alias in @($manifest.aliases)) {
    $name = [string]$alias.name
    if ($name -notmatch "^[a-z0-9][a-z0-9-]{0,63}$") {
        throw "Invalid alias name: $name"
    }
    if ($seenNames.ContainsKey($name)) {
        throw "Duplicate skill or alias name: $name"
    }
    $seenNames[$name] = $true
    $canonicalName = [string](Get-ObjectProperty $alias "canonical")
    if (-not $canonicalName) {
        throw "Alias must declare canonical: $name"
    }
    if (-not $canonicalSkillNames.ContainsKey($canonicalName)) {
        throw "Alias canonical skill is not declared: $name -> $canonicalName"
    }

    $sourcePath = Expand-PortablePath -PathValue ([string]$alias.source) -BasePath $sourceRoot
    if (-not (Test-Path -LiteralPath (Join-Path $sourcePath "SKILL.md") -PathType Leaf)) {
        throw "Alias source is missing SKILL.md: $name ($sourcePath)"
    }
    if ((Test-EntryPlatform $alias) -and (Test-LocalSkillEnabled $canonicalName)) {
        $declaredEntries += [PSCustomObject]@{
            Name = $name
            SourcePath = $sourcePath
            Targets = @($alias.targets)
            Kind = "alias"
        }
    }
}

if ($localConfig) {
    $localSkills = Get-ObjectProperty $localConfig "skills"
    if ($localSkills) {
        foreach ($localSkillName in @($localSkills.PSObject.Properties.Name)) {
            if (-not $canonicalSkillNames.ContainsKey($localSkillName)) {
                throw "Local config references an undeclared skill: $localSkillName"
            }
        }
    }
}

$operations = @()
foreach ($clientName in $selectedClients) {
    $definition = Get-ObjectProperty $manifest.clients $clientName
    $rootValue = [string]$definition.root

    if ($localConfig) {
        $localClients = Get-ObjectProperty $localConfig "clients"
        if ($localClients) {
            $override = Get-ObjectProperty $localClients $clientName
            if ($override) {
                $overrideRoot = Get-ObjectProperty $override "root"
                if ($overrideRoot) {
                    $rootValue = [string]$overrideRoot
                }
            }
        }
    }

    $clientRoot = Expand-PortablePath -PathValue $rootValue -BasePath $repoRoot
    Assert-SafeClientRoot -ClientRoot $clientRoot -SourceRoot $sourceRoot
    foreach ($entry in $declaredEntries) {
        if ($entry.Targets -notcontains $clientName) {
            continue
        }
        $operations += [PSCustomObject]@{
            Client = $clientName
            ClientRoot = $clientRoot
            Name = $entry.Name
            SourcePath = $entry.SourcePath
            TargetPath = Join-Path $clientRoot $entry.Name
            Kind = $entry.Kind
        }
    }
}

Write-Host "machine_id: $machineId"
Write-Host "platform: $platformName"
Write-Host "command: $Command"
Write-Host "clients: $($selectedClients -join ', ')"
Write-Host "manifest: $ManifestPath"
if ($localConfig) {
    Write-Host "local override: $LocalConfigPath"
} else {
    Write-Host "local override: not configured (using hostname and manifest defaults)"
}
Write-Host "---"

$created = 0
$ok = 0
$conflicts = 0
$missing = 0
$index = 0

foreach ($operation in $operations) {
    $index += 1
    $prefix = "[$index/$($operations.Count)] [$($operation.Client)] $($operation.Name)"
    $existing = Get-Item -LiteralPath $operation.TargetPath -Force -ErrorAction SilentlyContinue

    if ($null -eq $existing) {
        if ($Command -eq "Doctor") {
            Write-Host "$prefix MISSING -> $($operation.SourcePath)" -ForegroundColor Yellow
            $missing += 1
            continue
        }
        if ($DryRun) {
            Write-Host "$prefix would create junction -> $($operation.SourcePath)"
            $created += 1
            continue
        }
        if (-not (Test-Path -LiteralPath $operation.ClientRoot -PathType Container)) {
            New-Item -ItemType Directory -Path $operation.ClientRoot -Force | Out-Null
        }
        New-Item -ItemType Junction -Path $operation.TargetPath -Target $operation.SourcePath | Out-Null
        Write-Host "$prefix created junction -> $($operation.SourcePath)" -ForegroundColor Green
        $created += 1
        continue
    }

    $linkTarget = Get-LinkTarget $existing
    if ($linkTarget -and (Test-SamePath $linkTarget $operation.SourcePath)) {
        Write-Host "$prefix OK -> $linkTarget"
        $ok += 1
        continue
    }

    if ($linkTarget) {
        if ($Command -eq "Sync" -and $RepairLinks) {
            if ($DryRun) {
                Write-Host "$prefix would repair junction: $linkTarget -> $($operation.SourcePath)" -ForegroundColor Yellow
            } else {
                Remove-ExistingLink $operation.TargetPath
                New-Item -ItemType Junction -Path $operation.TargetPath -Target $operation.SourcePath | Out-Null
                Write-Host "$prefix repaired junction -> $($operation.SourcePath)" -ForegroundColor Green
            }
            $created += 1
            continue
        }
        Write-Host "$prefix CONFLICT: existing link points to $linkTarget; use -RepairLinks to replace the link" -ForegroundColor Red
        $conflicts += 1
        continue
    }

    Write-Host "$prefix CONFLICT: target is a regular file or real directory; it will not be overwritten" -ForegroundColor Red
    $conflicts += 1
}

Write-Host "---"
Write-Host "OK: $ok, create/repair: $created, missing: $missing, conflicts: $conflicts"

if ($conflicts -gt 0 -or ($Command -eq "Doctor" -and $missing -gt 0)) {
    exit 1
}

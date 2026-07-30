[CmdletBinding()]
param(
    [switch]$KeepArtifacts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
    throw "No Chrome, Edge, or Brave executable found for layout inspection."
}

function Assert-True {
    param(
        [Parameter(Mandatory)][bool]$Condition,
        [Parameter(Mandatory)][string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

$testDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $testDir
$fixture = Join-Path $testDir "fixtures\text_clipping_16px.mmd"
$renderer = Join-Path $skillDir "scripts\render.ps1"
$cssFile = Join-Path $skillDir "references\fonts.css"
$configFile = Join-Path $skillDir "references\mmd-config.json"

$css = Get-Content -LiteralPath $cssFile -Raw -Encoding utf8
$cssWithoutComments = [regex]::Replace($css, "(?s)/\*.*?\*/", "")
$lateMetricProperty = [regex]::Match(
    $cssWithoutComments,
    "(?im)(?:^|[;{])\s*(?:font(?:-[a-z-]+)?|line-height|letter-spacing|word-spacing|padding(?:-[a-z-]+)?|white-space)\s*:"
)
Assert-True (-not $lateMetricProperty.Success) (
    "fonts.css changes text metrics after Mermaid layout: {0}" -f $lateMetricProperty.Value.Trim()
)
Assert-True ($cssWithoutComments -match "(?is)foreignObject\s*\{[^}]*overflow\s*:\s*visible") (
    "fonts.css must keep foreignObject overflow visible as a fallback guard."
)

$config = Get-Content -LiteralPath $configFile -Raw -Encoding utf8 | ConvertFrom-Json
Assert-True ([bool]$config.fontFamily) "mmd-config.json must define fontFamily before Mermaid layout."
Assert-True ($config.themeCSS -match "(?i)foreignObject.+overflow\s*:\s*visible") (
    "mmd-config.json must apply the foreignObject overflow guard during Mermaid rendering."
)

$artifactDir = Join-Path ([System.IO.Path]::GetTempPath()) (
    "mmd-explain-text-clipping-{0}" -f [guid]::NewGuid().ToString("N")
)
New-Item -ItemType Directory -Path $artifactDir -Force | Out-Null
$svgPath = Join-Path $artifactDir "text_clipping.svg"
$pngPath = Join-Path $artifactDir "text_clipping.png"
$htmlPath = Join-Path $artifactDir "inspect.html"
$profilePath = Join-Path $artifactDir "chrome-profile"

try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $renderer `
        -InputPath $fixture -OutputPath $svgPath -Width 1200 -Height 1200 -Scale 1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "SVG regression render failed with exit code $LASTEXITCODE."
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $renderer `
        -InputPath $fixture -OutputPath $pngPath -Width 1200 -Height 1200 -Scale 1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PNG regression render failed with exit code $LASTEXITCODE."
    }

    $svg = Get-Content -LiteralPath $svgPath -Raw -Encoding utf8
    # Keep this Windows PowerShell 5.1 script ASCII-safe; ConvertFrom-Json
    # decodes the fixture's Unicode labels without depending on a UTF-8 BOM.
    $expectedLabels = @(
        '["\u4e2d\u6587\u6807\u7b7e\u672b\u5c3e\u6d4b\u8bd5\u5b57",' +
        '"English label ending W",' +
        '"\u7c97\u4f53\u4e2d\u6587\u672b\u5c3e\u5b57",' +
        '"\u8fd9\u662f\u4e00\u4e2a\u5f88\u957f\u7684\u4e2d\u6587\u6807\u7b7e' +
        '\u7528\u4e8e\u9a8c\u8bc1\u5bbd\u5ea6\u8ba1\u7b97\u540e\u6700\u540e' +
        '\u5b57\u7b26\u7ec8",' +
        '"\u672b\u5c3e\u6807\u70b9\u6d4b\u8bd5\u3002\uff09\u3011",' +
        '"Mixed \u4e2d\u6587 and English ending \u5b57"]'
    ) -join "" | ConvertFrom-Json
    foreach ($expected in $expectedLabels) {
        Assert-True ($svg.Contains($expected)) "Rendered SVG lost expected label text: $expected"
    }

    $inspectorScript = @'
<script>
(async () => {
  await document.fonts.ready;
  const normalize = (value) => value.replace(/\s+/g, " ").trim();
  const rows = [...document.querySelectorAll(".node foreignObject")].map((foreignObject) => {
    const label = foreignObject.querySelector(".nodeLabel");
    const range = document.createRange();
    range.selectNodeContents(label);
    const textRect = range.getBoundingClientRect();
    const boxRect = foreignObject.getBoundingClientRect();
    const boxStyle = getComputedStyle(foreignObject);
    const labelStyle = getComputedStyle(label);
    const outside =
      textRect.left < boxRect.left - 0.75 ||
      textRect.right > boxRect.right + 0.75 ||
      textRect.top < boxRect.top - 0.75 ||
      textRect.bottom > boxRect.bottom + 0.75;
    const overflowVisible =
      boxStyle.overflowX === "visible" && boxStyle.overflowY === "visible";
    return {
      text: normalize(label.textContent),
      boxWidth: boxRect.width,
      textWidth: textRect.width,
      fontFamily: labelStyle.fontFamily,
      fontSize: labelStyle.fontSize,
      overflowX: boxStyle.overflowX,
      overflowY: boxStyle.overflowY,
      clipped: outside && !overflowVisible
    };
  });
  document.body.dataset.result = encodeURIComponent(JSON.stringify({
    fontsStatus: document.fonts.status,
    rows
  }));
})();
</script>
'@
    $html = '<!doctype html><html><head><meta charset="utf-8"></head><body>' +
        $svg + $inspectorScript + '</body></html>'
    [System.IO.File]::WriteAllText($htmlPath, $html, [System.Text.UTF8Encoding]::new($false))

    $browser = Find-BrowserPath
    $htmlUri = ([uri]$htmlPath).AbsoluteUri
    $browserArgs = @(
        "--headless",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--allow-file-access-from-files",
        "--virtual-time-budget=3000",
        "--user-data-dir=$profilePath",
        "--dump-dom",
        $htmlUri
    )
    # Windows Chrome may emit --dump-dom on a native stream that PowerShell
    # classifies as stderr. Capture both streams, then trust the structured
    # result rather than the stream classification.
    $dump = (
        & $browser @browserArgs 2>&1 |
            ForEach-Object { $_.ToString() }
    ) -join "`n"
    $resultMatch = [regex]::Match($dump, 'data-result="([^"]+)"')
    Assert-True $resultMatch.Success "Browser did not return layout inspection data."
    $encodedResult = [System.Net.WebUtility]::HtmlDecode($resultMatch.Groups[1].Value)
    $result = [uri]::UnescapeDataString($encodedResult) | ConvertFrom-Json

    Assert-True ($result.fontsStatus -eq "loaded") (
        "Browser fonts were not ready during inspection: $($result.fontsStatus)"
    )
    Assert-True ($result.rows.Count -eq $expectedLabels.Count) (
        "Expected $($expectedLabels.Count) node labels, got $($result.rows.Count)."
    )
    foreach ($expected in $expectedLabels) {
        $row = $result.rows | Where-Object { $_.text -eq $expected } | Select-Object -First 1
        Assert-True ($null -ne $row) "Browser DOM lost expected terminal text: $expected"
        Assert-True ($row.fontSize -eq "16px") (
            "Late CSS changed Mermaid's 16px label size for '$expected' to $($row.fontSize)."
        )
        Assert-True (-not $row.clipped) (
            "Browser reports clipped text for '$expected' " +
            "(text=$($row.textWidth), box=$($row.boxWidth), overflow=$($row.overflowX)/$($row.overflowY))."
        )
    }

    Write-Output "PASS text clipping regression"
    Write-Output "fonts=$($result.fontsStatus); labels=$($result.rows.Count); fontSize=16px"
    if ($KeepArtifacts) {
        Write-Output "PNG=$pngPath"
    }
} finally {
    if ($KeepArtifacts) {
        Write-Output "Artifacts kept at $artifactDir"
    } elseif (Test-Path -LiteralPath $artifactDir -PathType Container) {
        Remove-Item -LiteralPath $artifactDir -Recurse -Force
    }
}

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envExample = Get-Content -LiteralPath (Join-Path $repoRoot ".env.example")
$imageLine = $envExample | Where-Object { $_ -match '^KONG_IMAGE=' } | Select-Object -First 1
if (-not $imageLine) {
    throw "KONG_IMAGE is not defined in .env.example"
}
$image = $imageLine -replace '^KONG_IMAGE=', ''
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("kong-fragments-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir | Out-Null

function Write-MergedConfig([string]$name, [string]$fragmentPath) {
    $target = Join-Path $tempDir $name
    @'
_format_version: "3.0"
services:
  - name: mock-upstream
    url: http://mock-upstream:8080
    routes:
      - name: mock-route
        paths:
          - /mock
        strip_path: true
consumers:
  - username: fintech-free
  - username: fintech-premium
plugins:
'@ | Set-Content -LiteralPath $target -Encoding utf8

    $lines = Get-Content -LiteralPath $fragmentPath
    $pluginsLine = [Array]::IndexOf($lines, "plugins:")
    if ($pluginsLine -lt 0 -or $pluginsLine -eq ($lines.Count - 1)) {
        throw "Expected a top-level plugins: list in $fragmentPath"
    }
    $lines | Select-Object -Skip ($pluginsLine + 1) | Add-Content -LiteralPath $target -Encoding utf8
    return $target
}

try {
    $ratelimit = Write-MergedConfig "ratelimit.yml" (Join-Path $repoRoot "kong\fragments\20-ratelimit.yml")
    $transform = Write-MergedConfig "transform.yml" (Join-Path $repoRoot "kong\fragments\30-transform.yml")
    foreach ($config in @($ratelimit, $transform)) {
        $fileName = [System.IO.Path]::GetFileName($config)
        Write-Output "Parsing $fileName with $image"
        docker run --rm -v "${tempDir}:/c:ro" $image kong config parse "/c/$fileName"
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
}
finally {
    if (Test-Path $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force
    }
}

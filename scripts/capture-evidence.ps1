param(
  [Parameter(Mandatory = $true)][string]$Title,
  [Parameter(Mandatory = $true)][string]$InputFile,
  [Parameter(Mandatory = $true)][string]$OutputFile
)

# Render a terminal transcript to a PNG so evidence is viewable without a
# terminal. Uses only Windows System.Drawing (no extra tools to install).
Add-Type -AssemblyName System.Drawing

$lines = Get-Content -Path $InputFile
$font = New-Object System.Drawing.Font('Consolas', 13)
$titleFont = New-Object System.Drawing.Font('Consolas', 16, [System.Drawing.FontStyle]::Bold)
$padding = 30
$titleHeight = 46
$lineHeight = 21

$maxWidth = 0
foreach ($line in $lines) { $maxWidth = [Math]::Max($maxWidth, [Math]::Ceiling(([System.Drawing.Graphics]::FromImage((New-Object System.Drawing.Bitmap(1,1)))).MeasureString($line, $font).Width)) }
$width = [Math]::Max(900, $maxWidth + 2 * $padding)
$height = $titleHeight + $lines.Count * $lineHeight + 2 * $padding

$bitmap = New-Object System.Drawing.Bitmap([int]$width, [int]$height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([System.Drawing.Color]::FromArgb(24, 24, 32))
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::SingleBitPerPixelGridFit
$graphics.DrawString($Title, $titleFont, [System.Drawing.Brushes]::Cyan, $padding, 18)

$y = $titleHeight + $padding
foreach ($line in $lines) {
  $graphics.DrawString($line, $font, [System.Drawing.Brushes]::WhiteSmoke, $padding, $y)
  $y += $lineHeight
}

$directory = Split-Path -Parent $OutputFile
if (-not (Test-Path $directory)) { New-Item -ItemType Directory -Force -Path $directory | Out-Null }
$bitmap.Save($OutputFile, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$font.Dispose()
$titleFont.Dispose()
$bitmap.Dispose()
Write-Output "saved $OutputFile ($width x $height)"

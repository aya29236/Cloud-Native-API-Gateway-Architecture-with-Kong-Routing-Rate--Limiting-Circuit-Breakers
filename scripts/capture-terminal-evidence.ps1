param(
  [Parameter(Mandatory = $true)] [string] $Id,
  [Parameter(Mandatory = $true)] [string] $Output
)

$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Drawing

$source = @'
using System;
using System.Runtime.InteropServices;

public static class Win32Capture
{
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
}
'@
Add-Type -TypeDefinition $source

$repo = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path $env:TEMP 'opencode'
$inner = Join-Path $PSScriptRoot 'terminal-evidence-run.ps1'
$sentinel = Join-Path $tmp "terminal_$Id.done"
Remove-Item $sentinel -Force -ErrorAction SilentlyContinue

$arguments = "-NoProfile -NoExit -File `"$inner`" -Id $Id"
$process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments `
  -WorkingDirectory $repo -PassThru -WindowStyle Normal

for ($i = 0; $i -lt 180; $i++) {
  if (Test-Path $sentinel) { break }
  Start-Sleep -Seconds 1
}
if (-not (Test-Path $sentinel)) {
  Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  throw "evidence $Id timed out"
}
$result = (Get-Content $sentinel -Raw).Trim()

$shell = New-Object -ComObject WScript.Shell
$windowProcess = $null
for ($i = 0; $i -lt 20; $i++) {
  $windowProcess = Get-Process | Where-Object { $_.MainWindowTitle -like "Evidence $Id - live terminal capture*" } | Select-Object -First 1
  if ($null -ne $windowProcess -and $windowProcess.MainWindowHandle -ne [IntPtr]::Zero) { break }
  Start-Sleep -Milliseconds 300
}
if ($null -eq $windowProcess -or $windowProcess.MainWindowHandle -eq [IntPtr]::Zero) { throw "no window for evidence $Id" }
$handle = $windowProcess.MainWindowHandle
$null = $shell.AppActivate($windowProcess.Id)
Start-Sleep -Milliseconds 700

[void][Win32Capture]::ShowWindow($handle, 9)
[void][Win32Capture]::SetForegroundWindow($handle)
$null = $shell.AppActivate($process.Id)
Start-Sleep -Milliseconds 900

$rect = New-Object Win32Capture+RECT
if (-not [Win32Capture]::GetWindowRect($handle, [ref]$rect)) { throw "GetWindowRect failed for $Id" }
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
$bitmap = New-Object System.Drawing.Bitmap($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
$directory = Split-Path -Parent $Output
if (-not (Test-Path $directory)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
$bitmap.Save($Output, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()

Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
if ($windowProcess.Id -ne $process.Id) { Stop-Process -Id $windowProcess.Id -Force -ErrorAction SilentlyContinue }
"captured $Id $result $width x $height -> $Output"

# Restart everything needed for the Fairbeam web app from a source checkout:
# Vite UI on 5310 and fairbeam serve API on 5320. Exits when both answer so the
# status-bar task can be clicked again (does not hold a VS Code background task).
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$sim = Join-Path $root ".sim"
New-Item -ItemType Directory -Force -Path $sim | Out-Null

function Stop-FairbeamDevProcesses {
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -and ($_.CommandLine -match 'fairbeam serve|fairbeam\.preview worker') } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

  $rootEsc = [regex]::Escape($root)
  Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object {
      $_.CommandLine -and
      $_.CommandLine -match $rootEsc -and
      $_.CommandLine -match 'vite|npm-cli|npm\\bin'
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Wait-HttpOk([string]$Url, [int]$TimeoutSec = 45) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
    } catch { Start-Sleep -Milliseconds 400 }
  }
  return $false
}

Write-Host "Stopping previous Fairbeam Vite / serve processes..."
Stop-FairbeamDevProcesses
Start-Sleep -Seconds 1

if (-not $env:OPENEMS_INSTALL_PATH) {
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "org.fairbeam.desktop\runtime\openEMS"),
    (Join-Path $env:LOCALAPPDATA "org.fairbeam.desktop\gpu-runtime\openEMS"),
    "C:\opt\openEMS"
  )
  $env:OPENEMS_INSTALL_PATH = $candidates |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ "CSXCAD.dll") } |
    Select-Object -First 1
  if (-not $env:OPENEMS_INSTALL_PATH) {
    $env:OPENEMS_INSTALL_PATH = $candidates[0]
  }
}
Write-Host "OPENEMS_INSTALL_PATH=$($env:OPENEMS_INSTALL_PATH)"
$env:PYTHONPATH = Join-Path $root "python"

$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
  throw "Missing venv python: $py"
}

$viteOut = Join-Path $sim "vite.out.log"
$viteErr = Join-Path $sim "vite.err.log"
$apiOut = Join-Path $sim "serve-api.out.log"
$apiErr = Join-Path $sim "serve-api.err.log"
foreach ($f in @($viteOut, $viteErr, $apiOut, $apiErr)) {
  if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue }
}

Write-Host "Starting Vite (http://127.0.0.1:5310/)..."
Start-Process -FilePath $npm -ArgumentList @("run", "dev") -WorkingDirectory $root `
  -WindowStyle Hidden -RedirectStandardOutput $viteOut -RedirectStandardError $viteErr | Out-Null

Write-Host "Starting fairbeam serve (http://127.0.0.1:5320/api)..."
Start-Process -FilePath $py -ArgumentList @("-m", "fairbeam", "serve") `
  -WorkingDirectory (Join-Path $root "python") `
  -WindowStyle Hidden -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr | Out-Null

$uiOk = Wait-HttpOk "http://127.0.0.1:5310/"
$apiOk = Wait-HttpOk "http://127.0.0.1:5320/api/health"
if (-not $uiOk) { throw "Vite did not become ready on 5310. See $viteOut / $viteErr" }
if (-not $apiOk) { throw "fairbeam serve did not become ready on 5320. See $apiOut / $apiErr" }

Write-Host "Ready:"
Write-Host "  UI   http://127.0.0.1:5310/"
Write-Host "  API  http://127.0.0.1:5320/api"
Start-Process "http://127.0.0.1:5310/"

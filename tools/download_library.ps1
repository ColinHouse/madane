# Download the sample libraries approved by the user (2026-10-13).
# Each download goes into its own new directory under library\.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$lib = Join-Path (Split-Path -Parent $PSScriptRoot) 'library'      # library\ next to tools\
$log = Join-Path $lib 'download_log.txt'
New-Item -ItemType Directory -Force -Path $lib | Out-Null
function Log($msg) { "$(Get-Date -Format HH:mm:ss) $msg" | Add-Content -Path $log -Encoding UTF8 }

function Fetch($url, $dir, $name) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $out = Join-Path $dir $name
  Log "start $name"
  & curl.exe -L --fail --retry 3 --silent --show-error -o $out $url
  if ($LASTEXITCODE -eq 0) { Log ("done  {0} ({1:N1} MB)" -f $name, ((Get-Item $out).Length / 1MB)) }
  else { Log "FAILED $name (curl exit $LASTEXITCODE)" }
}

Fetch 'https://www.7-zip.org/a/7zr.exe' "$lib\7zip" '7zr.exe'
Fetch 'https://github.com/freepats/electric-bass-YR/releases/download/2019-09-30/FingerBassYR-SFZ+FLAC-20190930.7z' "$lib\fingerbass_dl" 'FingerBassYR-SFZ+FLAC-20190930.7z'

# VSCO-2 CE string sections (sustain, vibrato), 75 WAV files
$tree = Invoke-RestMethod -Uri 'https://api.github.com/repos/sgossner/VSCO-2-CE/git/trees/master?recursive=1' -Headers @{ 'User-Agent' = 'curl' } -TimeoutSec 60
$files = $tree.tree | Where-Object { $_.type -eq 'blob' -and $_.path -match '(?i)^Strings/(Violin Section|Viola Section|Cello Section)/sus' -and $_.path -match '(?i)\.(wav|flac)$' }
Log "vsco2: $($files.Count) files"
foreach ($f in $files) {
  $dest = Join-Path "$lib\vsco2" ($f.path -replace '/', '\')
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  $url = 'https://raw.githubusercontent.com/sgossner/VSCO-2-CE/master/' + (($f.path -split '/') | ForEach-Object { [uri]::EscapeDataString($_) }) -join '/'
  & curl.exe -L --fail --retry 3 --silent --show-error -o $dest $url
  if ($LASTEXITCODE -ne 0) { Log "FAILED $($f.path)" }
}
Log "vsco2 done"

Fetch 'https://github.com/freepats/muldjordkit/releases/download/2020-10-18/MuldjordKit-SFZ+FLAC-20201018.7z' "$lib\muldjord_dl" 'MuldjordKit-SFZ+FLAC-20201018.7z'
Fetch 'https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPianoV3+20161209_44khz16bit.tar.xz' "$lib\salamander_dl" 'SalamanderGrandPianoV3+20161209_44khz16bit.tar.xz'
Log "ALL DONE"

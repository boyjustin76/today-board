# Today Board - get a private copy of Python (Windows). No install, no admin rights, nothing added to PATH.
# Downloads the official "embeddable" Python from python.org into tools\python\ and checks its SHA-256.
# Run by board.cmd / start.bat only when this PC has no Python. Delete tools\python\ to undo.
# ASCII only on purpose (Windows PowerShell 5.1 reads files without a BOM in the local code page).
$ErrorActionPreference = 'Stop'
$Version = '3.13.17'
$Url     = "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip"
$Sha256  = '9E35319BFFEDAB8B36AD44D8F377CB4F1733BCEC257A0B6D04D94F01486DDB38'
$Dest    = Join-Path $PSScriptRoot 'python'
$Exe     = Join-Path $Dest 'python.exe'

if (Test-Path $Exe) { Write-Host "Python is already here: $Exe"; exit 0 }
Write-Host "This PC has no Python. Getting a private copy (about 11 MB) from python.org ..."
$zip = Join-Path $env:TEMP ("today-board-python-" + [guid]::NewGuid().ToString('N') + '.zip')
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  $ProgressPreference = 'SilentlyContinue'
  Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing
  $got = (Get-FileHash $zip -Algorithm SHA256).Hash
  if ($got -ne $Sha256) { throw "The downloaded file is not the expected one (SHA-256 $got). Nothing was installed." }
  $tmp = "$Dest.partial"
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
  Expand-Archive -Path $zip -DestinationPath $tmp -Force
  if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
  Rename-Item $tmp 'python'
  Write-Host "Ready: $Exe"
  exit 0
} catch {
  Write-Host ""
  Write-Host "Could not get Python automatically: $($_.Exception.Message)"
  Write-Host "Do one of these, then start again:"
  Write-Host "  - In a terminal:  winget install -e --id Python.Python.3.13 --scope user"
  Write-Host "  - Or install from https://www.python.org/downloads/  (tick 'Add python.exe to PATH')"
  exit 1
} finally {
  Remove-Item $zip -Force -ErrorAction SilentlyContinue
}

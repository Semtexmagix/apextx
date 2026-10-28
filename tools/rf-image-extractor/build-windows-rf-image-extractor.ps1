# Build the ApexTX RF Image Extractor as a standalone Windows .exe.
#
# Produces dist/ApexTX-RF-Image-Extractor.exe: a single, double-clickable app
# with a native window (Edge WebView2, falling back to the browser), in the same
# style as the ApexTX Flasher and Theme Editor. It unpacks the RF-module and
# receiver firmware images from the user's own FlySky Noble NB4/NB4+ updater and
# writes them to the radio's USB storage.
#
# No FlySky files are bundled; the user supplies their own updater.
#
# Requirements: Windows, Python 3.11+ on PATH.
# Run from this folder:  pwsh build-windows-rf-image-extractor.ps1

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
Set-Location $here
$work = Join-Path $here 'build'
New-Item -ItemType Directory -Force $work | Out-Null

Write-Host '==> Python venv + dependencies'
$venv = Join-Path $work 'venv'
if (-not (Test-Path $venv)) { python -m venv $venv }
$py = Join-Path $venv 'Scripts/python.exe'
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install pyinstaller==6.11.1 pywebview==6.2.1 pillow==11.1.0 | Out-Null

Write-Host '==> App icon from the brand logo'
$ico = Join-Path $work 'ApexTX.ico'
& $py -c @"
from PIL import Image
src = Image.open(r'apextx-updater-logo.png').convert('RGBA')
src = src.crop(src.getbbox()); w, h = src.size
S = 256; c = Image.new('RGBA', (S, S), (0, 0, 0, 0))
sc = min((S-20)/w, (S-20)/h); rw, rh = round(w*sc), round(h*sc)
c.paste(src.resize((rw, rh), Image.LANCZOS), ((S-rw)//2, (S-rh)//2))
c.save(r'$ico'.replace('\\','/'), sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print('icon ok')
"@

Write-Host '==> PyInstaller'
& (Join-Path $venv 'Scripts/pyinstaller.exe') --onefile --windowed --name ApexTX-RF-Image-Extractor `
    --icon $ico `
    --add-data 'apextx-rf-image-extractor.html;.' `
    --add-data 'apextx-updater-logo.png;.' `
    --collect-all webview `
    --noconfirm --clean (Join-Path $here 'apextx-rf-image-extractor.py')

Write-Host '==> Done: dist/ApexTX-RF-Image-Extractor.exe'

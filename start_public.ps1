# Share DocWeave through a public link (runs on this computer, uses your local Ollama models).
#
#   .\start_public.ps1                       # random password is generated and printed
#   .\start_public.ps1 -Password "mypass"    # choose the password
#   .\start_public.ps1 -NoTunnel             # just run the production server locally
#
# Needs: Ollama running, and `cloudflared` for the public link (winget install Cloudflare.cloudflared).
# See DEPLOY.md for details and limits.
param(
    [string]$User = "docweave",
    [string]$Password = "",
    [int]$Port = 5000,
    [switch]$NoTunnel,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$python = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "venv not found. Create it and install requirements first (see INSTALL.md)." }

# 1. Build the frontend so Flask can serve it from one port.
if (-not $SkipBuild) {
    Push-Location (Join-Path $root "frontend")
    npm install --no-audit --no-fund
    npm run build
    Pop-Location
}

# 2. Public mode + shared password (only github.com repos, risky endpoints disabled).
if (-not $Password) {
    $Password = -join ((48..57) + (97..122) | Get-Random -Count 10 | ForEach-Object { [char]$_ })
}
$env:DOCWEAVE_PUBLIC = "1"
$env:DOCWEAVE_USER = $User
$env:DOCWEAVE_PASSWORD = $Password

# 3. Start the server (bound to this computer only; the tunnel connects to it locally).
$server = Start-Process -FilePath $python -ArgumentList "run_web_ui.py", "--host", "127.0.0.1", "--port", "$Port" -PassThru -NoNewWindow
Start-Sleep -Seconds 6
Write-Host ""
Write-Host "Local address : http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "Login         : user '$User'  password '$Password'" -ForegroundColor Yellow

try {
    if ($NoTunnel) {
        Write-Host "Server running. Press Ctrl+C to stop."
        Wait-Process -Id $server.Id
    }
    else {
        if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
            Write-Host "cloudflared is not installed. Install it with:  winget install Cloudflare.cloudflared" -ForegroundColor Red
            Write-Host "Then run this script again (the server is stopping)."
            return
        }
        Write-Host "Starting the public tunnel. Look for the https://....trycloudflare.com address below." -ForegroundColor Green
        Write-Host "Share that link plus the login above. Press Ctrl+C to stop sharing."
        cloudflared tunnel --url "http://127.0.0.1:$Port"
    }
}
finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
}

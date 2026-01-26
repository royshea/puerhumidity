# Deploy to Azure Web App
# Usage: .\scripts\deploy.ps1
#
# Prerequisites:
# - Azure CLI installed and logged in (az login)
# - Web App already created (app-puerhumidity)

param(
    [string]$AppName = "app-puerhumidity",
    [string]$ResourceGroup = "rg-puerhumidity",
    [string]$TempDir = "deploy_temp",
    [string]$ZipFile = "deploy.zip"
)

Write-Host "Creating clean deployment package..." -ForegroundColor Cyan

# Clean up any previous deployment artifacts
if (Test-Path $TempDir) {
    Remove-Item -Recurse -Force $TempDir
}
if (Test-Path $ZipFile) {
    Remove-Item -Force $ZipFile
}

# Create temp directory
New-Item -ItemType Directory $TempDir | Out-Null

# Copy only production files
Write-Host "Copying app folder..." -ForegroundColor Gray
Copy-Item -Recurse app "$TempDir/app"

Write-Host "Copying requirements.txt..." -ForegroundColor Gray
Copy-Item requirements.txt "$TempDir/"

# Remove __pycache__ directories
Write-Host "Removing __pycache__ directories..." -ForegroundColor Gray
Get-ChildItem -Recurse -Directory -Filter "__pycache__" $TempDir | Remove-Item -Recurse -Force

# Remove .pyc files (in case any exist outside __pycache__)
Get-ChildItem -Recurse -Filter "*.pyc" $TempDir | Remove-Item -Force

# Create ZIP archive
Write-Host "Creating ZIP archive..." -ForegroundColor Gray
Compress-Archive -Path "$TempDir/*" -DestinationPath $ZipFile -Force

# Clean up temp directory
Remove-Item -Recurse -Force $TempDir

# Get ZIP size
$zipSize = (Get-Item $ZipFile).Length / 1KB
Write-Host "Created $ZipFile ($([math]::Round($zipSize, 1)) KB)" -ForegroundColor Green

# Deploy to Azure
Write-Host "`nDeploying to Azure Web App: $AppName..." -ForegroundColor Cyan
az webapp deploy `
    --name $AppName `
    --resource-group $ResourceGroup `
    --src-path $ZipFile `
    --type zip

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nDeployment successful!" -ForegroundColor Green
    Write-Host "App URL: https://$AppName.azurewebsites.net" -ForegroundColor Cyan
    
    # Clean up ZIP file
    Remove-Item -Force $ZipFile
} else {
    Write-Host "`nDeployment failed!" -ForegroundColor Red
    exit 1
}

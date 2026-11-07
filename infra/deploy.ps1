<#
.SYNOPSIS
  Provisiona a infra (Bicep), builda a imagem no ACR e publica no Azure Container Apps.

.EXAMPLE
  ./infra/deploy.ps1 -ResourceGroup rg-hospital-monitor -Location brazilsouth
#>
param(
  [string]$ResourceGroup = "rg-hospital-monitor",
  [string]$Location = "brazilsouth",
  [string]$Environment = "dev",
  [string]$ImageTag = (Get-Date -Format "yyyyMMddHHmmss"),
  [ValidateSet("F0", "S0")][string]$SpeechSku = "S0",
  [ValidateSet("F0", "S")][string]$LanguageSku = "S"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Bicep = Join-Path $PSScriptRoot "main.bicep"

# PowerShell não interrompe em falha de executável nativo: checa o código de saída do az.
function Assert-Ok($step) { if ($LASTEXITCODE -ne 0) { throw "Falha em: $step (código $LASTEXITCODE)" } }

Write-Host "==> Resource group $ResourceGroup ($Location)"
az group create --name $ResourceGroup --location $Location --output none
Assert-Ok "criar resource group"

Write-Host "==> Fase 1: infraestrutura (imagem placeholder)"
$out = az deployment group create `
  --resource-group $ResourceGroup --template-file $Bicep `
  --parameters environmentName=$Environment speechSku=$SpeechSku languageSku=$LanguageSku `
  --query properties.outputs --output json | ConvertFrom-Json
Assert-Ok "deploy da infraestrutura (fase 1)"
$acr = $out.acrName.value

Write-Host "==> Build da imagem no ACR $acr (az acr build, sem Docker local)"
az acr build --registry $acr --image "hospital-monitor:$ImageTag" --file (Join-Path $Root "Dockerfile") $Root
Assert-Ok "az acr build"

Write-Host "==> Fase 2: apontando o Container App para hospital-monitor:$ImageTag"
$out = az deployment group create `
  --resource-group $ResourceGroup --template-file $Bicep `
  --parameters environmentName=$Environment speechSku=$SpeechSku languageSku=$LanguageSku containerImage="hospital-monitor:$ImageTag" `
  --query properties.outputs --output json | ConvertFrom-Json
Assert-Ok "deploy do app (fase 2)"

Write-Host ""
Write-Host "Pronto! App: $($out.appUrl.value)" -ForegroundColor Green

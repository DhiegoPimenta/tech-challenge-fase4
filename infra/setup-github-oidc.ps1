<#
.SYNOPSIS
  Cria a identidade que o GitHub Actions usa para publicar no Azure (OIDC, sem senha).

.DESCRIPTION
  - App registration + service principal "gh-hospital-monitor"
  - Credencial federada: só o workflow da branch main do repositório informado
  - Contributor SOMENTE no resource group  (atualizar o Container App)
  - AcrPush SOMENTE no registry            (enviar a imagem)
  - Cadastra no repositório os IDs que o workflow lê (AZURE_CLIENT_ID/TENANT_ID/SUBSCRIPTION_ID).
    São identificadores, não senhas.

  Requer: az login (assinatura correta) e gh auth login. Rode uma vez, depois da fase 1 do deploy.

.EXAMPLE
  ./infra/setup-github-oidc.ps1 -Repo DhiegoPimenta/tech-challenge-fase4
#>
param(
  [Parameter(Mandatory)][string]$Repo,
  [string]$ResourceGroup = "rg-hospital-monitor",
  [string]$Branch = "main"
)

$ErrorActionPreference = "Continue"
function Assert-Ok($step) { if ($LASTEXITCODE -ne 0) { throw "Falha em: $step" } }

$sub = az account show --query id -o tsv; Assert-Ok "az account show"
$tenant = az account show --query tenantId -o tsv
$acrId = az acr list -g $ResourceGroup --query "[0].id" -o tsv
if (-not $acrId) { throw "Registry não encontrado em $ResourceGroup. Rode antes a fase 1 (infra/deploy.ps1)." }

Write-Host "==> App registration"
$app = az ad app list --display-name "gh-hospital-monitor" --query "[0].appId" -o tsv
if (-not $app) { $app = az ad app create --display-name "gh-hospital-monitor" --query appId -o tsv; Assert-Ok "criar app" }
if (-not (az ad sp show --id $app --query id -o tsv 2>$null)) { az ad sp create --id $app --output none; Assert-Ok "criar service principal"; Start-Sleep 20 }

Write-Host "==> Credencial federada (repo:$Repo, branch $Branch)"
$f = Join-Path $env:TEMP "fedcred.json"
@{ name = "github-$Branch"; issuer = "https://token.actions.githubusercontent.com"
   subject = "repo:${Repo}:ref:refs/heads/$Branch"; audiences = @("api://AzureADTokenExchange") } |
  ConvertTo-Json | Set-Content $f -Encoding ascii
az ad app federated-credential create --id $app --parameters "@$f" --output none 2>$null

Write-Host "==> Papéis com escopo mínimo"
az role assignment create --assignee $app --role Contributor --scope "/subscriptions/$sub/resourceGroups/$ResourceGroup" --output none; Assert-Ok "Contributor no RG"
az role assignment create --assignee $app --role AcrPush --scope $acrId --output none; Assert-Ok "AcrPush no ACR"

Write-Host "==> Secrets no GitHub"
gh secret set AZURE_CLIENT_ID --body $app --repo $Repo; Assert-Ok "secret client id"
gh secret set AZURE_TENANT_ID --body $tenant --repo $Repo
gh secret set AZURE_SUBSCRIPTION_ID --body $sub --repo $Repo

Write-Host "`nPronto. Dispare o deploy:  gh workflow run deploy.yml --repo $Repo" -ForegroundColor Green

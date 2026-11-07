#!/usr/bin/env bash
# Provisiona a infra (Bicep), builda a imagem no ACR e publica no Azure Container Apps.
# Uso: ./infra/deploy.sh [resource-group] [location] [environment]
set -euo pipefail

RG="${1:-rg-hospital-monitor}"
LOCATION="${2:-brazilsouth}"
ENVIRONMENT="${3:-dev}"
TAG="$(date +%Y%m%d%H%M%S)"
SPEECH_SKU="${SPEECH_SKU:-S0}"
LANGUAGE_SKU="${LANGUAGE_SKU:-S}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BICEP="$ROOT/infra/main.bicep"

echo "==> Resource group $RG ($LOCATION)"
az group create --name "$RG" --location "$LOCATION" --output none

echo "==> Fase 1: infraestrutura (imagem placeholder)"
ACR=$(az deployment group create --resource-group "$RG" --template-file "$BICEP" \
  --parameters environmentName="$ENVIRONMENT" speechSku="$SPEECH_SKU" languageSku="$LANGUAGE_SKU" \
  --query properties.outputs.acrName.value --output tsv)

echo "==> Build da imagem no ACR $ACR (az acr build, sem Docker local)"
az acr build --registry "$ACR" --image "hospital-monitor:$TAG" --file "$ROOT/Dockerfile" "$ROOT"

echo "==> Fase 2: apontando o Container App para hospital-monitor:$TAG"
URL=$(az deployment group create --resource-group "$RG" --template-file "$BICEP" \
  --parameters environmentName="$ENVIRONMENT" speechSku="$SPEECH_SKU" languageSku="$LANGUAGE_SKU" \
  containerImage="hospital-monitor:$TAG" \
  --query properties.outputs.appUrl.value --output tsv)

echo
echo "Pronto! App: $URL"

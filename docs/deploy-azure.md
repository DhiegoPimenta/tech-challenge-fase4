# Deploy no Azure

## Pré-requisitos

* Assinatura Azure com permissão de *Contributor* e *User Access Administrator* no resource group (o template cria uma role assignment `AcrPull`).
* [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.60+ (`az bicep` já vem junto).
* Providers registrados (uma vez por assinatura):

```bash
az provider register -n Microsoft.App -n Microsoft.ContainerRegistry -n Microsoft.CognitiveServices -n Microsoft.OperationalInsights --wait
```

## Deploy completo (um comando)

```powershell
az login
az account set --subscription "<id-ou-nome>"
./infra/deploy.ps1 -ResourceGroup rg-hospital-monitor -Location eastus2 -Environment dev
```

Linux/macOS: `./infra/deploy.sh rg-hospital-monitor eastus2 dev`. Em assinaturas Azure for Students, uma política limita as regiões (ex.: `eastus2`, `eastus`, `southcentralus`); `brazilsouth` é recusada.

O script executa:

1. `az group create`
2. **Fase 1** — `az deployment group create` com `infra/main.bicep` (imagem placeholder): cria Log Analytics, ACR, managed identity, role `AcrPull`, Speech, Language, ambiente e Container App.
3. `az acr build` — builda o `Dockerfile` **na nuvem** e publica `hospital-monitor:<timestamp>` no ACR (o 1º build leva alguns minutos: instala PyTorch CPU e baixa os pesos YOLO).
4. **Fase 2** — reaplica o Bicep com `containerImage=hospital-monitor:<tag>`; o Container App troca para a imagem real.
5. Imprime a URL pública (`https://ca-hospmon-dev.<...>.azurecontainerapps.io`).

Re-executar é seguro (idempotente): cada execução gera uma nova tag e uma nova revisão.

## Parâmetros do Bicep

| Parâmetro | Padrão | Observação |
|---|---|---|
| `namePrefix` | `hospmon` | 3–12 caracteres |
| `environmentName` | `dev` | entra nos nomes |
| `location` | região do RG | confirme disponibilidade de Speech/Language/Container Apps |
| `containerImage` | vazio | vazio = placeholder (fase 1) |
| `speechSku` / `languageSku` | `S0` / `S` | `F0` = gratuito (um por assinatura) |
| `alertWebhookUrl` | vazio | secure; habilita o botão de envio na UI |
| `minReplicas` / `maxReplicas` | `1` / `2` | |

Exemplo com SKUs gratuitos e webhook:

```bash
az deployment group create -g rg-hospital-monitor -f infra/main.bicep \
  -p speechSku=F0 languageSku=F0 alertWebhookUrl="https://..."
```

Validar sem aplicar:

```bash
az bicep build --file infra/main.bicep          # compila/valida
az deployment group what-if -g rg-hospital-monitor -f infra/main.bicep
```

## CI/CD (GitHub Actions)

* `ci.yml`: lint + testes + `az bicep build` + build da imagem Docker, em push e PR.
* `deploy.yml`: *manual* (`workflow_dispatch`), login por **OIDC** (sem senha guardada) e chama `infra/deploy.sh`.

Configuração única do OIDC:

```bash
az ad app create --display-name gh-hospital-monitor          # anote appId
az ad sp create --id <appId>
az role assignment create --assignee <appId> --role Owner --scope /subscriptions/<sub>/resourceGroups/rg-hospital-monitor
az ad app federated-credential create --id <appId> --parameters '{
  "name":"github-main","issuer":"https://token.actions.githubusercontent.com",
  "subject":"repo:<owner>/<repo>:ref:refs/heads/main","audiences":["api://AzureADTokenExchange"]}'
```

Depois cadastre os *secrets* `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` no repositório.
(`Owner` no RG é necessário pela role assignment do `AcrPull`; restrinja ao mínimo que sua política permitir.)

## Operação

```bash
# logs do app
az containerapp logs show -g rg-hospital-monitor -n ca-hospmon-dev --follow
# revisões
az containerapp revision list -g rg-hospital-monitor -n ca-hospmon-dev -o table
# rollback: ativar revisão anterior
az containerapp ingress traffic set -g rg-hospital-monitor -n ca-hospmon-dev --revision-weight <revisao>=100
```

## Custos e limpeza

* Container App com `minReplicas=1` (2 vCPU/4 GiB) cobra enquanto estiver rodando; para economizar fora das gravações use `minReplicas=0` (1º acesso fica lento) ou apague o grupo.
* ACR Basic e Log Analytics têm custo baixo e fixo/por uso; Speech e Language cobram por uso (existe camada F0).
* **Apagar tudo após a entrega/gravação:**

```bash
az group delete --name rg-hospital-monitor --yes --no-wait
```

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `InvalidTemplateDeployment ... customSubDomainName` | nome já usado globalmente; mude `namePrefix` |
| Fase 1 funciona, app mostra "Hello World" | fase 2 não rodou; rode o script de novo |
| `ImagePullBackOff` / unauthorized | role `AcrPull` ainda propagando; aguarde 1–2 min e reinicie a revisão |
| Cota de F0 excedida | já existe um recurso F0 na assinatura; use S0/S |
| Transcrição retorna vazio | áudio sem fala ou idioma errado (`AZURE_SPEECH_LANGUAGE`) |
| App lento no vídeo | YOLO em CPU; aumente `stride`, reduza duração, ou use GPU |

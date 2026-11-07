// Infraestrutura do Monitor Clínico Multimodal (escopo: resource group).
//
// Recursos:
//   - Log Analytics Workspace          (logs do Container Apps)
//   - Azure Container Registry         (imagem Docker; pull via managed identity, sem usuário admin)
//   - User-assigned Managed Identity   (+ role AcrPull no ACR)
//   - Azure AI Speech                  (Speech to Text)
//   - Azure AI Language                (sentimento, frases-chave, entidades)
//   - Container Apps Environment + Container App (Streamlit na porta 8501)
//
// Deploy em duas fases (ver infra/deploy.ps1 | deploy.sh):
//   1) containerImage vazio  -> sobe tudo com uma imagem placeholder (ACR precisa existir antes do build)
//   2) containerImage = 'hospital-monitor:<tag>' -> aponta o app para a imagem construída no ACR

targetScope = 'resourceGroup'

@description('Prefixo curto dos recursos (minúsculas e números).')
@minLength(3)
@maxLength(12)
param namePrefix string = 'hospmon'

@description('Nome do ambiente (dev, hml, prd).')
param environmentName string = 'dev'

@description('Região dos recursos.')
param location string = resourceGroup().location

@description('Imagem no ACR no formato repositorio:tag. Vazio = imagem placeholder (fase 1).')
param containerImage string = ''

@description('SKU do Azure AI Speech (F0 = gratuito, 1 por assinatura).')
@allowed(['F0', 'S0'])
param speechSku string = 'S0'

@description('SKU do Azure AI Language (F0 = gratuito, 1 por assinatura).')
@allowed(['F0', 'S'])
param languageSku string = 'S'

@description('Webhook opcional (Teams/Slack/Logic App) para disparo de alertas.')
@secure()
param alertWebhookUrl string = ''

@description('Réplicas mínima e máxima do Container App.')
param minReplicas int = 1
param maxReplicas int = 2

var suffix = uniqueString(resourceGroup().id)
var baseName = '${namePrefix}-${environmentName}'
var acrName = take('${namePrefix}${environmentName}${suffix}', 50)
var placeholder = empty(containerImage)
var image = placeholder
  ? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
  : '${acr.properties.loginServer}/${containerImage}'
var targetPort = placeholder ? 80 : 8501
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

var tags = {
  project: 'tech-challenge-fase4'
  environment: environmentName
  managedBy: 'bicep'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${baseName}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${baseName}'
  location: location
  tags: tags
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

resource speech 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: 'speech-${baseName}-${suffix}'
  location: location
  tags: tags
  kind: 'SpeechServices'
  sku: { name: speechSku }
  properties: {
    customSubDomainName: 'speech-${baseName}-${suffix}'
    publicNetworkAccess: 'Enabled'
  }
}

resource language 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: 'lang-${baseName}-${suffix}'
  location: location
  tags: tags
  kind: 'TextAnalytics'
  sku: { name: languageSku }
  properties: {
    customSubDomainName: 'lang-${baseName}-${suffix}'
    publicNetworkAccess: 'Enabled'
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${baseName}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var baseSecrets = [
  { name: 'speech-key', value: speech.listKeys().key1 }
  { name: 'language-key', value: language.listKeys().key1 }
]
var webhookSecrets = empty(alertWebhookUrl) ? [] : [{ name: 'alert-webhook-url', value: alertWebhookUrl }]

var baseEnv = [
  { name: 'AZURE_SPEECH_KEY', secretRef: 'speech-key' }
  { name: 'AZURE_SPEECH_REGION', value: location }
  { name: 'AZURE_SPEECH_LANGUAGE', value: 'pt-BR' }
  { name: 'AZURE_LANGUAGE_ENDPOINT', value: language.properties.endpoint }
  { name: 'AZURE_LANGUAGE_KEY', secretRef: 'language-key' }
  { name: 'MODELS_DIR', value: '/app/models' }
]
var webhookEnv = empty(alertWebhookUrl) ? [] : [{ name: 'ALERT_WEBHOOK_URL', secretRef: 'alert-webhook-url' }]

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${baseName}'
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  dependsOn: [acrPull]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
        // Streamlit usa websocket por sessão: mantém o usuário na mesma réplica.
        stickySessions: { affinity: 'sticky' }
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: concat(baseSecrets, webhookSecrets)
    }
    template: {
      containers: [
        {
          name: 'web'
          image: image
          env: concat(baseEnv, webhookEnv)
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-concurrency'
            http: { metadata: { concurrentRequests: '20' } }
          }
        ]
      }
    }
  }
}

output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output containerAppName string = app.name
output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output speechEndpoint string = speech.properties.endpoint
output languageEndpoint string = language.properties.endpoint

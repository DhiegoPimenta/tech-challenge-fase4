// Receptor de webhook SÓ PARA TESTE: imprime nos logs tudo que receber via POST.
// Usa a imagem oficial python:3.11-slim com um servidor HTTP de poucas linhas (sem código de terceiros).
//
// Atenção: o endpoint é público e anônimo. Use só durante o teste e apague depois:
//   az containerapp delete -g rg-hospital-monitor -n ca-webhook-sink --yes
//
// Deploy:
//   az deployment group create -g rg-hospital-monitor -f infra/test/webhook-sink.bicep
// Ver o que chegou:
//   az containerapp logs show -g rg-hospital-monitor -n ca-webhook-sink --type console --tail 30

targetScope = 'resourceGroup'

param location string = resourceGroup().location
param environmentName string = 'cae-hospmon-dev'

var serverCode = '''
import http.server

class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        print('WEBHOOK_RECEBIDO ' + self.rfile.read(n).decode('utf-8', 'replace'), flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'sink ok')

    def log_message(self, *args):
        pass

http.server.HTTPServer(('0.0.0.0', 8080), H).serve_forever()
'''

resource env 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

resource sink 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-webhook-sink'
  location: location
  tags: { purpose: 'test-only' }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'sink'
          image: 'python:3.11-slim'
          command: ['python', '-c', serverCode]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output sinkUrl string = 'https://${sink.properties.configuration.ingress.fqdn}'

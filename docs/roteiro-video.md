# Roteiro do vídeo (até 15 min)

Upload no YouTube ou Vimeo (público ou não listado). Tenha prontos antes de gravar:

* App publicado no Azure (URL) **e** o Portal Azure aberto no resource group;
* 1 vídeo curto de agachamento/caminhada (10–30 s) — ex.: gravado por você;
* 1 áudio de 20–40 s falando sintomas em português (use o texto de exemplo da aba Áudio);
* Webhook de teste (Teams/Slack/webhook.site) configurado em `ALERT_WEBHOOK_URL`.

| Tempo | Cena | O que mostrar / falar |
|---|---|---|
| 0:00–1:30 | Contexto | Desafio (hospital, dados multimodais), objetivo e diagrama da [arquitetura](arquitetura.md). |
| 1:30–3:30 | **Infra Azure** | Portal: resource group com ACR, Container Apps, Speech, Language, Log Analytics, managed identity. Abrir `infra/main.bicep` e destacar: sem admin no ACR, secrets, deploy em 2 fases. Mostrar `deploy.ps1`. |
| 3:30–6:30 | **Vídeo** | Aba Vídeo → enviar clipe → escolher perfil → analisar. Mostrar gráfico de ângulos, evento detectado, quadro anotado com esqueleto. Mostrar ROI com objeto (tesoura) se tiver. |
| 6:30–9:30 | **Áudio** | Enviar áudio → características vocais → **Transcrever com Azure Speech** → sentimento/frases-chave (Azure AI Language) → termos críticos e indicadores. No Portal, mostrar métricas de uso dos serviços. |
| 9:30–12:00 | **Anomalias** | Sinais vitais (gráfico com taquicardia/dessaturação marcadas, episódios), prescrições (salto de dose/interação), movimentação (imobilidade/queda). Explicar regras + z-score + Isolation Forest. |
| 12:00–14:00 | **Alerta à equipe** | Aba Alertas: central consolidada com os alertas das cinco fontes → **enviar ao webhook** → mostrar a mensagem chegando → baixar o relatório. |
| 14:00–15:00 | Fechamento | Resultados, limitações (ilustrativo, sem validação clínica), próximos passos (correlação entre modalidades, persistência, GPU). Log do Container App ao vivo, se couber. |

Dicas: grave em 1080p, aumente o zoom do navegador (125%), deixe as chaves fora do enquadramento
(não abra a tela de *Keys* do Portal) e rode a demonstração uma vez antes para aquecer o container.

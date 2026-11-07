# Monitor Clínico Multimodal — Tech Challenge Fase 4 (IADT)


### ▶️ [Assistir ao vídeo de demonstração](https://youtu.be/ECQEFq01__g) · 🌐 [Abrir a aplicação no Azure](https://ca-hospmon-dev.graymushroom-60baf176.eastus2.azurecontainerapps.io/) · 💻 [Repositório](https://github.com/DhiegoPimenta/tech-challenge-fase4)

> A aplicação roda em uma assinatura de teste do Azure e escala a zero quando fica parada: o primeiro acesso
> pode levar de 10 a 60 segundos. O ambiente pode ser desligado após a avaliação; nesse caso, use o vídeo ou
> reproduza com o [passo a passo de deploy](docs/deploy-azure.md). Para testar, use os arquivos de
> [`tests/manual/`](tests/manual) seguindo o [guia de teste](docs/guia-de-teste.md).

Aplicação **Streamlit** que funde **vídeo, áudio e texto/séries temporais** para identificar sinais
precoces de risco em pacientes e alertar a equipe médica. Roda localmente, em Docker e no
**Azure Container Apps**, com infraestrutura como código em **Bicep**.

> Projeto acadêmico. Os alertas são heurísticas/modelos de apoio à decisão e **não substituem avaliação clínica**.
> Os dados das demonstrações são sintéticos, com anomalias injetadas em posições conhecidas. Também foram usados
> 53 registros públicos e anonimizados do PhysioNet (BIDMC) para ver o comportamento em dados reais
> ([relatório técnico, seção 5.5](docs/relatorio-tecnico.md)). Não há dados identificáveis de pacientes.

## O que o sistema faz

| Modalidade | Entrada | Técnica | Saída |
|---|---|---|---|
| **Vídeo** | Fisioterapia / procedimento gravado | YOLOv8-pose (17 keypoints → ângulos, tronco, assimetria, velocidade), YOLOv8 (objetos em área crítica), caixa da pessoa (queda) | Eventos com tempo, severidade e quadro anotado |
| **Áudio** | Gravação da consulta | Características vocais (pausas, f0, jitter) + **Azure Speech to Text** + **Azure AI Language** + dicionário de termos críticos | Indicadores de fadiga/dispneia/disartria, sentimento, sintomas críticos |
| **Sinais vitais** | CSV `timestamp,hr,sbp,dbp,spo2` | Regras clínicas + z-score robusto (MAD) + Isolation Forest | Episódios anômalos |
| **Prescrições** | CSV `timestamp,drug,dose_mg,frequency_per_day` | Salto de dose, dose máxima, interações | Alertas de prescrição |
| **Movimentação** | CSV `timestamp,activity` | Imobilidade prolongada, picos, queda suspeita | Episódios |
| **Alertas** | Tudo acima | Central única + webhook + relatório Markdown | Notificação da equipe |

Detalhes: [arquitetura](docs/arquitetura.md) · [relatório técnico](docs/relatorio-tecnico.md) ·
[deploy no Azure](docs/deploy-azure.md) · [mapa de testes](docs/mapa-de-testes.md).

## Estrutura

```
app/                      # UI Streamlit (streamlit_app.py + views/)
src/hospital_monitor/     # lógica de negócio (sem dependência de UI)
  anomalies/              #   vitals, prescriptions, movement, episodes
  audio/                  #   voice_features, speech (Azure), text_analytics (Azure), clinical_terms
  video/                  #   pose_metrics (puro), detector (YOLOv8)
  alerts.py pipelines.py report.py synthetic.py config.py
infra/                    # Bicep + scripts de deploy (PowerShell e bash)
tests/                    # pytest (não exige GPU, Azure nem vídeo)
docs/                     # arquitetura, relatório, deploy, roteiro
Dockerfile  .github/workflows/
```

## Rodando localmente

Requer Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install torch torchvision     # CPU; para GPU siga pytorch.org
pip install -r requirements-dev.txt
cp .env.example .env              # opcional: preencha as chaves Azure
streamlit run app/streamlit_app.py
```

Sem chaves Azure o app funciona em **modo offline**: a transcrição é colada manualmente e a análise
de texto usa o léxico local. Na 1ª análise de vídeo os pesos YOLOv8 (~25 MB) são baixados.

Para testar sem dados próprios: na **Visão geral** clique em *Rodar demonstração*; nas abas de
anomalias use os dados sintéticos; para vídeo/áudio use clipes curtos (veja
[datasets](docs/relatorio-tecnico.md#datasets)).

## Testes

```bash
pytest -q
ruff check src app tests
```

Os testes cobrem a lógica de detecção (séries, prescrições, geometria de pose, queda, características
vocais, termos críticos, alertas e relatório). Integrações Azure e YOLO são isoladas em módulos
com importação tardia e não são exercitadas em CI.

## Docker

```bash
docker build -t hospital-monitor .
docker run --rm -p 8501:8501 --env-file .env hospital-monitor
```

## Deploy no Azure

```powershell
az login
./infra/deploy.ps1 -ResourceGroup rg-hospital-monitor -Location brazilsouth
```

(`./infra/deploy.sh` no Linux/macOS). O script cria Resource Group, ACR, Log Analytics, Speech,
Language, Managed Identity e Container Apps; builda a imagem com `az acr build` e publica.
Passo a passo, custos e limpeza em [docs/deploy-azure.md](docs/deploy-azure.md).

## Variáveis de ambiente

| Variável | Uso |
|---|---|
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `AZURE_SPEECH_LANGUAGE` | Azure AI Speech |
| `AZURE_LANGUAGE_ENDPOINT`, `AZURE_LANGUAGE_KEY` | Azure AI Language |
| `ALERT_WEBHOOK_URL` | Webhook opcional (Teams/Slack/Logic App) |
| `MODELS_DIR` | Pasta dos pesos YOLOv8 |

No Azure, as chaves são injetadas como *secrets* do Container App pelo Bicep (nunca no código).

## Requisitos do desafio × onde estão

| Requisito | Implementação |
|---|---|
| Análise de vídeo + relatório automático | `video/`, aba **Vídeo**, relatório em **Alertas** |
| Análise de áudio (Speech to Text, Text Analytics) | `audio/`, aba **Áudio** |
| Anomalias em vitais, prescrições e movimentação | `anomalies/`, aba **Anomalias** |
| Alertas automáticos à equipe | `alerts.py`, aba **Alertas** (webhook) |
| Integração com serviços Azure | `infra/main.bicep`, `audio/speech.py`, `audio/text_analytics.py` |
| Relatório técnico | `docs/relatorio-tecnico.md` |

## Limitações conhecidas

* Em vez do OpenPose original (Caffe, pesado de empacotar) usamos **YOLOv8-pose**, que entrega os mesmos 17 keypoints COCO. Justificativa em [docs/arquitetura.md](docs/arquitetura.md#decisões-técnicas).
* Limiares clínicos, tabela de doses e de interações são **ilustrativos** e precisam de validação clínica.
* Indicadores vocais são heurísticos (sem modelo treinado em voz patológica).
* O estado dos alertas vive na sessão do Streamlit; para histórico persistente, ligar a um banco (Cosmos DB/Table Storage).

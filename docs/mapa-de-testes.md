# Mapa de testes manuais

Roteiro para validar **todas as funcionalidades** do app (local ou no Azure) com os arquivos de
[`tests/manual/`](../tests/manual). A coluna **Observado** registra o resultado real obtido no app
publicado no Azure Container Apps durante a validação; `—` = ainda não executado.

Os arquivos são regeneráveis:

```bash
python scripts/make_test_data.py                                     # CSVs + vídeo sintético
powershell -ExecutionPolicy Bypass -File scripts/make_test_audio.ps1 # áudios (voz pt-BR do Windows)
```

## Arquivos de teste

| Arquivo | Tipo | Conteúdo |
|---|---|---|
| `vitais_com_anomalias.csv` | CSV, 480 min | FC/PA/SpO₂ com 4 anomalias injetadas (pico isolado de FC às 10:00, taquicardia 11:20–11:34, dessaturação 13:00–13:11, pico de PA sistólica 14:20–14:25) |
| `vitais_normais.csv` | CSV | Mesma série sem anomalias |
| `prescricoes_com_anomalias.csv` | CSV | Dipirona (dose dobra e passa do máximo), tramadol ×4, varfarina + ibuprofeno |
| `prescricoes_normais.csv` | CSV | Paracetamol e enalapril estáveis |
| `movimento_com_anomalias.csv` | CSV, 2 dias | 4 h de imobilidade (dia 1, 13:00) e queda suspeita (dia 2, 10:00) |
| `movimento_normal.csv` | CSV | Rotina normal com sono noturno |
| `invalido_sem_timestamp.csv` | CSV | Sem a coluna `timestamp` (teste de erro) |
| `consulta_sintomas_criticos.wav` | áudio, 19,5 s | Paciente relata cansaço, falta de ar, tontura, dor no peito |
| `consulta_normal.wav` | áudio, 14,6 s | Consulta tranquila, sem queixas |
| `consulta_fala_lenta_pausas.wav` | áudio, 64 s | Fala muito lenta com pausas de ~3,5 s |
| `video_sem_pessoa.mp4` | vídeo, 8 s | Retângulo em movimento, **sem pessoa** (testa o caminho "fora de quadro") |
| `pessoa_em_pe.mp4` | vídeo, 6 s *(gerado, não versionado)* | Pessoas reais em pé, de corpo inteiro, paradas |
| `pessoa_inclinada.mp4` | vídeo, 6 s *(gerado)* | Mesma cena girada 30° (tronco inclinado) |
| `queda_simulada.mp4` | vídeo, 6 s *(gerado)* | 3 s em pé + 3 s com a cena girada 90° (pessoa "deitada") |

Os três vídeos com pessoa saem de uma **foto real** do pacote `ultralytics` (`scripts/make_test_video.py`):
o YOLOv8 detecta as pessoas de verdade, mas o "movimento" é simulado (foto girada). Não são versionados porque a
foto vem de repositório AGPL; gere com `python scripts/make_test_video.py`. Para validar **movimento real**
(agachamento de verdade), ainda vale gravar um clipe seu (caso V-7).

## Passo a passo

### 0. Visão geral

| ID | Passo | Esperado | Observado |
|---|---|---|---|
| G-1 | Abrir a URL | Título "Monitor clínico multimodal" e diagrama do fluxo | OK |
| G-2 | Ver "Integrações Azure" | Speech **conectado**, Language **conectado**, Webhook "não configurado" | OK |
| G-3 | Clicar **Rodar demonstração de séries temporais** | "11 alertas gerados" (4 vitais + 5 prescrições + 2 movimento); barra lateral: 8 críticos e 3 alertas | OK (11 alertas; 8 críticos / 3 alertas) |

### 1. Anomalias → Sinais vitais

Escolha **Enviar CSV** e envie o arquivo.

| ID | Arquivo | Esperado | Observado |
|---|---|---|---|
| A-1 | `vitais_normais.csv` | **0 episódios** (série limpa) | 0 episódios |
| A-2 | `vitais_com_anomalias.csv` | **4 episódios, todos críticos**: hr 10:00, hr 11:20–11:34, SpO₂ 13:00–13:11, PA 14:20–14:25 | 4 episódios; 4 críticos; picos nos horários esperados |
| A-3 | Gráfico → trocar o sinal (FC, PA, SpO₂) | Pontos vermelhos (crítico) e laranja (alerta) sobre a linha | OK (FC) |
| A-4 | `invalido_sem_timestamp.csv` | Mensagem "CSV inválido: faltam as colunas ['timestamp']…", **sem traceback** | OK (após correção) |
| A-5 | Abrir *Parâmetros de detecção* e subir o limiar do z-score para 8 | Menos episódios que A-2 | — |

### 2. Anomalias → Prescrições

| ID | Arquivo | Esperado | Observado |
|---|---|---|---|
| P-1 | `prescricoes_normais.csv` | "0 anomalia(s) na prescrição" | OK (0) |
| P-2 | `prescricoes_com_anomalias.csv` | **5 anomalias**: dipirona 2000→4000 mg/dia (crítico), dipirona 6000 mg > máximo (crítico), dipirona ×1,5 (alerta), tramadol ×4 (crítico), interação varfarina + ibuprofeno (alerta). Enalapril **não** aparece | OK (5) |

### 3. Anomalias → Movimentação

| ID | Arquivo | Esperado | Observado |
|---|---|---|---|
| M-1 | `movimento_normal.csv` | Nenhum evento | OK (tabela vazia; curva com sono noturno) |
| M-2 | `movimento_com_anomalias.csv` | **2 eventos**: `imobilidade` 01/01 13:00–16:45 ("4,0 h", alerta) e `queda_suspeita` 02/01 10:00 (crítico); faixas coloridas no gráfico | OK |

### 4. Áudio (Azure Speech + Azure AI Language)

Na aba **Áudio**: enviar o arquivo → *Transcrever com Azure Speech* → ler os blocos 1 a 4.
Áudios longos levam ~o tempo do áudio para transcrever (reconhecimento em tempo quase real).

| ID | Arquivo | Esperado | Observado |
|---|---|---|---|
| U-1 | `consulta_sintomas_criticos.wav` | Confiança ~80–90%; análise "Fonte: **azure**"; sentimento **negativo**; termos críticos: dor no peito, falta de ar, tontura, cansado, fraco; 6 alertas | Confiança 86%; fonte azure; negativo; os 5 termos; 6 alertas |
| U-2 | `consulta_normal.wav` | Sentimento positivo/neutro, **0 termos críticos**, 0 alertas | Confiança 75%; positivo; 0 alertas |
| U-3 | `consulta_fala_lenta_pausas.wav` | Silêncio **81%**, pausa longa **8,8 s**, "Fala lenta (9 palavras/min)", termo "cansado", sentimento negativo; 4 alertas | Todos os itens acima; confiança 84%; 4 alertas |
| U-4 | Trocar de áudio após U-1 | Confiança e palavras/min **do novo arquivo** (não os do anterior) | Defeito encontrado (valores antigos persistiam) → corrigido e reverificado: ao trocar o arquivo, confiança e palavras/min somem |
| U-5 | Sem transcrever, clicar **Usar texto de exemplo** | Análise de texto roda sobre o exemplo; termos críticos listados | OK (fonte azure; 5 termos críticos; 6 alertas) |
| U-6 | *...ou grave agora* (microfone) | Grava e analisa como os demais | Parcial: **microfone simulado** (fala sintética injetada no `getUserMedia`): gravou 6,0 s; f0 141 Hz (sinal de 140 Hz), 40 pausas/min, voz monótona, 2 alertas. O microfone físico e a permissão do navegador não foram exercitados |

### 5. Vídeo (YOLOv8)

| ID | Arquivo / ajuste | Esperado | Observado |
|---|---|---|---|
| V-1 | `video_sem_pessoa.mp4`, perfil *Agachamento* | 8,0 s, 40 quadros, **1 evento** "Paciente não detectado por 8,0 s" (alerta) | OK |
| V-2 | Conferir a central (aba Alertas) | Alerta "Fora de quadro" de origem *Vídeo* | OK |
| V-3 | `pessoa_em_pe.mp4`, perfil *Agachamento* | Pessoas detectadas (`person`, `bus` no gráfico de objetos), ângulos plotados, **0 eventos** | OK (20 quadros; 0 eventos) |
| V-4 | `pessoa_inclinada.mp4`, perfil **Marcha / caminhada** | Evento de limite: `trunk_tilt` fora de [0°, 20°] | OK (alerta; desvio de 13° ≈ tronco a 33° para uma foto girada em 30°) |
| V-5 | `queda_simulada.mp4` | Aos 3,0 s: evento **crítico** "Queda suspeita" (+ tronco fora do limite) | OK (2 eventos críticos aos 3,0 s; tronco a 68° de desvio) |
| V-6 | `pessoa_em_pe.mp4` + *Definir área crítica* (H 0,60–1,00; V 0,50–1,00) + objetos `person` | Evento crítico "Objeto 'person' dentro da área crítica"; quadro anotado com esqueleto, caixas e o retângulo vermelho da área | OK (1 evento crítico; quadro com 3 pessoas, confiança 0,83–0,87) |
| V-7 | **Seu clipe** de agachamento real (10–30 s, corpo inteiro, câmera parada), perfil *Agachamento* | Ângulos de joelho variando; eventos de limite/assimetria/velocidade se houver desvio | — (precisa de filmagem real) |

### 6. Alertas e relatório

| ID | Passo | Esperado | Observado |
|---|---|---|---|
| L-1 | Após U-3 e V-1, abrir a aba | Central com alertas de **Vídeo** e **Áudio**, ordenados por severidade | OK (5 alertas: 1 vídeo + 4 áudio) |
| L-2 | Filtro "Mostrar a partir de" = CRÍTICO | Só os críticos | OK (8 linhas) |
| L-3 | Preencher paciente e observações → **Baixar relatório (Markdown)** | Relatório com resumo e tabelas por fonte (visto na **Pré-visualização** da tela, que usa o mesmo texto do download; o clique em *Baixar* não foi exercitado para não gravar arquivo na máquina) | OK (pré-visualização) |
| L-4 | **Limpar alertas** | Contadores zeram e aparece "Nenhum alerta ainda" | OK |
| L-5 | `ALERT_WEBHOOK_URL` configurado + **Enviar alertas** | "N alerta(s) enviados" e a mensagem chega ao destino | OK: receptor de teste no próprio Azure (`infra/test/webhook-sink.bicep`) registrou o POST com os **13 alertas** e o payload completo; a interface mostrou "13 alerta(s) enviados" |

### 7. Infraestrutura

| ID | Passo | Esperado | Observado |
|---|---|---|---|
| I-1 | `GET /_stcore/health` | HTTP 200 | OK |
| I-2 | Portal Azure → resource group `rg-hospital-monitor` | ACR, Container Apps (env + app), Speech, Language, Log Analytics, Managed Identity | OK |
| I-3 | Ficar ~5 min sem acessar e reabrir | Escala a zero; 1º acesso demora alguns segundos e volta | — |
| I-4 | `az containerapp logs show -g rg-hospital-monitor -n ca-hospmon-dev` | Logs do Streamlit sem exceções durante os testes acima | OK (nenhuma exceção) |

## Testes automatizados (sem Azure)

```bash
pip install -r requirements-dev.txt
pytest -q          # 41 testes
ruff check src app tests scripts
```

Cobrem detecção de séries, prescrições, movimento, geometria de pose, queda, características vocais,
termos críticos, alertas, relatório e a **consistência das chamadas das telas** (`tests/test_view_calls.py`).

## Como repetir o teste do webhook (sem serviço de terceiros)

O receptor de teste é um Container App mínimo, na mesma assinatura, que imprime nos logs o que receber.
O endpoint é **público e anônimo**: use só durante o teste e apague depois.

```bash
# 1) criar o receptor e pegar a URL
az deployment group create -g rg-hospital-monitor -f infra/test/webhook-sink.bicep --query properties.outputs.sinkUrl.value -o tsv

# 2) apontar o app para ele (secret + variável de ambiente)
az containerapp secret set -g rg-hospital-monitor -n ca-hospmon-dev --secrets "alert-webhook-url=<URL>/hook"
az containerapp update   -g rg-hospital-monitor -n ca-hospmon-dev --set-env-vars "ALERT_WEBHOOK_URL=secretref:alert-webhook-url"

# 3) no app: Visão geral -> Rodar demonstração -> Alertas -> Enviar alertas ao webhook
# 4) conferir o que chegou
az containerapp logs show -g rg-hospital-monitor -n ca-webhook-sink --type console --tail 20 --format text

# 5) limpeza
az containerapp delete -g rg-hospital-monitor -n ca-webhook-sink --yes
az containerapp update -g rg-hospital-monitor -n ca-hospmon-dev --remove-env-vars ALERT_WEBHOOK_URL
```

Em produção, troque o receptor por um webhook de entrada do Teams/Slack ou um Logic App.

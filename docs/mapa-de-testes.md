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

> **Falta um arquivo seu:** para exercitar postura/queda é preciso um vídeo de **pessoa real** (10–30 s,
> corpo inteiro, câmera parada). Veja o caso V-3.

## Passo a passo

### 0. Visão geral

| ID | Passo | Esperado | Observado |
|---|---|---|---|
| G-1 | Abrir a URL | Título "Monitor clínico multimodal" e diagrama do fluxo | OK |
| G-2 | Ver "Integrações Azure" | Speech **conectado**, Language **conectado**, Webhook "não configurado" | OK |
| G-3 | Clicar **Rodar demonstração de séries temporais** | "13 alertas gerados" (6 vitais + 5 prescrições + 2 movimento); barra lateral: 8 críticos e 5 alertas | OK (13 alertas; 8 críticos / 5 alertas) |

### 1. Anomalias → Sinais vitais

Escolha **Enviar CSV** e envie o arquivo.

| ID | Arquivo | Esperado | Observado |
|---|---|---|---|
| A-1 | `vitais_normais.csv` | ≤ 2 episódios leves, **0 críticos** | 2 episódios (SpO₂, leves) |
| A-2 | `vitais_com_anomalias.csv` | **6 episódios, 4 críticos**: hr 10:00, hr 11:20–11:34, SpO₂ 13:00–13:11, PA 14:20–14:25, mais 2 leves | 6 episódios; 4 críticos; picos nos horários esperados |
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
| M-1 | `movimento_normal.csv` | Nenhum evento | — (coberto por teste automatizado) |
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
| U-5 | Sem transcrever, clicar **Usar texto de exemplo** | Análise de texto roda sobre o exemplo; termos críticos listados | — |
| U-6 | *...ou grave agora* (microfone) | Grava e analisa como os demais | — (exige microfone/permissão do navegador) |

### 5. Vídeo (YOLOv8)

| ID | Passo | Esperado | Observado |
|---|---|---|---|
| V-1 | `video_sem_pessoa.mp4`, perfil *Agachamento*, stride 3 | 8,0 s, 40 quadros, **1 evento** "Paciente não detectado por 8,0 s" (alerta) | OK |
| V-2 | Conferir a central (aba Alertas) | Alerta "Fora de quadro" de origem *Vídeo* | OK |
| V-3 | **Seu vídeo** de agachamento/caminhada, perfil correspondente | Gráfico de ângulos de joelho/tronco; eventos de limite, assimetria ou movimento brusco quando houver; quadro anotado com esqueleto dentro de cada evento | — (precisa de vídeo real) |
| V-4 | Vídeo com pessoa **caindo/deitando** | Evento crítico "Queda suspeita" | — |
| V-5 | *Área crítica (ROI)* ligada, com objeto "scissors"/"knife" dentro | Evento crítico "Objeto 'scissors' dentro da área crítica" | — |
| V-6 | Mudar o perfil (Marcha, Livre) no mesmo vídeo | Eventos de assimetria só no perfil Agachamento | — |

### 6. Alertas e relatório

| ID | Passo | Esperado | Observado |
|---|---|---|---|
| L-1 | Após U-3 e V-1, abrir a aba | Central com alertas de **Vídeo** e **Áudio**, ordenados por severidade | OK (5 alertas: 1 vídeo + 4 áudio) |
| L-2 | Filtro "Mostrar a partir de" = CRÍTICO | Só os críticos | — |
| L-3 | Preencher paciente e observações → **Baixar relatório (Markdown)** | Arquivo `relatorio_<paciente>.md` com resumo e tabelas por fonte | — (cobertura por teste automatizado) |
| L-4 | **Limpar alertas** | Contadores zeram | — |
| L-5 | Configurar `ALERT_WEBHOOK_URL` (ex.: um endereço de teste de webhook) e clicar **Enviar alertas** | "N alerta(s) enviados" e a mensagem chega ao destino | — (sem webhook configurado) |

### 7. Infraestrutura

| ID | Passo | Esperado | Observado |
|---|---|---|---|
| I-1 | `GET /_stcore/health` | HTTP 200 | OK |
| I-2 | Portal Azure → resource group `rg-hospital-monitor` | ACR, Container Apps (env + app), Speech, Language, Log Analytics, Managed Identity | OK |
| I-3 | Ficar ~5 min sem acessar e reabrir | Escala a zero; 1º acesso demora alguns segundos e volta | — |
| I-4 | `az containerapp logs show -g rg-hospital-monitor -n ca-hospmon-dev` | Logs do Streamlit sem exceções durante os testes acima | — |

## Testes automatizados (sem Azure)

```bash
pip install -r requirements-dev.txt
pytest -q          # 37 testes
ruff check src app tests scripts
```

Cobrem detecção de séries, prescrições, movimento, geometria de pose, queda, características vocais,
termos críticos, alertas, relatório e a **consistência das chamadas das telas** (`tests/test_view_calls.py`).

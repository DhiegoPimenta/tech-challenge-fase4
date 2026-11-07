# Relatório técnico — Tech Challenge Fase 4

> Seções 1–4 descrevem o que está implementado. A seção 5 traz os resultados medidos no app publicado no
> Azure (roteiro e resultados completos em [mapa-de-testes.md](mapa-de-testes.md)).

## 1. Fluxo multimodal

1. **Entrada** — vídeo (mp4/mov/avi), áudio (wav/flac/ogg ou gravação no navegador) e dados tabulares (CSV).
2. **Análise por modalidade** — cada módulo produz *eventos* com tempo, severidade e justificativa.
3. **Fusão em nível de decisão** — eventos viram `Alert` e são consolidados na `AlertCenter` (ordenação por severidade, substituição por fonte ao reanalisar).
4. **Resposta** — painel, relatório Markdown e webhook (Teams/Slack/Logic App) para a equipe médica.

Diagrama em [arquitetura.md](arquitetura.md).

## 2. Modelos e técnicas por tipo de dado

### 2.1 Vídeo (`src/hospital_monitor/video`)

| Etapa | Modelo/técnica |
|---|---|
| Postura | **YOLOv8n-pose** (Ultralytics): 17 keypoints COCO por pessoa; usa-se a maior pessoa do quadro |
| Objetos / áreas críticas | **YOLOv8n** (COCO): objetos da lista de observação com centro dentro da ROI definida geram alerta |
| Métricas | Ângulos de joelho, cotovelo e quadril; inclinação do tronco; assimetria esquerda/direita; velocidade angular |
| Eventos | Fora do intervalo seguro do perfil (agachamento, marcha, livre), assimetria acima do limite, movimento brusco (≥ 2 amostras), paciente fora de quadro (≥ 2 s), queda suspeita (proporção largura/altura da caixa: de < 0,8 para > 1,2 em ≤ 1,5 s), objeto em área crítica |
| Relatório | Eventos com tempo, severidade, valor e quadro anotado mais próximo |

Keypoints com confiança < 0,4 são descartados (ângulo vira NaN) para evitar falsos positivos.
`pose_metrics.py` é puro NumPy/pandas e totalmente testado sem vídeo.

**Sobre OpenPose:** a especificação cita OpenPose; adotamos YOLOv8-pose por entregar os mesmos
keypoints COCO com instalação via `pip` e um único runtime com o YOLOv8 de objetos (ver
[decisões técnicas](arquitetura.md#decisões-técnicas)).

### 2.2 Áudio (`src/hospital_monitor/audio`)

| Etapa | Modelo/técnica |
|---|---|
| Transcrição | **Azure AI Speech — Speech to Text** (reconhecimento contínuo, saída detalhada com confiança por segmento, pt-BR) |
| Texto | **Azure AI Language**: `analyze_sentiment`, `extract_key_phrases`, `recognize_entities` (pt) |
| Termos críticos | Dicionário clínico pt-BR insensível a acentos/caixa, com severidade por categoria (respiratório, cardiovascular, neurológico, sangramento…) |
| Sinais vocais | Proporção de silêncio e pausas (limiar de −30 dB do nível típico de fala), energia (dB) e sua variação, **f0 por autocorrelação** (75–400 Hz), **jitter** aproximado, palavras/min |
| Indicadores | Fadiga (silêncio alto, voz monótona), dificuldade respiratória (fala entrecortada, muitas pausas), possível disartria/rouquidão (jitter elevado), fala lenta |

Os limiares (`DEFAULT_THRESHOLDS`) são heurísticos e configuráveis; não há modelo treinado em voz
patológica, logo os indicadores são **apoio**, não diagnóstico.

### 2.3 Anomalias (`src/hospital_monitor/anomalies`)

| Dado | Técnica |
|---|---|
| Sinais vitais (FC, PA, SpO₂) | (1) regras de limite de aviso/crítico; (2) **z-score robusto** em janela móvel (mediana/MAD, `0,6745·(x−med)/MAD`); (3) **Isolation Forest** multivariado sobre valores e derivadas. União por (instante, sinal) mantendo a maior severidade; agrupamento em *episódios* |
| Prescrições | Razão da dose diária vs. prescrição anterior (≥ 1,5× / ≤ 0,5× = alerta; ≥ 2× / ≤ 0,25× = crítico), excesso da dose máxima de referência e pares de fármacos de risco numa janela de 7 dias |
| Movimentação | Imobilidade diurna prolongada (≥ 3 h alerta, ≥ 6 h crítico), picos por z-score robusto e **queda suspeita** (pico seguido de imobilidade) |

## 3. Alertas

`Alert(source, severity ∈ {INFO, ALERTA, CRÍTICO}, title, message, when)`. Ao reanalisar uma fonte,
seus alertas anteriores são substituídos. O webhook envia um resumo com os alertas ≥ ALERTA.

## 4. Infraestrutura e integração Azure

Bicep (`infra/main.bicep`): Container Apps (Streamlit), ACR com *managed identity*, Log Analytics,
Azure AI Speech e Azure AI Language, com chaves injetadas como *secrets*. Deploy em duas fases por
`infra/deploy.ps1|sh`. Detalhes em [deploy-azure.md](deploy-azure.md).

## 5. Resultados

### Datasets

* **Sinais vitais, prescrições e movimentação** — séries **sintéticas** geradas por `synthetic.py`, com anomalias injetadas em posições conhecidas. Isso permite conferir o acerto objetivamente. Foram usados 480 pontos de sinais vitais (1 por minuto), 2 dias de movimentação e 3 prescrições (arquivos em `tests/manual/`). O app aceita CSV `timestamp,hr,sbp,dbp,spo2`.
* **Sinais vitais reais (PhysioNet)** — os 53 registros do *BIDMC PPG and Respiration Dataset* (https://physionet.org/content/bidmc/1.0.0/, acesso aberto, licença ODC-By): pacientes de UTI, dados anonimizados, 1 amostra/s por ~8 min, com FC e SpO₂. Usados na seção 5.5 (25.361 pontos). Os dados sintéticos continuam sendo a única base com anomalias *rotuladas*.
* **Áudio** — três consultas simuladas, falando em português com a voz sintética do Windows (Microsoft Maria), e gravação pelo microfone no navegador: sintomas críticos (19,5 s), consulta normal (14,6 s) e fala lenta com pausas (64 s).
* **Vídeo** — quatro clipes de teste: um sem pessoa (retângulo em movimento) e três derivados de uma foto real com pessoas (em pé, inclinada em 30° e "queda" girada em 90°). O YOLOv8 detecta as pessoas de verdade, mas o movimento é simulado. Não houve ainda clipe de agachamento ou marcha reais.

### 5.1 Séries temporais (dados sintéticos, anomalias conhecidas)

Anomalias injetadas em `make_vitals()`: pico isolado de FC (10:00), taquicardia sustentada (11:20–11:34),
dessaturação (13:00–13:11) e pico hipertensivo (14:20–14:25). `make_prescriptions()`: dipirona com dose
dobrada e acima do máximo, tramadol ×4, interação varfarina + ibuprofeno. `make_movement()`: 4 h de
imobilidade (dia 1) e queda às 10:00 do dia 2.

Os testes automatizados (`tests/`) e a validação manual no app verificam que cada uma é detectada e que as
séries sem anomalia geram poucos alertas.

| Métrica | Valor |
|---|---|
| Episódios de sinais vitais com anomalias | 4, todos críticos e exatamente nos horários injetados (FC 10:00, FC 11:20–11:34, SpO₂ 13:00–13:11, PA 14:20–14:25) |
| Episódios na série limpa (`vitais_normais.csv`) | 0 |
| Alertas de prescrição | 5 (dipirona: dobra e excesso do máximo, e ×1,5; tramadol ×4; interação varfarina + ibuprofeno). A prescrição estável (enalapril) não alertou |
| Eventos de movimentação | 2 (imobilidade diurna de 13:00 a 16:45, alerta; queda suspeita às 10:00 do dia 2, crítico). Série normal: 0 eventos |
| Demonstração completa (botão da Visão geral) | 11 alertas: 4 de sinais vitais, 5 de prescrições e 2 de movimentação (8 críticos e 3 alertas) |

A taxa de falsos positivos caiu depois de dois ajustes: piso do MAD no z-score robusto e confirmação do
Isolation Forest por z-score local (>2,5). Antes disso a série limpa gerava 18 alertas.

### 5.2 Vídeo

| Vídeo | Perfil | Eventos | Resultado |
|---|---|---|---|
| `video_sem_pessoa.mp4` (8 s, 40 quadros) | Agachamento | 1 | "Paciente não detectado por 8,0 s" (alerta) |
| `pessoa_em_pe.mp4` | Agachamento | 0 | Pessoas detectadas, ângulos plotados, sem desvio |
| `pessoa_inclinada.mp4` | Marcha / caminhada | 1 | Tronco fora de [0°, 20°]: desvio de 13° (tronco a ~33° para uma foto girada em 30°) |
| `queda_simulada.mp4` | qualquer | 2 (críticos) | Queda suspeita aos 3,0 s (razão largura/altura passa de <0,8 para >1,2 em até 1,5 s) e tronco 68° fora do limite |
| `pessoa_em_pe.mp4` + área crítica (H 0,60–1,00; V 0,50–1,00) | Agachamento | 1 (crítico) | "Objeto 'person' dentro da área crítica", com esqueleto, caixas (confiança 0,83–0,87) e retângulo vermelho no quadro anotado |

Limite: o movimento desses clipes é simulado. A validação com agachamento ou marcha reais ainda precisa de filmagem.

### 5.3 Áudio

Valores medidos nos três arquivos de teste. Silêncio, pausas, f0 e jitter vêm do cálculo local em NumPy;
confiança, sentimento e termos vêm do Azure Speech e do Azure AI Language no app publicado.

| Áudio | Silêncio | Pausas/min | f0 / jitter | Palavras/min | Termos críticos | Sentimento (Azure) |
|---|---|---|---|---|---|---|
| `consulta_sintomas_criticos.wav` (19,5 s) | 10% | 6,1 | 189 Hz / 1,5% | n/d | 5: dor no peito, falta de ar, tontura, cansado, fraco | negativo (confiança da transcrição 86%) |
| `consulta_normal.wav` (14,6 s) | 10% | 4,1 | 185 Hz / 1,6% | n/d | 0 | positivo/neutro (confiança 75%) |
| `consulta_fala_lenta_pausas.wav` (64 s) | 81% (pausa mais longa 8,8 s) | 5,6 | 185 Hz / 1,0% | 9 | 1: cansado | negativo (confiança 84%) |

Alertas gerados: 6, 0 e 4, respectivamente. A voz é sintética, então f0 e jitter não representam um
paciente real. O microfone foi exercitado só com sinal simulado no navegador (f0 141 Hz para um tom de 140 Hz).

### 5.4 Exemplos de alertas gerados

A central da aba *Alertas* consolidou, na demonstração, 11 alertas de séries temporais (8 críticos, 3 alertas),
e depois somou os de áudio e vídeo. Todos foram enviados ao webhook de teste em um único POST
(`{"text": ..., "alerts": [...]}`), confirmado nos logs do receptor. Exemplos:

| Fonte | Severidade | Descrição (resumida) |
|---|---|---|
| Sinais vitais | CRÍTICO | Dessaturação de SpO₂ entre 13:00 e 13:11 |
| Prescrição | CRÍTICO | Dipirona acima da dose máxima diária |
| Prescrição | ALERTA | Interação varfarina + ibuprofeno |
| Movimentação | CRÍTICO | Queda suspeita no dia 2 às 10:00 |
| Vídeo | CRÍTICO | Queda suspeita aos 3,0 s |
| Áudio | ALERTA | Fala lenta (9 palavras/min) e pausa longa de 8,8 s |

Prova da entrega ao webhook (teste em 07/11/2026): ao clicar em *Enviar alertas* no app publicado, a tela mostrou
"11 alerta(s) enviados" e o receptor de teste (outro Container App) registrou em seus logs, às 22:13:31 UTC, uma
linha `WEBHOOK_RECEBIDO` com o JSON completo (11 alertas). Trecho do campo `text` recebido:

```
**11 alerta(s) clínico(s)**
- [CRÍTICO] Movimentação - Possível queda: pico de movimento seguido de imobilidade (02/01 10:00 - 11:00)
- [CRÍTICO] Prescrições - Prescrição de dipirona: aumento brusco da dose diária: 2000 mg -> 4000 mg (x2.00)
- [CRÍTICO] Prescrições - Prescrição de tramadol: aumento brusco da dose diária: 100 mg -> 400 mg (x4.00)
- [CRÍTICO] Prescrições - Prescrição de dipirona: dose diária de 6000 mg excede o máximo de referência (4000 mg)
- [CRÍTICO] Sinais vitais - Frequência cardíaca (bpm) fora do limite crítico ... valor de pico 160.0 (01/01 10:00 - 10:00)
- [CRÍTICO] Sinais vitais - Frequência cardíaca (bpm) fora do limite crítico ... valor de pico 139.2 (01/01 11:20 - 11:34)
```

Cada item de `alerts` traz `source`, `severity`, `title`, `message`, `when` e `details`.

O relatório Markdown completo é gerado pelo botão *Baixar relatório* da aba Alertas.

### 5.5 Sinais vitais reais (PhysioNet BIDMC)

Roteiro reproduzível: `python scripts/eval_physionet.py <pasta com os bidmc_*_Numerics.csv>`. Os arquivos não têm
rótulos de anomalia nem relógio, então o resultado mostra **o que o sistema marca em dados reais**, não
precisão e revocação. O script usa FC e SpO₂ (não há pressão arterial), monta o `timestamp` a partir de
2025-01-01 + segundos e agrupa pontos vizinhos com tolerância de 5 s (o padrão do app é 5 min, pensado para
1 amostra/min).

| Métrica (53 registros, 25.361 pontos) | Valor |
|---|---|
| Registros com episódio **crítico** | 4: SpO₂ de 83% (reg. 32), 84% (reg. 49) e 88% (reg. 22), e FC de até 139 bpm (reg. 25) |
| Registros com SpO₂ < 90% ou FC > 130 bpm (limiares críticos) | os mesmos 4: nenhum caso crítico foi perdido e nenhum foi inventado |
| Registros sem nenhum episódio | 22 |
| Episódios por registro | média 1,9 (máximo 14) |
| Pontos marcados | 6.312 (24,9%) |

**Leitura honesta do resultado:**

* Os críticos são clinicamente plausíveis, mas isso é em grande parte a regra de limiar clínico, não aprendizado.
* Os 24,9% de pontos marcados ainda são **muitos**, mas quase tudo vem da regra clínica: dos 6.312 pontos, 6.138
  são só da regra de limiar (por exemplo, SpO₂ estável em 93% fica abaixo da referência de 94% e é marcada em todos
  os segundos) e apenas 74 só do z-score robusto. O limiar da regra é ilustrativo e deveria ser ajustado por um
  clínico.
* **Correção aplicada após a primeira rodada.** Na primeira versão, o z-score disparava por **quantização**: FC e
  SpO₂ reais são inteiros e, em séries muito estáveis, o MAD é quase zero, então um passo de 1 bpm ou 1% virava
  "variação abrupta" (36,4% dos pontos marcados e 10,2 episódios por registro). Passamos a exigir uma variação mínima
  clínica em relação à mediana móvel (FC 8 bpm, PAS 15, PAD 10, SpO₂ 3 pontos) antes de contar o z-score, também no
  gate de corroboração do Isolation Forest. Resultado nos mesmos 53 registros: pontos marcados 36,4% para 24,9%,
  episódios por registro de 10,2 para 1,9 e registros sem episódio de 1 para 22; os 4 críticos continuam. Nas séries
  sintéticas os 4 críticos injetados continuam detectados e os 2 episódios leves de falso positivo sumiram (6 para 4
  episódios; série limpa de 2 para 0). O ajuste tem testes automáticos (`tests/test_anomalies.py`).

O registro 32 (SpO₂ ~84% o tempo todo) está em `tests/manual/physionet_bidmc_32.csv` para subir na aba
*Anomalias → Sinais vitais*: o app mostra 1 episódio, SpO₂ crítica (481 medições, ~84%).

Fonte dos dados: Pimentel et al., *BIDMC PPG and Respiration Dataset* (PhysioNet), licença Open Data Commons
Attribution v1.0. Goldberger et al., *PhysioBank, PhysioToolkit, and PhysioNet*, Circulation 2000.

## 6. Limitações e trabalhos futuros

* Limiares clínicos/dose/interações ilustrativos — validar com especialistas e bases oficiais.
* Sem avaliação quantitativa em dados rotulados reais (precisão/revocação); recomenda-se anotar um conjunto de validação. Em dados reais do PhysioNet (seção 5.5) o sistema ainda marca muitos pontos (24,9%) por causa do limiar clínico de SpO₂; a correção do z-score por quantização já foi aplicada e está descrita lá.
* **Tempo real:** a análise é feita sob demanda sobre arquivos enviados (vídeo, áudio e CSV); o envio do alerta ao webhook é automático após a análise, mas não há ingestão contínua. O fluxo em tempo real (RTSP, Event Hubs ou Azure Stream Analytics) é trabalho futuro.
* Correlacionar modalidades por janela de tempo (fusão intermediária) e personalizar limiares por paciente.
* Persistência de alertas (Cosmos DB / Table Storage), autenticação (Entra ID) e rede privada para uso real (LGPD).
* Inferência em GPU ou endpoint dedicado para vídeos longos; streaming em tempo real (RTSP/Event Hubs).

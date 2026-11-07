# Relatório técnico — Tech Challenge Fase 4

> Seções 1–4 descrevem o que está implementado. A **seção 5 (resultados)** tem espaços marcados com
> `PREENCHER`: preencha com as saídas reais após executar a aplicação, para que o relatório
> reflita medições e não estimativas.

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

* **Sinais vitais** — PhysioNet (https://physionet.org/): exporte para CSV `timestamp,hr,sbp,dbp,spo2`. Sugestão: bases de UTI como MIMIC-III Waveform / Demo ou *BIDMC PPG and Respiration*. `PREENCHER: qual base e quantos registros foram usados`.
* **Áudio** — AudioSet (https://research.google.com/audioset/) para sons de tosse/respiração/fala, e gravações próprias de leitura de sintomas. `PREENCHER`.
* **Vídeo** — clipes próprios de agachamento/caminhada com consentimento. `PREENCHER`.
* **Demonstração/testes** — geradores em `synthetic.py` com anomalias injetadas em posições conhecidas (permitem verificar acerto de forma objetiva).

### 5.1 Séries temporais (dados sintéticos, anomalias conhecidas)

Anomalias injetadas por `make_vitals()`: taquicardia sustentada (min 200–214), dessaturação
(min 300–311), pico hipertensivo (min 380–385) e um pico isolado de FC (min 120).
`make_prescriptions()`: dipirona 2×→dose acima do máximo, tramadol ×4, interação varfarina + ibuprofeno.
`make_movement()`: 4 h de imobilidade (dia 1) e queda às 10:00 do dia 2.

Os testes automatizados (`tests/test_anomalies.py`) verificam que cada uma é detectada e que as séries
sem anomalia geram poucos alertas.

| Métrica | Valor |
|---|---|
| Episódios de sinais vitais detectados | 7 (4 correspondem às anomalias injetadas: pico isolado de FC, taquicardia, dessaturação, pico hipertensivo; 3 são falsos positivos de 1–2 pontos, em SpO₂, DBP e SBP) |
| Alertas de prescrição | 5 (dipirona: dobra da dose e excesso do máximo; tramadol x4; interação varfarina + ibuprofeno) |
| Eventos de movimentação | 2 (imobilidade diurna de 13:00 a 16:45; queda suspeita às 10:00 do dia 2) |
| Eventos na série limpa (`make_vitals(inject=False)`, todos de severidade ALERTA) | 10 de 480 medições (2,1%) |

### 5.2 Vídeo

| Vídeo | Perfil | Eventos | Exemplo |
|---|---|---|---|
| `PREENCHER` | Agachamento | `PREENCHER` | `PREENCHER` (tempo, tipo, ângulo, captura anotada) |

### 5.3 Áudio

| Áudio | Silêncio | Pausas/min | f0 / jitter | Palavras/min | Termos críticos | Sentimento (Azure) |
|---|---|---|---|---|---|---|
| `PREENCHER` | | | | | | |

### 5.4 Exemplos de alertas gerados

`PREENCHER`: cole a tabela da aba *Alertas e relatório* e o relatório `.md` baixado.

## 6. Limitações e trabalhos futuros

* Limiares clínicos/dose/interações ilustrativos — validar com especialistas e bases oficiais.
* Sem avaliação quantitativa em dados rotulados reais (precisão/revocação); recomenda-se anotar um conjunto de validação.
* Correlacionar modalidades por janela de tempo (fusão intermediária) e personalizar limiares por paciente.
* Persistência de alertas (Cosmos DB / Table Storage), autenticação (Entra ID) e rede privada para uso real (LGPD).
* Inferência em GPU ou endpoint dedicado para vídeos longos; streaming em tempo real (RTSP/Event Hubs).

# Guia de teste — como testar cada funcionalidade

App publicado: <https://ca-hospmon-dev.graymushroom-60baf176.eastus2.azurecontainerapps.io/>

> A primeira abertura pode levar de 10 a 60 s (o app escala a zero quando fica parado). Abra a página
> alguns minutos antes de gravar o vídeo.

Os arquivos de exemplo estão na pasta `arquivos-de-teste/` do pacote (ou em `tests/manual/` no repositório).
Cada seção abaixo diz **o que clicar**, **qual arquivo usar** e **o que deve aparecer**. O registro detalhado dos
resultados obtidos está em [`mapa-de-testes.md`](mapa-de-testes.md).

## Ordem sugerida (uns 15 minutos)

1. Visão geral → demonstração (1 clique)
2. Sinais vitais → prescrições → movimentação (CSVs)
3. Áudio (3 arquivos + microfone)
4. Vídeo (4 arquivos + seu clipe)
5. Alertas → relatório → webhook

Dica: a central de alertas **acumula** entre as telas. Se quiser começar do zero, use *Limpar alertas*
na tela Alertas.

---

## 1. Visão geral

**Arquivo:** nenhum.

1. Abra a URL. Deve aparecer o título "Monitor clínico multimodal" e o diagrama do fluxo.
2. Em *Integrações Azure*: **Speech conectado**, **Language conectado**; *Webhook* conectado ou "não configurado".
3. Clique em **Rodar demonstração de séries temporais**.

**Esperado:** "11 alertas gerados" (4 de sinais vitais, 5 de prescrições, 2 de movimentação). Na barra lateral:
8 críticos e 3 alertas.

---

## 2. Anomalias → Sinais vitais

**Tela:** Anomalias → aba *Sinais vitais* → escolha **Enviar CSV**.

| Arquivo | Esperado |
|---|---|
| `vitais_normais.csv` | **Nenhum episódio** (série limpa) |
| `vitais_com_anomalias.csv` | **4 episódios, todos críticos**: pico de FC às 10:00, taquicardia 11:20–11:34, queda de SpO₂ 13:00–13:11, pico de PA 14:20–14:25 |
| `invalido_sem_timestamp.csv` | Mensagem de erro amigável ("CSV inválido: faltam as colunas…"), sem traceback |
| `physionet_bidmc_32.csv` (dado real do PhysioNet, só FC e SpO₂, 1 amostra/s) | **1 episódio**: SpO₂ crítica (481 medições, ~84%) |

Outras verificações:
- Troque o sinal do gráfico (FC, PA, SpO₂): pontos **vermelhos** (críticos) e **laranja** (alertas) sobre a linha.
- Abra *Parâmetros de detecção* e suba o limiar do z-score para 8: devem sobrar menos episódios.
- Sem arquivo, a opção de dados sintéticos gera uma série com anomalias injetadas.

## 3. Anomalias → Prescrições

**Tela:** Anomalias → aba *Prescrições*.

| Arquivo | Esperado |
|---|---|
| `prescricoes_normais.csv` | 0 anomalias |
| `prescricoes_com_anomalias.csv` | **5 anomalias**: dipirona dobra de dose (crítico), dipirona acima do máximo diário (crítico), dipirona ×1,5 (alerta), tramadol ×4 (crítico), interação varfarina + ibuprofeno (alerta). O enalapril não deve aparecer |

## 4. Anomalias → Movimentação

**Tela:** Anomalias → aba *Movimentação*.

| Arquivo | Esperado |
|---|---|
| `movimento_normal.csv` | Nenhum evento; curva com sono à noite |
| `movimento_com_anomalias.csv` | **2 eventos**: *imobilidade* no dia 1 às 13:00 (cerca de 4 h, alerta) e *queda suspeita* no dia 2 às 10:00 (crítico), com faixas coloridas no gráfico |

---

## 5. Áudio (Azure Speech + Azure AI Language)

**Tela:** Áudio → enviar o arquivo → **Transcrever com Azure Speech**. Áudios longos levam quase o tempo
do próprio áudio. Leia os blocos 1 a 4 (transcrição, voz, texto, alertas).

| Arquivo | Esperado |
|---|---|
| `consulta_sintomas_criticos.wav` (19 s) | Confiança ~80–90%; fonte **azure**; sentimento **negativo**; termos críticos: dor no peito, falta de ar, tontura, cansado, fraco; cerca de 6 alertas |
| `consulta_normal.wav` (15 s) | Sentimento positivo/neutro; **0 termos críticos**; 0 alertas |
| `consulta_fala_lenta_pausas.wav` (64 s) | Silêncio ~81%; pausa longa ~8,8 s; "Fala lenta"; termo "cansado"; sentimento negativo; cerca de 4 alertas |

Outras verificações:
- **Trocar de arquivo:** depois do primeiro, envie outro. A confiança e as palavras por minuto devem ser as do novo arquivo.
- **Texto de exemplo:** sem transcrever nada, clique em *Usar texto de exemplo*. A análise de texto roda e lista os termos críticos.
- **Microfone:** use *...ou grave agora*. Permita o microfone no navegador, fale 10–20 s (por exemplo:
  "Doutor, estou com falta de ar e uma dor no peito desde ontem, me sinto muito cansado e tonto") e clique em
  transcrever. Esperado: gravação com a duração falada, transcrição em português, termos críticos detectados.
  *Este é o único caso que ainda não foi exercitado com microfone físico.*

---

## 6. Vídeo (YOLOv8)

**Tela:** Vídeo → enviar o arquivo → escolher o perfil → **Analisar**.

| Arquivo | Perfil | Esperado |
|---|---|---|
| `video_sem_pessoa.mp4` | Agachamento | 1 evento "Paciente não detectado por 8,0 s" (alerta) |
| `pessoa_em_pe.mp4` | Agachamento | Pessoas detectadas, ângulos plotados, **0 eventos** |
| `pessoa_inclinada.mp4` | **Marcha / caminhada** | Alerta de tronco inclinado fora do limite (`trunk_tilt`) |
| `queda_simulada.mp4` | qualquer | Aos 3,0 s, evento **crítico** "Queda suspeita" |
| `pessoa_em_pe.mp4` | qualquer | Abra *Área crítica (ROI) e objetos observados*, marque *Definir área crítica* (H 0,60–1,00; V 0,50–1,00) e marque o objeto `person`: evento crítico "Objeto 'person' dentro da área crítica", com o retângulo vermelho no quadro anotado |

Observações:
- Esses vídeos são uma foto real girada, por isso o movimento é simulado. Eles provam a detecção de pessoa, a
  inclinação e a queda, mas não um agachamento de verdade.
- **Seu clipe (V-7):** grave 10–30 s de uma pessoa agachando, de corpo inteiro, com a câmera parada e luz boa.
  Use o perfil *Agachamento*. Esperado: ângulos de joelho variando e eventos de limite, assimetria ou velocidade se houver desvio.
  Para marcha, use o perfil *Marcha / caminhada* com a pessoa andando de lado para a câmera.

---

## 7. Alertas e relatório

**Tela:** Alertas.

1. Depois de ter rodado áudio e vídeo, a central lista os alertas das duas fontes, ordenados por severidade.
2. Filtro *Mostrar a partir de* = CRÍTICO: só os críticos aparecem.
3. Preencha **paciente** e **observações**, abra *Pré-visualizar relatório* e clique em **Baixar relatório (Markdown)**.
   O relatório traz resumo e uma tabela por fonte.
4. **Enviar alertas ao webhook** (só aparece com `ALERT_WEBHOOK_URL` configurado): mostra um aviso (toast) "Webhook confirmou o recebimento de N alerta(s)" no canto da tela e a mensagem "N alerta(s) enviados".
   Para ver a mensagem chegando:
   ```bash
   az containerapp logs show -g rg-hospital-monitor -n ca-webhook-sink --type console --tail 20 --format text
   ```
5. **Limpar alertas**: contadores voltam a zero.

---

## 8. Infraestrutura (para mostrar no vídeo)

- Portal Azure → grupo de recursos `rg-hospital-monitor`: registro de contêineres, ambiente e app do Container
  Apps, Speech, Language, Log Analytics e identidade gerenciada.
- Saúde do app: `https://ca-hospmon-dev.graymushroom-60baf176.eastus2.azurecontainerapps.io/_stcore/health` deve responder **ok**.
- Logs: `az containerapp logs show -g rg-hospital-monitor -n ca-hospmon-dev --type console --tail 30 --format text`.
- Código da infraestrutura: [`infra/main.bicep`](../infra/main.bicep). Pipeline: `.github/workflows/`.

## 9. Testes automatizados (sem Azure)

```bash
pip install -r requirements-dev.txt
pytest -q
ruff check src app tests scripts
```

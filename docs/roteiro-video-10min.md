# Roteiro do vídeo — versão de 10 minutos

Versão enxuta do [roteiro de 15 min](roteiro-video.md). Para cada cena: **Tela**, **Fazer** (cliques e arquivos)
e **Falar** (texto sugerido, diga com suas palavras). Resultados esperados de cada passo:
[guia-de-teste.md](guia-de-teste.md). Arquivos de exemplo: `tests/manual/` ou o zip `arquivos-de-teste`.

| Tempo | Cena | Resumo |
|---|---|---|
| 0:00–1:00 | 1. A ideia | Problema, solução e diagrama |
| 1:00–2:00 | 2. Repositório (Git) | Estrutura, commits, CI |
| 2:00–3:00 | 3. Datasets | O que foi usado e por quê |
| 3:00–4:30 | 4. Azure e IaC | Portal, Bicep, serviços, deploy |
| 4:30–5:00 | 5. App: visão geral | Integrações e demonstração |
| 5:00–6:30 | 6. Vídeo (IA: YOLOv8) | Pose, queda, área crítica |
| 6:30–8:00 | 7. Áudio (IA: Speech + Language) | Transcrição, voz, termos críticos |
| 8:00–9:00 | 8. Séries temporais | Vitais, prescrições, movimento |
| 9:00–10:00 | 9. Alertas, webhook e fechamento | Central, webhook, limitações |

## Antes de gravar (10 min antes)

- [ ] Abrir o app e rodar um áudio e um vídeo para aquecer o contêiner. Depois, **Limpar alertas**.
      URL: <https://ca-hospmon-dev.graymushroom-60baf176.eastus2.azurecontainerapps.io/>
- [ ] Abas prontas, nesta ordem: GitHub, `infra/main.bicep` no editor, Portal Azure (grupo `rg-hospital-monitor`), app.
- [ ] Terminal com o comando de logs do webhook já digitado:
      `az containerapp logs show -g rg-hospital-monitor -n ca-webhook-sink --type console --tail 20 --format text`
- [ ] Seletor de arquivos já navegado até a pasta dos exemplos. Zoom do navegador em 125%, 1080p.
- [ ] **Não abrir a tela de *Keys* do Portal** nem mostrar arquivos `.env`.

Para ficar em 10 minutos, **não espere a transcrição inteira ao vivo**: o áudio de 19 s leva ~20 s. Fale
durante a espera. Se quiser apertar mais, corte a espera na edição.

---

## 1. A ideia (0:00–1:00)

**Tela:** `README.md` no GitHub, no diagrama de arquitetura.

**Falar:**
> "Este é o Tech Challenge da Fase 4: um sistema de monitoramento clínico multimodal. Em um hospital, informação
> importante chega por vários canais: vídeo de um paciente em fisioterapia, áudio de uma consulta e séries de
> sinais vitais. O sistema analisa cada canal com IA, detecta anomalias e consolida tudo em alertas para a equipe
> médica. Tudo roda no Azure, criado por código."

**Fazer:** aponte no diagrama: entradas (vídeo, áudio, CSV) → módulos de análise → central de alertas → webhook.

## 2. Repositório (1:00–2:00)

**Tela:** <https://github.com/DhiegoPimenta/tech-challenge-fase4>

**Fazer:**
1. Mostre as pastas: `src/hospital_monitor` (vídeo, áudio, anomalias, alertas), `app` (telas Streamlit), `infra` (Bicep), `tests`, `docs`, `.github/workflows`.
2. Abra **Commits**: histórico organizado.
3. Abra **Actions**: os fluxos `ci.yml` (lint, testes, build do Bicep e da imagem) e `deploy.yml` (publica no Azure).
4. Cite `docs/` (arquitetura, deploy, relatório técnico, guia de teste).

**Falar:**
> "O código está organizado por responsabilidade: um pacote com a lógica, o app Streamlit só como interface, a
> infraestrutura em Bicep, 41 testes automatizados e documentação. Cada alteração passa por um pipeline que roda
> lint, testes e valida a infraestrutura. O deploy é outro pipeline, com login OIDC no Azure, sem senhas
> guardadas no repositório."

## 3. Datasets (2:00–3:00)

**Tela:** `docs/relatorio-tecnico.md`, seção 5 "Datasets" (ou `tests/manual/` no GitHub).

**Falar:**
> "Para poder medir o acerto, usei dados sintéticos com anomalias injetadas em posições conhecidas: uma série de
> sinais vitais de 480 minutos com taquicardia, queda de saturação e pico de pressão; prescrições com dose
> dobrada e interação medicamentosa; e movimentação com 4 horas de imobilidade e uma queda. O áudio são consultas
> simuladas em português, e o vídeo são clipes de teste, um sem pessoa e três a partir de uma foto real. O app
> também aceita CSVs reais, por exemplo do PhysioNet. Não usei dados de pacientes."

**Fazer:** mostre a lista de arquivos de `tests/manual/` (CSVs, `.wav`, `.mp4`).

## 4. Azure e IaC (3:00–4:30)

**Tela:** Portal Azure → `rg-hospital-monitor`; depois `infra/main.bicep`.

**Fazer:**
1. No Portal, percorra os recursos e diga o papel de cada um:
   - **Container Apps** (ambiente + app): hospeda o Streamlit, com escala a zero.
   - **Container Registry**: guarda a imagem do app.
   - **Azure AI Speech**: transcrição de áudio.
   - **Azure AI Language**: sentimento, frases-chave e entidades.
   - **Log Analytics**: logs.
   - **Identidade gerenciada**: o app puxa a imagem sem senha.
2. Abra `infra/main.bicep` e role até: o ACR sem usuário admin, o papel AcrPull, os secrets das chaves e o `minReplicas`.
3. Mostre rapidamente `infra/deploy.ps1` e `.github/workflows/deploy.yml`.

**Falar:**
> "A infraestrutura é totalmente código. Um único Bicep cria o ambiente, o registro de imagens, o Speech, o
> Language e o app. O app acessa o registro por identidade gerenciada, sem senha de administrador, e as chaves
> dos serviços entram como secrets. O deploy é em duas fases: primeiro a infraestrutura, depois a imagem real
> construída pelo GitHub Actions. O Speech e o Language são as peças de IA do Azure que o sistema usa de verdade,
> chamadas em tempo de execução."

## 5. App: visão geral (4:30–5:00)

**Tela:** app → **Visão geral**.

**Fazer:** mostre *Integrações Azure* (Speech e Language conectados) e clique em
**▶️ Rodar demonstração de séries temporais**.

**Falar:**
> "A Visão geral mostra o fluxo e se os serviços do Azure estão conectados. Este botão roda os detectores sobre
> dados sintéticos: 13 alertas, 8 críticos, que já aparecem no contador da barra lateral."

## 6. Vídeo — IA com YOLOv8 (5:00–6:30)

**Tela:** **Vídeo**.

**Fazer:**
1. `pessoa_em_pe.mp4`, perfil **Agachamento** → **🔍 Analisar vídeo**. Mostre o quadro com esqueleto e caixas; sem eventos.
2. `queda_simulada.mp4` → Analisar. Aos 3,0 s, evento **crítico** de queda suspeita. Abra o evento e mostre o quadro.
3. Opcional, se sobrar tempo: `pessoa_inclinada.mp4` com perfil **Marcha / caminhada** (tronco fora do limite) ou a área crítica (*Definir área crítica*).

**Falar:**
> "No vídeo uso o YOLOv8 com estimativa de pose, que extrai 17 pontos do corpo. A partir deles calculo ângulos de
> joelho, cotovelo e quadril, inclinação do tronco, assimetria e velocidade, e comparo com os limites de cada
> perfil: agachamento, marcha ou livre. A queda é detectada quando a proporção da caixa da pessoa muda de em pé
> para deitada em menos de 1,5 segundo. Também dá para definir uma área crítica e alertar se um objeto, como uma
> tesoura, entrar nela. Os clipes de teste usam uma foto girada, então o movimento é simulado; a detecção das
> pessoas é real."

## 7. Áudio — Azure Speech + Language (6:30–8:00)

**Tela:** **Áudio**.

**Fazer:**
1. Envie `consulta_sintomas_criticos.wav` → **🎙️ Transcrever com Azure Speech**. Fale enquanto espera (~20 s).
2. Percorra os blocos: transcrição e confiança (~86%) → características vocais → análise de texto (fonte **azure**, sentimento **negativo**, termos críticos: dor no peito, falta de ar, tontura, cansado, fraco) → alertas.
3. Opcional, se sobrar tempo: *...ou grave agora* e fale uma frase com "falta de ar e dor no peito".

**Falar:**
> "O áudio passa por três etapas. O Azure Speech transcreve, com a confiança do reconhecimento. Em paralelo,
> calculo localmente características da voz, como silêncio, pausas, frequência fundamental e jitter, que são
> indicadores de fadiga ou dificuldade respiratória, não diagnóstico. Depois o Azure AI Language analisa o
> sentimento e extrai frases-chave, e um dicionário de termos clínicos marca o que é crítico. Neste caso ele
> achou dor no peito, falta de ar e tontura, e gerou alertas."

## 8. Séries temporais (8:00–9:00)

**Tela:** **Anomalias**.

**Fazer:**
1. Aba **Sinais vitais** → *Enviar CSV* → `vitais_com_anomalias.csv`. Mostre os 6 episódios (4 críticos) e os pontos vermelhos; troque o sinal do gráfico para SpO₂.
2. Aba **Prescrições** → `prescricoes_com_anomalias.csv`: 5 anomalias.
3. Aba **Movimentação** → `movimento_com_anomalias.csv`: imobilidade de 4 h e queda suspeita.

**Falar:**
> "Nos sinais vitais combino regras clínicas, um z-score robusto em janela móvel e o Isolation Forest, que só vale
> quando o z-score local concorda, para reduzir falsos positivos. Pontos vizinhos viram um episódio com a
> justificativa. Nas prescrições verifico salto de dose, dose máxima diária e interações de risco, como
> varfarina com ibuprofeno. Na movimentação, imobilidade diurna prolongada e queda suspeita."

## 9. Alertas, webhook e fechamento (9:00–10:00)

**Tela:** **Alertas**, depois o terminal.

**Fazer:**
1. Mostre a central com alertas de todas as fontes. Filtre por CRÍTICO.
2. Preencha **paciente**, clique em **📨 Enviar alertas (ALERTA e acima) ao webhook** ("N alerta(s) enviados").
3. No terminal, rode o comando de logs do receptor e mostre a linha `WEBHOOK_RECEBIDO` com o JSON.
4. Mostre o botão **Baixar relatório (Markdown)** (ou a pré-visualização).
5. Feche com o link do repositório na tela.

**Falar:**
> "Todas as modalidades alimentam uma central única, com três níveis de severidade. Os alertas importantes são
> enviados por webhook para a equipe, aqui um receptor de teste, mas em produção seria Teams, Slack ou um Logic
> App. A mensagem chegou completa. Também gero um relatório em Markdown. Para fechar: os limiares clínicos são
> ilustrativos e precisam de validação com especialistas, e usei dados sintéticos para poder medir o acerto. Os
> próximos passos são cruzar as modalidades por janela de tempo, persistir os alertas, autenticar com Entra ID,
> usar GPU para vídeos longos e streaming em tempo real. Código e documentação estão no GitHub. Obrigado."

---

## Se algo der errado

| Problema | O que fazer |
|---|---|
| App demora a abrir | Inicialização a frio: espere até 60 s ou corte na edição |
| Transcrição lenta | Comente os blocos de voz enquanto espera, ou corte a espera |
| Webhook não aparece | Rode o comando de logs de novo com `--tail 30` |
| Estourando o tempo | Pule o opcional: a área crítica, o microfone e a aba de movimentação |

Dica: grave por cena e junte depois; fale sem pressa e mostre o resultado antes de explicar.

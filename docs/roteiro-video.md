# Roteiro do vídeo (até 15 min)

Para cada cena: **Tela** (onde estar), **Fazer** (o que clicar e subir) e **Falar** (texto sugerido, com suas
palavras). Os arquivos de exemplo estão em [`tests/manual/`](../tests/manual) e no zip `arquivos-de-teste`.
Resultados esperados de cada passo: [guia-de-teste.md](guia-de-teste.md).

## Antes de gravar (10 minutos antes)

- [ ] Abrir o app e deixar a página carregada: <https://ca-hospmon-dev.graymushroom-60baf176.eastus2.azurecontainerapps.io/> (se estiver parado, a 1ª abertura demora).
- [ ] Rodar uma vez o fluxo completo (áudio e vídeo) para aquecer o contêiner, depois **Limpar alertas**.
- [ ] Portal Azure aberto no grupo `rg-hospital-monitor`. **Não abra a tela de *Keys*.**
- [ ] Abas prontas: app, Portal, GitHub (repositório), `infra/main.bicep` no editor, terminal para os logs.
- [ ] Pasta com os arquivos de teste aberta (ou o caminho no seletor de arquivos já navegado).
- [ ] Navegador a 125% de zoom, 1080p, notificações desligadas, microfone testado.
- [ ] Receptor de webhook no ar (para mostrar o alerta chegando) e terminal com este comando pronto:
  `az containerapp logs show -g rg-hospital-monitor -n ca-webhook-sink --type console --tail 20 --format text`
- [ ] (Opcional) um clipe seu de agachamento de 10–30 s e o microfone liberado no navegador.

## Visão geral dos tempos

| Tempo | Cena |
|---|---|
| 0:00–1:30 | 1. Abertura e contexto |
| 1:30–3:30 | 2. Infraestrutura Azure |
| 3:30–4:30 | 3. Visão geral do app |
| 4:30–7:00 | 4. Vídeo (YOLOv8) |
| 7:00–9:30 | 5. Áudio (Speech + Language) |
| 9:30–12:00 | 6. Anomalias (vitais, prescrições, movimento) |
| 12:00–14:00 | 7. Alertas, webhook e relatório |
| 14:00–15:00 | 8. Fechamento |

---

## 1. Abertura e contexto (0:00–1:30)

**Tela:** slide ou o `README.md` no GitHub, com o diagrama de [arquitetura](arquitetura.md).

**Falar:**
> "Este é o Tech Challenge da Fase 4: um sistema de monitoramento clínico multimodal. Ele recebe vídeo, áudio e
> dados de sinais vitais, detecta anomalias em cada um e consolida tudo em alertas para a equipe médica.
> O vídeo usa YOLOv8 com estimativa de pose. O áudio usa Azure Speech para transcrever e Azure AI Language
> para analisar o texto. Os sinais vitais, prescrições e movimentação usam regras clínicas, z-score robusto e
> Isolation Forest. Tudo roda no Azure Container Apps, criado por Bicep."

Mostre o diagrama apontando: entradas → módulos → central de alertas → webhook.

## 2. Infraestrutura Azure (1:30–3:30)

**Tela:** Portal Azure → grupo `rg-hospital-monitor`; depois `infra/main.bicep` no editor.

**Fazer:**
1. No Portal, percorra os recursos: registro de contêineres, ambiente e app do Container Apps, Speech, Language, Log Analytics e identidade gerenciada.
2. Abra `infra/main.bicep` e role até o ACR (sem usuário admin), a identidade com AcrPull e os secrets do app.
3. Abra `.github/workflows/deploy.yml` por 10 s.

**Falar:**
> "Toda a infraestrutura é código: um Bicep cria o ambiente, o registro de imagens, o Speech, o Language e o app.
> O app puxa a imagem com identidade gerenciada, sem senha de administrador, e as chaves dos serviços entram como
> secrets. A imagem é construída pelo GitHub Actions com login OIDC, sem segredos guardados no repositório.
> O app escala a zero quando fica parado, para economizar."

## 3. Visão geral do app (3:30–4:30)

**Tela:** app → barra lateral → **Visão geral**.

**Fazer:**
1. Mostre o título e o fluxo.
2. Aponte *Integrações Azure*: Speech e Language conectados.
3. Clique em **▶️ Rodar demonstração de séries temporais**.

**Falar:**
> "A Visão geral mostra o fluxo e o estado das integrações com o Azure. Speech e Language estão conectados.
> Este botão gera dados sintéticos com anomalias em posições conhecidas e roda os detectores: 13 alertas,
> 8 críticos, que aparecem no contador da barra lateral."

## 4. Vídeo (4:30–7:00)

**Tela:** **Vídeo**.

**Fazer (nesta ordem):**
1. Envie `pessoa_em_pe.mp4`, perfil **Agachamento** → **🔍 Analisar vídeo**. Mostre os ângulos, o gráfico de objetos e o quadro anotado com esqueleto. Sem eventos.
2. Envie `queda_simulada.mp4` → Analisar. Aos 3,0 s aparece o evento **crítico de queda suspeita**; abra o evento e mostre o quadro.
3. Envie `pessoa_inclinada.mp4`, perfil **Marcha / caminhada** → Analisar. Evento de tronco fora do limite.
4. Abra *Área crítica (ROI) e objetos observados*, marque *Definir área crítica* (H 0,60–1,00; V 0,50–1,00), objeto `person`, e analise `pessoa_em_pe.mp4`. Evento crítico de objeto na área, com o retângulo vermelho.
5. (Opcional, se tiver) envie seu clipe de agachamento e mostre a curva do ângulo do joelho.
6. `video_sem_pessoa.mp4`: evento "Paciente não detectado por 8 s".

**Falar:**
> "O YOLOv8 com pose extrai 17 pontos do corpo. Daí calculo ângulos de joelho, cotovelo e quadril, inclinação do
> tronco, assimetria entre os lados e velocidade angular. Cada perfil tem seus limites: agachamento, marcha ou
> livre. A queda é detectada pela mudança da proporção da caixa da pessoa, de em pé para deitada em menos de
> 1,5 segundo. Também dá para marcar uma área crítica e objetos observados, como tesoura ou faca, e ser alertado
> se algo entrar nela. Se a pessoa some do quadro por tempo demais, também gera alerta."

**Aviso honesto (pode falar):** os clipes de teste são uma foto girada; o movimento é simulado.

## 5. Áudio (7:00–9:30)

**Tela:** **Áudio**.

**Fazer:**
1. Envie `consulta_sintomas_criticos.wav` → **🎙️ Transcrever com Azure Speech** (leva ~20 s; fale sobre as características vocais enquanto espera).
2. Percorra os blocos: transcrição e confiança (~86%) → características vocais (silêncio, pausas, f0, jitter) → análise de texto: fonte **azure**, sentimento **negativo**, frases-chave, termos críticos (dor no peito, falta de ar, tontura, cansado, fraco) → alertas.
3. Envie `consulta_normal.wav` e transcreva: sem termos críticos nem alertas, sentimento positivo (mostra o contraste e que os dados antigos somem).
4. (Rápido) `consulta_fala_lenta_pausas.wav`: não precisa esperar tudo; se o tempo estiver apertado, mostre só o resultado já testado, ou pule.
5. **Microfone:** em *...ou grave agora*, permita o microfone e fale: "Doutor, estou com falta de ar e uma dor no peito desde ontem, me sinto muito cansado e tonto." Transcreva.
6. No Portal, abra o recurso Speech → **Monitoring** (métricas de chamadas). Não abra *Keys*.

**Falar:**
> "O áudio passa por três etapas. Primeiro o Azure Speech transcreve, com a confiança do reconhecimento. Depois
> calculo características da voz localmente: proporção de silêncio, pausas, frequência fundamental, jitter e
> palavras por minuto, que são indicadores de fadiga e dificuldade respiratória, não diagnóstico. Por fim, o
> Azure AI Language faz sentimento, frases-chave e entidades, e eu cruzo com um dicionário de termos críticos.
> Neste áudio ele encontra dor no peito, falta de ar e tontura, e gera alertas."

## 6. Anomalias (9:30–12:00)

**Tela:** **Anomalias**.

**Fazer:**
1. Aba **Sinais vitais** → *Enviar CSV* → `vitais_com_anomalias.csv`. Mostre os 6 episódios (4 críticos), troque o sinal do gráfico (FC → SpO₂ → PA), aponte os pontos vermelhos. Abra *Parâmetros de detecção* e suba o z-score para mostrar o efeito.
2. (Rápido) `vitais_normais.csv`: nenhum episódio crítico.
3. Aba **Prescrições** → `prescricoes_com_anomalias.csv`: 5 anomalias (dose dobra, acima do máximo, tramadol ×4, varfarina + ibuprofeno). O enalapril não aparece.
4. Aba **Movimentação** → `movimento_com_anomalias.csv`: imobilidade de 4 h e queda suspeita, com faixas coloridas.
5. Se o erro de CSV couber: `invalido_sem_timestamp.csv` → mensagem amigável (mostra robustez).

**Falar:**
> "Nos sinais vitais combino três técnicas. Regras clínicas pegam valores perigosos, como saturação abaixo de
> 90%. Um z-score robusto, com mediana e MAD em janela móvel, pega desvios do padrão do paciente. E o Isolation
> Forest pega combinações estranhas entre FC, pressão e saturação, mas só vale se o z-score local concordar,
> o que reduziu muito os falsos positivos. Pontos vizinhos viram um único episódio com a justificativa. Nas
> prescrições verifico salto de dose, dose diária máxima e interações de risco. Na movimentação detecto
> imobilidade diurna prolongada e queda suspeita."

## 7. Alertas, webhook e relatório (12:00–14:00)

**Tela:** **Alertas**.

**Fazer:**
1. Mostre a central consolidada (vídeo, áudio, vitais, prescrições, movimento) ordenada por severidade. Use o filtro *Mostrar a partir de* = CRÍTICO.
2. Preencha **paciente** e **observações**, abra *Pré-visualizar relatório* e clique em **Baixar relatório (Markdown)**.
3. Clique em **📨 Enviar alertas (ALERTA e acima) ao webhook** → "N alerta(s) enviados".
4. Mude para o terminal e rode o comando de logs do receptor (`az containerapp logs show ... ca-webhook-sink`). Mostre a linha `WEBHOOK_RECEBIDO` com o JSON.
5. (Opcional) logs do app principal ao vivo: `az containerapp logs show -g rg-hospital-monitor -n ca-hospmon-dev --type console --tail 30 --format text`.

**Falar:**
> "Todas as modalidades alimentam uma central única, com três níveis de severidade. Os alertas de nível alerta
> ou crítico são enviados por webhook para a equipe, aqui para um receptor de teste, mas em produção seria
> Teams, Slack ou um Logic App. A mensagem chegou com os alertas completos. Também gero um relatório em
> Markdown para o prontuário ou para revisão."

## 8. Fechamento (14:00–15:00)

**Tela:** `docs/relatorio-tecnico.md` (seção 6) ou slide final.

**Falar:**
> "Resumindo: vídeo, áudio e séries temporais, tudo integrado e publicado no Azure por código. Os limiares
> clínicos e doses são ilustrativos e precisam de validação com especialistas; usei dados sintéticos para
> poder medir o acerto. Os próximos passos são cruzar as modalidades por janela de tempo, persistir os alertas,
> autenticar com Entra ID, usar GPU para vídeos longos e streaming em tempo real. O código, a documentação e o
> relatório técnico estão no GitHub. Obrigado."

Mostre por 5 s o link do repositório: <https://github.com/DhiegoPimenta/tech-challenge-fase4>.

---

## Se algo der errado ao vivo

| Problema | O que fazer |
|---|---|
| App demora a abrir | É a inicialização a frio. Espere até 60 s, ou corte na edição |
| Transcrição demora | Comente o que está acontecendo e fale do bloco de voz; o áudio longo leva quase o tempo dele |
| Microfone não pede permissão | Clique no cadeado da barra de endereço e permita o microfone; se não der, use o texto de exemplo |
| Webhook não aparece | Rode os logs do receptor de novo (`--tail 30`); o app precisa da variável `ALERT_WEBHOOK_URL` |
| Erro inesperado | Mostre o log do contêiner, é um bom material sobre observabilidade |

Dicas finais: fale sem pressa, mostre o resultado antes de explicar, grave por cenas (dá para cortar e juntar),
mantenha as chaves fora do enquadramento e confira o tempo total (máximo 15 min).

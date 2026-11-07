<#
.SYNOPSIS
  Gera áudios de consulta falados (voz pt-BR do Windows) para o mapa de testes manuais.
  Saída: tests/manual/*.wav (PCM 16 kHz mono).
#>
Add-Type -AssemblyName System.Speech
$out = Join-Path (Split-Path -Parent $PSScriptRoot) "tests\manual"
New-Item -ItemType Directory -Force $out | Out-Null

function New-Speech($file, $text, $rate = 0, $pauseMs = 0) {
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SelectVoice("Microsoft Maria Desktop")
  $s.Rate = $rate
  $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
  $s.SetOutputToWaveFile((Join-Path $out $file), $fmt)
  $pb = New-Object System.Speech.Synthesis.PromptBuilder
  $pb.Culture = [System.Globalization.CultureInfo]::GetCultureInfo("pt-BR")
  foreach ($sentence in $text) {
    $pb.AppendText($sentence)
    if ($pauseMs -gt 0) { $pb.AppendBreak([TimeSpan]::FromMilliseconds($pauseMs)) }
  }
  $s.Speak($pb)
  $s.Dispose()
}

# 1) Sintomas críticos (esperado: termos críticos + sentimento negativo)
New-Speech "consulta_sintomas_criticos.wav" @(
  "Doutor, eu estou muito cansado nos últimos dias.",
  "Sinto falta de ar quando subo a escada e ontem tive uma tontura forte.",
  "Também estou com dor no peito de vez em quando e me sinto muito fraco.",
  "Estou preocupado porque piorou.")

# 2) Consulta tranquila (esperado: sem termos críticos)
New-Speech "consulta_normal.wav" @(
  "Bom dia, doutor.",
  "Estou me sentindo bem e dormindo bem.",
  "Tomei os remédios direitinho e voltei a caminhar todos os dias.",
  "Não tenho nenhuma queixa hoje.")

# 3) Fala lenta e com pausas longas (esperado: indicadores vocais de silêncio/pausa/fala lenta)
New-Speech "consulta_fala_lenta_pausas.wav" @(
  "Doutor.", "Eu estou.", "Muito cansado.", "Hoje.", "Não consigo.", "Falar direito.") -rate -6 -pauseMs 3500

Get-ChildItem $out -Filter *.wav | ForEach-Object { "{0,-36} {1,8:N1} KB" -f $_.Name, ($_.Length / 1KB) }

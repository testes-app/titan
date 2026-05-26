# 🤖 TITAN v5.0.0 — Assistente Pessoal com IA

Assistente pessoal por voz para Windows 11, desenvolvido para **Cornelio**.  
Combina comandos locais rápidos com um agente de IA poderoso (Google Gemini 2.0 Flash) capaz de controlar o computador, navegar na web e gerenciar arquivos.

## Configuração
Copie .env.example para .env e preencha com suas chaves.
Nunca suba o arquivo .env para o GitHub.

---

## 📋 Sumário

- [Arquitetura](#-arquitetura)
- [Requisitos](#-requisitos)
- [Instalação](#-instalação)
- [Como Rodar](#-como-rodar)
- [Funcionalidades](#-funcionalidades)
- [Ferramentas do Agente IA](#-ferramentas-do-agente-ia)
- [Estrutura do Código](#-estrutura-do-código)
- [Changelog](#-changelog)

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                   GUI (tkinter)                     │
├─────────────────────────────────────────────────────┤
│  Microfone → VAD → STT (Google) → _processar_comando│
│                                                     │
│  ┌─────────────────────┐   ┌──────────────────────┐ │
│  │  CAMADA LOCAL       │   │  AGENTE IA           │ │
│  │  • Hora/Data        │   │  • Gemini 2.0 Flash  │ │
│  │  • Clima            │   │  • 11 Ferramentas    │ │
│  │  • Abrir/Fechar App │   │  • Loop tool_use     │ │
│  │  • Notas Obsidian   │   │  • Histórico 10 turns│ │
│  │  • Lotofácil/Reis   │   │  • Fallback: Ollama  │ │
│  │  • Saudações        │   │    (gemma2:2b)        │ │
│  │  • Notícias RSS     │   │                      │ │
│  └─────────────────────┘   └──────────────────────┘ │
│                                                     │
│  TTS (Edge TTS - pt-BR-AntonioNeural) → Alto-falante│
└─────────────────────────────────────────────────────┘
```

**Fluxo de decisão:**
1. Comando de voz capturado pelo VAD (Voice Activity Detection)
2. Transcrito pelo STT (Google Speech Recognition)
3. Passa pela **camada local** primeiro (respostas instantâneas, sem API)
4. Se nenhuma regra local bater → cai no **Agente IA** (Gemini)
5. Se Gemini falhar → **Fallback** para Ollama local (gemma2:2b)

---

## 📦 Requisitos

| Componente | Versão |
|---|---|
| Python | 3.14+ (`C:\Python314\python.exe`) |
| Windows | 11 |
| Microfone | Qualquer dispositivo de entrada |

### Dependências Python

```
edge-tts          # TTS via Microsoft Edge
sounddevice       # Captura de áudio
numpy             # Processamento de áudio
scipy             # Escrita de WAV
SpeechRecognition # STT via Google
google-genai      # API do Google Gemini
pyautogui         # Controle de mouse/teclado
playwright        # Navegação web headless
beautifulsoup4    # Parsing HTML
requests          # Requisições HTTP
chromadb          # Base de conhecimento de Design
```

---

## 🔧 Instalação

```powershell
# 1. Instalar dependências Python
C:\Python314\python.exe -m pip install edge-tts sounddevice numpy scipy SpeechRecognition google-genai pyautogui playwright beautifulsoup4 requests chromadb --break-system-packages

# 2. Instalar navegador Chromium para o Playwright
C:\Python314\python.exe -m playwright install chromium
```

### Configurar a chave da API

No arquivo `titan.py`, localize a linha:
```python
_gemini_client = genai.Client(api_key="SUA_CHAVE_AQUI")
```
Substitua `SUA_CHAVE_AQUI` pela sua chave do [Google AI Studio](https://aistudio.google.com).

---

## 🚀 Como Rodar

**Via terminal:**
```powershell
C:\Python314\python.exe C:\TITAN\titan.py
```

**Via atalho:**
```
C:\TITAN\INICIAR_TITAN.bat
```

Ao iniciar, o TITAN:
1. Abre a janela GUI
2. Fala a saudação (Bom dia/Boa tarde/Boa noite)
3. Calibra o ruído do microfone (2 segundos)
4. Fica aguardando sua voz

---

## 🎯 Funcionalidades

### Comandos Locais (sem API — resposta instantânea)

| Comando de Voz | Ação |
|---|---|
| "Que horas são" | Informa hora atual |
| "Que dia é hoje" | Informa data |
| "Bom dia" / "Oi" | Saudação |
| "Qual o clima" | Temperatura via Open-Meteo |
| "Notícias" | Últimas 3 da Folha (RSS) |
| "Abrir Chrome" | Abre o programa |
| "Fechar Spotify" | Encerra o processo |
| "Listar notas" | Lista notas do Obsidian |
| "Ler nota X" | Lê conteúdo da nota |
| "Crie uma nota sobre X" | Cria arquivo .md no Vault |
| "Pesquise X" | Busca nas notas do Obsidian |
| "Status" | Relatório do TITAN |
| "Auditar 01 02 03..." | Auditoria Lotofácil |
| "Como está o Rei 11" | Consulta de Reis |
| "Tchau" | Encerra o TITAN |

### Programas Suportados

| Nome | Processo |
|---|---|
| Calculadora | calc.exe |
| Chrome | chrome |
| Spotify | spotify: |
| Notepad / Bloco de Notas | notepad.exe |
| WhatsApp | whatsapp: |
| Terminal | cmd.exe |
| Explorador | explorer.exe |
| Cofre / Obsidian | Abre a pasta do Vault |
| Downloads / Documentos / Desktop | Pastas do sistema |

### Agente IA (via Gemini 2.0 Flash)

Qualquer comando que **não** bata com as regras locais acima é encaminhado ao agente inteligente, que pode usar ferramentas para resolver a solicitação. Exemplos:

- *"Pesquise no Google sobre inteligência artificial"*
- *"Tire um print da tela"*
- *"Crie um arquivo texto na área de trabalho"*
- *"Qual a capital da Austrália?"*

---

## 🔧 Ferramentas do Agente IA

O agente tem acesso a **11 ferramentas** que ele decide quando e como usar:

| # | Ferramenta | Descrição |
|---|---|---|
| 1 | `abrir_programa` | Abre app pelo nome |
| 2 | `fechar_programa` | Fecha processo |
| 3 | `mover_mouse` | Move cursor para X, Y |
| 4 | `clicar` | Clique (left/right/middle) |
| 5 | `digitar_texto` | Digita via teclado |
| 6 | `screenshot` | Captura tela em base64 (só se solicitado) |
| 7 | `gerenciar_arquivo` | Copiar, mover, deletar, criar, listar |
| 8 | `navegar_web` | Abre URL via Playwright e retorna texto |
| 9 | `executar_script` | Executa script Python |
| 10 | `pesquisar_obsidian` | Busca nas notas do Vault |
| 11 | `ler_nota` | Lê conteúdo de uma nota |

### Fallback Local

Se a API do Gemini falhar (sem internet, erro de chave, etc.), o TITAN automaticamente usa o **Ollama local** com o modelo `gemma2:2b` para responder.

---

## 📁 Estrutura do Código

```
C:\TITAN\
├── titan.py            # Código principal do assistente
├── INICIAR_TITAN.bat   # Atalho para iniciar
├── chromadb/           # Base de conhecimento de Web Design
└── README.md           # Este arquivo

Dependências externas:
├── C:\Users\...\vitoria-loto\          # Módulos Lotofácil
│   ├── _scripts\consultar_reis.py      # Consulta de Reis
│   ├── _scripts\auditar_voz.py         # Auditoria por voz
│   └── vitoria_bridge.py               # Bridge para comandos loto
└── C:\Users\...\VITORIA_LOTO\          # Vault Obsidian
```

### Módulos Internos

| Módulo | Responsabilidade |
|---|---|
| **GUI** | Interface tkinter com log, status e calibração |
| **VAD** | Detecção de atividade vocal (RMS threshold) |
| **STT** | Transcrição via Google Speech Recognition |
| **TTS** | Síntese de voz via Edge TTS (pt-BR-AntonioNeural) |
| **Agente IA** | Loop Gemini com tool_use + fallback Ollama |
| **Programas** | Abrir/fechar apps com cooldown e lock atômico |
| **Obsidian** | CRUD de notas no Vault |
| **Lotofácil** | Auditoria e consulta de Reis via bridge |
| **ChromaDB** | Base vetorial de conhecimento de Web Design |

---

## 📝 Changelog

### v5.0.0 (2026-05-24)
- **Agente IA com Google Gemini 2.0 Flash** — Loop completo de tool_use
- **11 ferramentas** — mouse, teclado, screenshot, arquivos, web, scripts, Obsidian
- **Histórico de 10 turnos** de contexto no agente
- **Fallback Ollama** (gemma2:2b) quando sem internet
- **Playwright em thread isolada** — não congela o tkinter
- **Screenshot restrito** — só ativa quando pedido explicitamente
- **Camada local de respostas** — hora, clima, notas, programas respondidos sem API

### v4.4.0
- Integração ChromaDB para Web Design Knowledge
- Consultas de design (tipografia, cores, layout, UX/UI)

### v4.3.0
- `_pode_ouvir` (Event) como único controlador do mic
- Loop bloqueante sem threads extras
- Cooldown + Lock atômico para programas
- UUID por WAV, anti-eco pós-fala

---

## ⚠️ Notas Importantes

- A chave da API do Gemini deve ter permissão para o modelo `gemini-2.0-flash`
- O microfone é calibrado automaticamente ao iniciar (2 segundos de silêncio)
- O botão "Calibrar" na GUI permite recalibrar manualmente
- Respostas do TTS usam a voz `pt-BR-AntonioNeural` (masculina)
- O sistema de auditoria Lotofácil requer confirmação por voz antes de processar

---

**Desenvolvido para Cornelio** 🏆

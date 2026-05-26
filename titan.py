# TITAN v5.0.0 - Assistente Pessoal
# ARQUITETURA v4.3.0:
#   - _pode_ouvir (Event) é o ÚNICO controlador do mic
#   - Só falar() mexe neste event — VAD apenas LÊ
#   - Inicialização: mic só liga APÓS saudação terminar
#   - Loop bloqueante: processar_comando é chamado direto (sem thread extra)
#   - Cooldown + Lock atômico para programas
#   - UUID por WAV, Get-Process array nativo
# NOVIDADE v5.0.0:
#   - Integração Web Design Knowledge (ChromaDB)

import os, sys, datetime, subprocess, re, tempfile, threading, asyncio, uuid
import time, requests, unicodedata
import json, base64, shutil
import pyautogui
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import scrolledtext
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import speech_recognition as sr
from dotenv import load_dotenv

load_dotenv()

HOME = os.path.expanduser("~")
VAULT_PATH = os.environ.get("VAULT_PATH", os.path.join(HOME, "Desktop", "VITORIA_LOTO"))
VITORIA_PATH = os.environ.get("VITORIA_PATH", os.path.join(HOME, "Desktop", "vitoria-loto"))
VITORIA_SCRIPTS = os.path.join(VITORIA_PATH, "_scripts")

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Imports do vitoria-loto movidos para dentro das funções

import re as _re

_REI_PATTERN = _re.compile(
    r"\b(?:como est[aá]|desempenho|resultado|status|consultar|ver)\b"
    r".*?\b[Rr](?:ei\s*)?(\d{2})\b",
    _re.IGNORECASE,
)

def _detectar_rei(texto: str):
    """Retorna 'R11'..'R15' se o comando mencionar um Rei, senão None."""
    m = _REI_PATTERN.search(texto)
    if m:
        numero = m.group(1)
        if numero in {"11", "12", "13", "14", "15"}:
            return f"R{numero}"
    return None

_bridge = None

# === WEB DESIGN KNOWLEDGE ===
_DESIGN_OK = False
_design_collection = None

def _init_design_kb():
    global _DESIGN_OK, _design_collection
    try:
        import chromadb
        client = chromadb.PersistentClient(
            path=os.path.join(os.path.expanduser("~"), "TITAN", "chromadb")
        )
        _design_collection = client.get_collection("web_design_knowledge")
        _DESIGN_OK = True
        print("[DESIGN] ChromaDB carregado OK")
    except Exception as e:
        _DESIGN_OK = False
        print(f"[DESIGN] ChromaDB não carregado: {e}")

# Inicia em background — não bloqueia o TITAN
threading.Thread(target=_init_design_kb, daemon=True).start()

# ============================================================
# CONFIGURACOES
# ============================================================
TITAN_VERSION   = "5.0.0"
SAMPLE_RATE     = 16000
LAT             = -21.1775
LON             = -47.8103

CHUNK_FRAMES    = 1600
SILENCIO_FIM    = 18
MAX_GRAVACAO    = 80
MARGEM_RUIDO    = 3.5
MIN_DURACAO_STT = 0.8
COOLDOWN_CMD    = 10.0

# ============================================================
# GEMINI — inicializado uma vez no topo
# ============================================================
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
_gemini_client  = None

def _bg_init():
    global _bridge, _gemini_client
    # Iniciar Ollama em background
    try:
        subprocess.Popen(['wsl', 'ollama', 'serve'], creationflags=subprocess.CREATE_NO_WINDOW)
    except:
        pass
    # Pre-caching pesados
    try:
        import playwright.sync_api
        import edge_tts
        from google import genai
        if _GEMINI_API_KEY:
            _gemini_client = genai.Client(api_key=_GEMINI_API_KEY)
    except:
        pass
    try:
        sys.path.insert(0, VITORIA_SCRIPTS)
        import consultar_reis
        import auditar_voz
        sys.path.insert(0, VITORIA_PATH)
        import vitoria_bridge
        _bridge = vitoria_bridge.VitoriaBridge()
    except:
        pass

threading.Thread(target=_bg_init, daemon=True).start()

# ============================================================
# ESTADO GLOBAL
# ============================================================
# _pode_ouvir: set=mic ativo  clear=mic surdo
# REGRA: só falar() e inicializar() escrevem neste event
_pode_ouvir    = threading.Event()
_programa_lock = threading.Lock()
_ultimo_cmd_t  = time.time() - COOLDOWN_CMD
_mic_ativo     = False
_thread_id     = 0
_ruido_base    = 600
_ultimo_proc   = time.time() - 10.0
_programas_abertos = set()
_aguardando_confirmacao_auditoria = False
_dezenas_pendentes = []

# ============================================================
# UTILITÁRIOS
# ============================================================
def normalizar(txt: str) -> str:
    return unicodedata.normalize('NFD', txt).encode('ascii','ignore').decode('utf-8').lower()

def _contar_notas():
    try:
        total = 0
        for root, dirs, files in os.walk(VAULT_PATH):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            total += len([f for f in files if f.endswith('.md')])
        return total
    except:
        return 0

# ============================================================
# GUI
# ============================================================
import random, math

janela = tk.Tk()
janela.title(f"TITAN v{TITAN_VERSION}")
janela.geometry("1280x720")
janela.configure(bg="#0a0f1e")

_is_fullscreen = True
janela.attributes('-fullscreen', True)

def _toggle_fullscreen(event=None):
    global _is_fullscreen
    _is_fullscreen = not _is_fullscreen
    janela.attributes('-fullscreen', _is_fullscreen)

janela.bind("<Escape>", _toggle_fullscreen)

def fechar_titan(event=None):
    try:
        subprocess.Popen(['wsl', '--', 'pkill', 'ollama'], creationflags=subprocess.CREATE_NO_WINDOW)
    except:
        pass
    janela.destroy()
    os._exit(0)

janela.protocol("WM_DELETE_WINDOW", fechar_titan)

canvas = tk.Canvas(janela, bg="#0a0f1e", highlightthickness=0)
canvas.pack(fill="both", expand=True)

_estado_texto = "INICIALIZANDO..."
_estado_cor = "#888888"
_mic_pulse_radius = 20
_mic_pulse_dir = 1
_mic_ativo_ui = False

class Particle:
    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(-0.5, 0.5)
        self.radius = random.uniform(1.5, 3.5)
        self.color = random.choice(["#ffffff", "#e0f0ff", "#b0d0ff", "#80b0ff"])
        self.shape = random.choice(["circle", "square"])

particles = []
_particles_initialized = False

def _update_ui():
    global _particles_initialized, _mic_pulse_radius, _mic_pulse_dir
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w <= 1 or h <= 1:
        w = janela.winfo_width()
        h = janela.winfo_height()

    if not _particles_initialized and w > 1:
        for _ in range(80):
            particles.append(Particle(w, h))
        _particles_initialized = True

    # Atualiza posição das partículas
    for p in particles:
        p.x += p.vx
        p.y += p.vy
        if p.x < 0 or p.x > w: p.vx *= -1
        if p.y < 0 or p.y > h: p.vy *= -1

    canvas.delete("all")
    
    # Desenha conexões neurais
    for i in range(len(particles)):
        for j in range(i + 1, len(particles)):
            p1 = particles[i]
            p2 = particles[j]
            dist = math.hypot(p1.x - p2.x, p1.y - p2.y)
            if dist < 120:
                canvas.create_line(p1.x, p1.y, p2.x, p2.y, fill="#1c2c54", tags="neural", width=1)

    # Desenha partículas
    for p in particles:
        if p.shape == "circle":
            canvas.create_oval(p.x - p.radius, p.y - p.radius, p.x + p.radius, p.y + p.radius, fill=p.color, outline="", tags="neural")
        else:
            canvas.create_rectangle(p.x - p.radius, p.y - p.radius, p.x + p.radius, p.y + p.radius, fill=p.color, outline="", tags="neural")

    # Texto de Estado
    # Adicionando tracking (espaçamento) no texto inserindo espaços
    texto_espacado = " ".join(list(_estado_texto))
    canvas.create_text(w/2, h/2 + 100, text=texto_espacado, font=("Segoe UI", 16, "bold"), fill=_estado_cor, tags="estado", justify="center")

    # Desenha botões inferiores
    cx = w / 2
    cy = h - 60
    spacing = 80
    _ICONS = [
        ("PIN", "\u25CE", 16),
        ("CAM", "\u25A3", 20),
        ("MIC", "\u25C9", 28),
        ("CHAT", "\u25A4", 20),
        ("SCREEN", "\u25A2", 20),
        ("MORE", "\u22EE", 20)
    ]
    start_x = cx - (len(_ICONS) - 1) * spacing / 2

    # Animação do MIC
    if "OUVINDO" in _estado_texto or _mic_ativo_ui:
        _mic_pulse_radius += 0.5 * _mic_pulse_dir
        if _mic_pulse_radius > 40: _mic_pulse_dir = -1
        if _mic_pulse_radius < 20: _mic_pulse_dir = 1
        mic_x = start_x + 2 * spacing
        canvas.create_oval(mic_x - _mic_pulse_radius, cy - _mic_pulse_radius, mic_x + _mic_pulse_radius, cy + _mic_pulse_radius, fill="#1c2c54", outline="", tags="bar")

    for i, (name, icon, size) in enumerate(_ICONS):
        x = start_x + i * spacing
        color = "#ffffff" if name == "MIC" else "#556688"
        canvas.create_text(x, cy, text=icon, font=("Segoe UI Symbol", size), fill=color, tags="bar")

    janela.after(30, _update_ui)

janela.after(100, _update_ui)

def log(msg, cor="sistema"):
    print(f"{msg}")

def _set_estado(txt, cor="#888888"):
    global _estado_texto, _estado_cor
    _estado_texto = txt.upper()
    _estado_cor = cor

def _on_canvas_click(event):
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    if w <= 1: return
    cx = w / 2
    cy = h - 60
    spacing = 80
    _ICONS = ["PIN", "CAM", "MIC", "CHAT", "SCREEN", "MORE"]
    start_x = cx - (len(_ICONS) - 1) * spacing / 2
    for i, name in enumerate(_ICONS):
        x = start_x + i * spacing
        if abs(event.x - x) < 30 and abs(event.y - cy) < 30:
            print(f"[UI] Clique no botão: {name}")
            if name == "MIC":
                interromper_fala()

canvas.bind("<Button-1>", _on_canvas_click)
janela.bind("<space>", lambda e: interromper_fala(e))

# ============================================================
# CALIBRAÇÃO
# ============================================================
def _calibrar():
    global _ruido_base
    log("Calibrando ruído (2s)...", cor="titan")
    amostras = []
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as s:
            for _ in range(20):
                chunk, _ = s.read(CHUNK_FRAMES)
                amostras.append(int(np.sqrt(np.mean(chunk.astype(np.float32)**2))))
        media = int(np.mean(amostras))
        _ruido_base = max(int(media * MARGEM_RUIDO), 1500)
        log(f"Ruído médio: {media} → Limiar: {_ruido_base}", cor="titan")
    except Exception as e:
        log(f"Erro calibração: {e}", cor="titan")
        _ruido_base = 600

# ============================================================
# VOZ — ÚNICO dono do _pode_ouvir
# ============================================================
async def _gerar_mp3(texto, tmp):
    import edge_tts
    await edge_tts.Communicate(texto, voice="pt-BR-AntonioNeural").save(tmp)

_audio_process = None

def _play_bloqueante(tmp):
    global _audio_process
    cmd = (
        'Add-Type -AssemblyName PresentationCore;'
        '$p=New-Object System.Windows.Media.MediaPlayer;'
        f'$p.Open("{tmp}");'
        'Start-Sleep -Milliseconds 400;'
        '$p.Play();'
        'do{Start-Sleep -Milliseconds 100}'
        'while($p.Position -lt $p.NaturalDuration.TimeSpan)'
    )
    _audio_process = subprocess.Popen(['powershell','-Command',cmd], creationflags=subprocess.CREATE_NO_WINDOW)
    _audio_process.wait()
    _audio_process = None

def interromper_fala(event=None):
    global _audio_process
    if _audio_process is not None:
        log("[UI] Interrompendo fala (barge-in)...", cor="sistema")
        try:
            _audio_process.kill()
        except:
            pass

def falar(texto: str):
    """
    Bloqueante.
    1) Surdia o mic (_pode_ouvir.clear)
    2) Gera e reproduz o áudio
    3) Aguarda eco dissipar
    4) Libera o mic (_pode_ouvir.set)
    """
    _pode_ouvir.clear()                      # SURDO primeiro
    _set_estado("falando...", "#ff6600")
    log(f"TITAN: {texto}", cor="titan")
    try:
        tmp = os.path.join(tempfile.gettempdir(), f"titan_{uuid.uuid4().hex}.mp3")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_gerar_mp3(texto, tmp))
        loop.close()
        _play_bloqueante(tmp)
        try: os.remove(tmp)
        except: pass
    except Exception as e:
        log(f"[VOZ] Erro: {e}", cor="titan")
    finally:
        time.sleep(0.5)                      # anti-eco: aguarda eco dissipar
        _pode_ouvir.set()                    # LIBERA o mic
        log("[MIC] Reativado.", cor="titan")
        _set_estado("aguardando voz...", "#888888")

# ============================================================
# VAD — só LÊ _pode_ouvir, jamais escreve
# ============================================================
def _capturar_vad(tid: int):
    gravando = False
    chunks   = []
    silencio = 0

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as stream:
            while _mic_ativo and tid == _thread_id:

                if not _pode_ouvir.is_set():
                    # Mic surdo — descarta estado e aguarda liberação
                    gravando = False
                    chunks   = []
                    silencio = 0
                    _pode_ouvir.wait(timeout=0.5)
                    # Janela cega: após liberar, descarta 0.5s de áudio (eco residual)
                    if _pode_ouvir.is_set():
                        n_blind = int(0.5 * SAMPLE_RATE / CHUNK_FRAMES)
                        for _ in range(n_blind):
                            if not _mic_ativo or tid != _thread_id or not _pode_ouvir.is_set():
                                break
                            stream.read(CHUNK_FRAMES)
                    continue

                chunk, _ = stream.read(CHUNK_FRAMES)
                rms = int(np.sqrt(np.mean(chunk.astype(np.float32)**2)))

                if not gravando:
                    if rms > _ruido_base:
                        log(f"[VAD] Detectado (RMS={rms}, limiar={_ruido_base})", cor="titan")
                        gravando = True
                        silencio = 0
                        chunks   = [chunk]
                        _set_estado("ouvindo...", "#00ff88")
                else:
                    chunks.append(chunk)
                    if rms < _ruido_base:
                        silencio += 1
                        if silencio >= SILENCIO_FIM:
                            dur = len(chunks) * CHUNK_FRAMES / SAMPLE_RATE
                            log(f"[VAD] Encerrado ({dur:.1f}s) → STT", cor="titan")
                            return np.concatenate(chunks, axis=0)
                    else:
                        silencio = 0

                if len(chunks) >= MAX_GRAVACAO:
                    return np.concatenate(chunks, axis=0)

    except Exception as e:
        log(f"[VAD] Erro: {e}", cor="titan")

    return None

# ============================================================
# LOOP DE ESCUTA — bloqueante, sequencial, sem threads extras
# ============================================================
def _loop_escuta(tid: int):
    _calibrar()
    log("Aguardando sua voz...", cor="titan")
    _set_estado("aguardando voz...", "#888888")

    while _mic_ativo and tid == _thread_id:
        audio = _capturar_vad(tid)
        if audio is None or not _mic_ativo or tid != _thread_id:
            break

        # Filtro de duração
        dur = len(audio) / SAMPLE_RATE
        if dur < MIN_DURACAO_STT:
            log(f"[VAD] Descartado: {dur:.1f}s", cor="titan")
            continue

        # Mic ainda disponível? (pode ter ficado surdo durante gravação)
        if not _pode_ouvir.is_set():
            log("[STT] Abortado: mic surdo.", cor="titan")
            continue

        _set_estado("reconhecendo...", "#ffaa00")

        # STT
        texto  = ""
        wav_p  = os.path.join(tempfile.gettempdir(), f"titan_{uuid.uuid4().hex}.wav")
        try:
            wav.write(wav_p, SAMPLE_RATE, audio)
            rec = sr.Recognizer()
            with sr.AudioFile(wav_p) as src:
                data = rec.record(src)
                texto = rec.recognize_google(data, language='pt-BR').lower()
            log(f"[STT] '{texto}'", cor="titan")
        except sr.UnknownValueError:
            _set_estado("aguardando voz...", "#888888")
            continue
        except Exception as e:
            log(f"[STT] Erro: {e}", cor="titan")
            _set_estado("aguardando voz...", "#888888")
            continue
        finally:
            try: os.remove(wav_p)
            except: pass

        # Filtro de comprimento
        if len(texto.split()) < 1 or texto.strip() == '':
            log(f"[STT] Descartado: '{texto}'", cor="titan")
            _set_estado("aguardando voz...", "#888888")
            continue

        # Checagem final antes de processar
        if not _pode_ouvir.is_set():
            log("[CMD] Abortado: mic surdo pós-STT.", cor="titan")
            continue

        janela.after(0, lambda t=texto: log(f"VOCÊ: {t}", cor="usuario"))
        _set_estado("processando...", "#ffaa00")

        # Processar — falar() dentro de _processar_comando é bloqueante
        # e surdia o mic sozinha antes de falar
        _processar_comando(texto)

# ============================================================
# PROGRAMAS
# ============================================================
PROGRAMAS_PS = {
    'calculadora':    (['CalculatorApp'], r'C:\Windows\System32\calc.exe'),
    'calc':           (['CalculatorApp'], r'C:\Windows\System32\calc.exe'),
    'spotify':        (['Spotify'],       'spotify:'),
    'chrome':         (['chrome'],        'chrome'),
    'notepad':        (['notepad'],       'notepad.exe'),
    'bloco de notas': (['notepad'],       'notepad.exe'),
    'whatsapp':       (['WhatsApp'],      'whatsapp:'),
    'terminal':       (['cmd'],           'cmd.exe'),
    'explorador':     (['explorer'],      'explorer.exe'),
    'cofre':          (['explorer'],      VAULT_PATH),
    'obsidian':       (['explorer'],      VAULT_PATH),
    'downloads':      (['explorer'],      'shell:Downloads'),
    'documentos':     (['explorer'],      'shell:Personal'),
    'desktop':        (['explorer'],      'shell:Desktop'),
}

def _abrir_programa(chave: str):
    global _ultimo_cmd_t
    log(f"[DBG] _abrir_programa ENTRADA: {chave} | lock={_programa_lock.locked()} | dt={time.time()-_ultimo_cmd_t:.1f}s | flag={chave in _programas_abertos}", cor="titan")
    agora = time.time()
    if agora - _ultimo_cmd_t < COOLDOWN_CMD:
        log(f"[COOLDOWN] {COOLDOWN_CMD-(agora-_ultimo_cmd_t):.1f}s restantes.", cor="titan")
        return
    if not _programa_lock.acquire(blocking=False):
        log("[LOCK] Abertura em andamento.", cor="titan")
        return
    _ultimo_cmd_t = agora
    try:
        nomes, app = PROGRAMAS_PS[chave]
        if chave in _programas_abertos:
            log(f"[FLAG] {chave} já foi aberto nesta sessão.", cor="titan")
            falar(f"{chave.capitalize()} já está aberto.")
            return

        if chave in ('cofre', 'obsidian', 'downloads', 'documentos', 'desktop'):
            subprocess.Popen(['explorer.exe', app], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "open", app, None, None, 1)

        _programas_abertos.add(chave)
        log(f"[FLAG] {chave} marcado como aberto.", cor="titan")
        falar(f"{chave.capitalize()} aberto.")
    except Exception as e:
        log(f"[ERR] {e}", cor="titan")
    finally:
        _programa_lock.release()

def _fechar_programa(chave: str):
    try:
        nomes, _ = PROGRAMAS_PS[chave]
        fechou_algo = False
        for nome_proc in nomes:
            # Alguns processos podem não ter o nome exato. No caso de 'WhatsApp', o Stop-Process -Name WhatsApp funciona.
            # No caso do chrome, Stop-Process -Name chrome.
            cmd = f"Stop-Process -Name {nome_proc} -Force -ErrorAction SilentlyContinue"
            res = subprocess.run(['powershell', '-Command', cmd], creationflags=subprocess.CREATE_NO_WINDOW)
            if res.returncode == 0:
                fechou_algo = True
        
        if fechou_algo:
            log(f"[FLAG] {chave} foi fechado.", cor="titan")
            falar(f"{chave.capitalize()} encerrado.")
            if chave in _programas_abertos:
                _programas_abertos.remove(chave)
        else:
            falar(f"Não encontrei {chave} rodando.")
    except Exception as e:
        log(f"[ERR] Falha ao fechar {chave}: {e}", cor="titan")
        falar(f"Erro ao tentar fechar {chave}.")

# ============================================================
# WEB DESIGN KNOWLEDGE
# ============================================================
def _perguntar_design(pergunta: str) -> str:
    if not _DESIGN_OK:
        return "Base de design não disponível no momento."
    try:
        resultados = _design_collection.query(
            query_texts=[pergunta],
            n_results=3
        )
        trechos = resultados['documents'][0]
        if not trechos:
            return "Não encontrei nada sobre design para essa pergunta."
        resumo = " ".join(trechos)[:600]
        return f'Segundo os livros de design: {resumo}'
    except Exception as e:
        return f"Erro ao consultar design: {e}"

# ============================================================
# PROCESSAMENTO DE COMANDOS
# ============================================================
VERBOS = ['abre','abrir','abra','inicia','iniciar','executa','executar','lanca','lancar']
VERBOS_FECHAR = ['fecha','fechar','feche','encerra','encerrar','mata','matar','fecha o','fecha a','fechar o','fechar a']


def _pesquisar_notas(termo: str) -> str:
    try:
        termo_norm = normalizar(termo)  # remove acentos
        resultados = []
        for root, dirs, files in os.walk(VAULT_PATH):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.endswith('.md'):
                    caminho = os.path.join(root, file)
                    nome_norm = normalizar(file.replace('.md', ''))
                    try:
                        with open(caminho, 'r', encoding='utf-8') as f:
                            conteudo_norm = normalizar(f.read())
                        # busca parcial — "agentes" encontra "agent", "agents"
                        if (termo_norm in conteudo_norm or
                            termo_norm in nome_norm or
                            nome_norm in termo_norm or  # "agents" dentro de "agentes"
                            any(termo_norm[:4] in p for p in [nome_norm, conteudo_norm[:500]])):
                            resultados.append(file.replace('.md', ''))
                    except:
                        pass
        if resultados:
            lista = ", ".join(resultados[:5])
            return f"Encontrei {len(resultados)} nota{'s' if len(resultados)>1 else ''}: {lista}."
        else:
            return f"Nenhuma nota encontrada com o termo {termo}."
    except Exception as e:
        return f"Erro na pesquisa: {e}"

_chat_history = []

def _tool_mover_mouse(x: int, y: int):
    try:
        pyautogui.moveTo(x, y)
        return f"Mouse movido para {x}, {y}."
    except Exception as e:
        return f"Erro: {e}"

def _tool_clicar(x: int, y: int, botao: str):
    try:
        pyautogui.click(x, y, button=botao)
        return f"Clique '{botao}' em {x}, {y} realizado."
    except Exception as e:
        return f"Erro: {e}"

def _tool_digitar_texto(texto: str):
    try:
        pyautogui.write(texto)
        return f"Texto digitado."
    except Exception as e:
        return f"Erro: {e}"

def _tool_screenshot():
    try:
        import io
        img = pyautogui.screenshot()
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        return f"Erro ao capturar tela: {e}"

def _tool_gerenciar_arquivo(acao: str, origem: str, destino: str = ""):
    try:
        if acao == "copiar":
            if os.path.isdir(origem): shutil.copytree(origem, destino)
            else: shutil.copy2(origem, destino)
            return "Copiado com sucesso."
        elif acao == "mover":
            shutil.move(origem, destino)
            return "Movido com sucesso."
        elif acao == "deletar":
            if os.path.isdir(origem): shutil.rmtree(origem)
            else: os.remove(origem)
            return "Deletado com sucesso."
        elif acao == "listar":
            items = os.listdir(origem)
            return f"Conteúdo de {origem}: {', '.join(items)}"
        elif acao == "criar":
            with open(origem, 'w', encoding='utf-8') as f:
                f.write(destino)
            return "Arquivo criado."
        return "Ação desconhecida."
    except Exception as e:
        return f"Erro ao gerenciar arquivo: {e}"

def _playwright_runner(url: str, res_dict: dict):
    try:
        from playwright.sync_api import sync_playwright
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            html = page.content()
            browser.close()
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            res_dict['texto'] = text[:2000]
    except Exception as e:
        res_dict['erro'] = f"Erro ao navegar: {e}"

def _tool_navegar_web(url: str):
    res = {}
    t = threading.Thread(target=_playwright_runner, args=(url, res))
    t.start()
    t.join()
    if 'erro' in res:
        return res['erro']
    return res.get('texto', '')

def _tool_executar_script(caminho_py: str):
    try:
        res = subprocess.run([sys.executable, caminho_py], capture_output=True, text=True, timeout=30)
        return f"Saída:\n{res.stdout}\nErros:\n{res.stderr}"
    except Exception as e:
        return f"Erro ao executar script: {e}"

TOOLS_DEF = [
    {"name": "abrir_programa", "description": "Abre um programa pelo nome (ex: chrome, calculadora, whatsapp).", "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}}, "required": ["nome"]}},
    {"name": "fechar_programa", "description": "Fecha um programa pelo nome.", "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}}, "required": ["nome"]}},
    {"name": "mover_mouse", "description": "Move o cursor para X, Y.", "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}},
    {"name": "clicar", "description": "Clica na tela.", "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "botao": {"type": "string", "enum": ["left", "right", "middle"]}}, "required": ["x", "y", "botao"]}},
    {"name": "digitar_texto", "description": "Digita via teclado.", "input_schema": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}},
    {"name": "screenshot", "description": "Captura tela e retorna em base64. USAR APENAS SE O USUÁRIO PEDIR EXPLICITAMENTE UM PRINT OU SCREENSHOT.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "gerenciar_arquivo", "description": "Copiar, mover, deletar, criar ou listar.", "input_schema": {"type": "object", "properties": {"acao": {"type": "string", "enum": ["copiar", "mover", "deletar", "listar", "criar"]}, "origem": {"type": "string"}, "destino": {"type": "string"}}, "required": ["acao", "origem"]}},
    {"name": "navegar_web", "description": "Abre URL e retorna HTML da página.", "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "executar_script", "description": "Executa um script Python.", "input_schema": {"type": "object", "properties": {"caminho_py": {"type": "string"}}, "required": ["caminho_py"]}},
    {"name": "pesquisar_obsidian", "description": "Pesquisa no cofre do Obsidian.", "input_schema": {"type": "object", "properties": {"termo": {"type": "string"}}, "required": ["termo"]}},
    {"name": "ler_nota", "description": "Lê uma nota específica.", "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}}, "required": ["nome"]}}
]

# TOOLS_DEF_GEMINI movido para uso dinâmico

def _executar_tool(nome_tool: str, args: dict):
    if nome_tool == "abrir_programa":
        _abrir_programa(args["nome"])
        return "Programa aberto (ou tentativa realizada)."
    elif nome_tool == "fechar_programa":
        _fechar_programa(args["nome"])
        return "Programa fechado (ou tentativa realizada)."
    elif nome_tool == "mover_mouse":
        return _tool_mover_mouse(args["x"], args["y"])
    elif nome_tool == "clicar":
        return _tool_clicar(args["x"], args["y"], args["botao"])
    elif nome_tool == "digitar_texto":
        return _tool_digitar_texto(args["texto"])
    elif nome_tool == "screenshot":
        return _tool_screenshot()
    elif nome_tool == "gerenciar_arquivo":
        return _tool_gerenciar_arquivo(args["acao"], args["origem"], args.get("destino", ""))
    elif nome_tool == "navegar_web":
        return _tool_navegar_web(args["url"])
    elif nome_tool == "executar_script":
        return _tool_executar_script(args["caminho_py"])
    elif nome_tool == "pesquisar_obsidian":
        return _pesquisar_notas(args["termo"])
    elif nome_tool == "ler_nota":
        return _ler_nota(args["nome"])
    return f"Ferramenta {nome_tool} não encontrada."

def _agente_ia_gemini(pergunta: str) -> str:
    global _chat_history
    
    if len(_chat_history) > 10:
        _chat_history = _chat_history[-10:]
        
    system_prompt = (
        "Você é TITAN, assistente pessoal do Cornelio rodando no Windows 11. "
        "Responda sempre em português. Seja direto e conciso — respostas serão convertidas em voz. "
        "Quando precisar executar algo no computador, use as ferramentas disponíveis. "
        "Nunca diga que não pode fazer algo sem antes tentar com as ferramentas."
    )
    
    try:
        if _gemini_client is None:
            return "Cliente Gemini ainda está carregando..."
            
        from google.genai import types
        TOOLS_DEF_GEMINI = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=t["name"],
                        description=t["description"],
                        parameters=t.get("input_schema")
                    ) for t in TOOLS_DEF
                ]
            )
        ]
        
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=TOOLS_DEF_GEMINI,
            temperature=0.7
        )
        
        _chat_history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=pergunta)])
        )
        
        while True:
            response = _gemini_client.models.generate_content(
                model='gemini-2.0-flash',
                contents=_chat_history,
                config=config
            )
            
            if response.candidates and response.candidates[0].content:
                _chat_history.append(response.candidates[0].content)
                
            function_calls = response.function_calls
            if function_calls:
                tool_responses = []
                for fc in function_calls:
                    log(f"[TITAN] Executando ferramenta: {fc.name}", cor="titan")
                    args_dict = dict(fc.args) if fc.args else {}
                    res = _executar_tool(fc.name, args_dict)
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": str(res)}
                        )
                    )
                _chat_history.append(
                    types.Content(role="user", parts=tool_responses)
                )
            else:
                return response.text if response.text else "Não consegui formular uma resposta em texto."
                
    except Exception as e:
        log(f"[GEMINI] Erro: {e}", cor="titan")
        raise

def _agente_ia(pergunta: str) -> str:
    try:
        return _agente_ia_gemini(pergunta)
    except Exception as e:
        log(f"[GEMINI] Falha ({e}). Acionando Ollama (Fallback)...", cor="titan")
        return _agente_ia_ollama(pergunta)

def _agente_ia_ollama(pergunta: str) -> str:
    try:
        # Ollama iniciado no _bg_init
        r = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": "gemma2:2b",
                "messages": [
                    {"role": "system", "content": "Você é TITAN, assistente pessoal do Cornelio. Responda em português, de forma direta e concisa. Não simule conversas."},
                    {"role": "user", "content": pergunta}
                ],
                "stream": False,
                "options": {
                    "num_predict": 150
                }
            },
            timeout=20
        )
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "Não consegui responder localmente.").strip()
    except Exception as e:
        log(f"[TITAN] Falha no Ollama ({e}).", cor="titan")
        return "Não consegui responder localmente nem pela internet."

def _limpar_para_voz(texto: str) -> str:
    texto = re.sub(r'[^\x00-\x7F\u00C0-\u024F\u1E00-\u1EFF\n]', ' ', texto)
    texto = re.sub(r'#+ ', '', texto)
    texto = re.sub(r'\*\*|__|\*|_|`', '', texto)
    texto = re.sub(r'\[\[.*?\]\]', '', texto)
    texto = re.sub(r'\[.*?\]\(.*?\)', '', texto)
    texto = re.sub(r'https?://\S+', '', texto)
    texto = re.sub(r'[|\\/<>]', ' ', texto)
    texto = re.sub(r'\n{2,}', ' ', texto)
    texto = re.sub(r'-{2,}', '', texto)
    texto = ' '.join(texto.split())
    return texto.strip()

def _ler_nota(nome_busca: str) -> str:
    try:
        nome_norm = normalizar(nome_busca)
        for root, dirs, files in os.walk(VAULT_PATH):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.endswith('.md'):
                    nome_arquivo = normalizar(file.replace('.md', ''))
                    if nome_norm in nome_arquivo or nome_arquivo in nome_norm or nome_norm[:4] in nome_arquivo:
                        caminho = os.path.join(root, file)
                        with open(caminho, 'r', encoding='utf-8') as f:
                            conteudo = f.read()
                        # limpa markdown e emojis para voz
                        conteudo = _limpar_para_voz(conteudo)
                        return conteudo[:800] if len(conteudo) > 800 else conteudo
        return f"Nota {nome_busca} não encontrada."
    except Exception as e:
        return f"Erro ao ler nota: {e}"

def _processar_comando(texto: str):
    global _ultimo_proc, _aguardando_confirmacao_auditoria, _dezenas_pendentes
    if not texto: return

    try:
        sys.path.insert(0, VITORIA_SCRIPTS)
        from auditar_voz import detectar_comando_auditoria, extrair_dezenas, frase_confirmacao, auditar, frase_resultado_voz, formatar_terminal, gravar_obsidian
        from consultar_reis import frase_para_voz, consultar_rei
        sys.path.insert(0, VITORIA_PATH)
        from vitoria_bridge import detectar_comando_vitoria
    except Exception as e:
        log(f"Erro ao importar Loto: {e}", cor="sistema")
        return

    agora = time.time()
    if agora - _ultimo_proc < 2.0:
        log(f"[CMD] Ignorado (cooldown): '{texto}'", cor="titan")
        return
    _ultimo_proc = agora

    n = normalizar(texto)

    if _aguardando_confirmacao_auditoria:
        if any(p in n for p in ["sim", "confirma", "pode", "isso"]):
            _aguardando_confirmacao_auditoria = False
            falar("Auditando...")
            resultado = auditar(_dezenas_pendentes)
            log("\n" + formatar_terminal(resultado) + "\n", cor="titan")
            falar(frase_resultado_voz(resultado))
            if gravar_obsidian(resultado):
                falar("Resultado gravado no Obsidian.")
            _dezenas_pendentes = []
            return
        elif any(p in n for p in ["nao", "cancela", "errado"]):
            _aguardando_confirmacao_auditoria = False
            _dezenas_pendentes = []
            falar("Auditoria cancelada. Pode repetir o jogo quando quiser.")
            return
        else:
            falar("Responda sim para confirmar ou não para cancelar.")
            return

    if detectar_comando_auditoria(n):
        dezenas = extrair_dezenas(n)
        confirmacao = frase_confirmacao(dezenas)
        falar(confirmacao)
        if len(dezenas) == 15:
            _dezenas_pendentes = dezenas
            _aguardando_confirmacao_auditoria = True
        return

    # ── Comandos vitoria-loto (bridge direto) ────────────────────────────────
    metodo, args = detectar_comando_vitoria(n)
    if metodo:
        if _bridge is None:
            falar("O sistema Loto está inicializando. Tente em alguns segundos.")
            return
        falar("Um momento...")
        try:
            frase, relatorio = getattr(_bridge, metodo)(*args)
            log(f"\n{relatorio}\n", cor="titan")
            falar(frase)
        except Exception as e:
            falar(f"Erro ao executar {metodo}: {e}")
        return

    if any(v in n for v in VERBOS):
        abriu = False
        for chave in PROGRAMAS_PS:
            if chave in n:
                _abrir_programa(chave)
                abriu = True
                return
        if not abriu:
            falar("Qual programa você quer abrir?")
            return

    if any(v in n for v in VERBOS_FECHAR):
        fechou = False
        for chave in PROGRAMAS_PS:
            if chave in n:
                _fechar_programa(chave)
                fechou = True
                return
        if not fechou:
            falar("Qual programa você quer fechar?")
            return

    if any(p in n for p in ['que horas','hora','horas sao']):
        falar(f"Agora são {datetime.datetime.now().strftime('%H horas e %M minutos')}.")
    elif any(p in n for p in ['que dia','data de hoje','qual a data']):
        meses = ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro']
        d = datetime.datetime.now()
        falar(f'Hoje é {d.day} de {meses[d.month-1]} de {d.year}.')
    elif any(p in n for p in ['ola','oi','bom dia','boa tarde','boa noite','tudo bem']):
        h = datetime.datetime.now().hour
        falar("Bom dia!" if h < 12 else "Boa tarde!" if h < 18 else "Boa noite!")
    elif any(p in n for p in ['clima','temperatura']):
        falar(_clima())
    elif any(p in n for p in ['seu nome','quem e voce','quem es tu','como se chama']):
        falar("Meu nome é TITAN, seu assistente pessoal versão 5.0.0.")
    elif any(p in n for p in ['ajuda','me ajuda','me ajude','ajude-me','help','comandos','o que voce faz','que voce faz','o que pode fazer','o que sabe','que voce sabe','sabe fazer','voce sabe','quais comandos']):
        falar(
            "Meus comandos são: "
            "abrir calculadora, abrir chrome, abrir spotify, abrir whatsapp, abrir terminal. "
            "Perguntar: que horas são, que dia é hoje, qual o clima, notícias, status. "
            "Obsidian: pesquise mais o termo, liste as notas. "
            "Design: pergunte sobre interface, layout, tipografia, cores, UX, UI. "
            "Sistema: status do sistema para ver CPU e memória. "
            "E também: qual seu nome, tchau."
        )
    elif any(p in n for p in ['noticias','novidades','ultimas noticias']):
        falar(_noticias())
    elif any(p in n for p in ['liste as notas','listar notas','quais notas','minhas notas']):
        notas = [f.replace('.md','') for f in os.listdir(VAULT_PATH) if f.endswith('.md')]
        falar(f"Você tem {len(notas)} notas: {', '.join(notas)}.")
    elif any(p in n for p in ['ler nota','leia nota','ver nota','mostrar nota','ler a nota','leia a nota','ver a nota','abra a nota','leia o arquivo']):
        for verbo in ['ler a nota','leia a nota','ver a nota','abra a nota','leia o arquivo','ler nota','leia nota','ver nota','mostrar nota']:
            if verbo in n:
                nome = n.split(verbo, 1)[1].strip()
                if nome:
                    conteudo = _ler_nota(nome)
                    falar(conteudo)
                else:
                    falar("Qual nota deseja que eu leia?")
                break
    elif any(p in n for p in ['crie uma nota','criar uma nota','nova nota']):
        for verbo in ['crie uma nota','criar uma nota','nova nota']:
            if verbo in n:
                conteudo = n.split(verbo, 1)[1].strip()
                if conteudo:
                    # Gera um título amigável baseado nas primeiras palavras
                    palavras = conteudo.split()[:4]
                    titulo_sugestao = "-".join(palavras).lower()
                    titulo_limpo = re.sub(r'[^a-z0-9-]', '', normalizar(titulo_sugestao))

                    if not titulo_limpo:
                        titulo_limpo = f"nota_{datetime.datetime.now().strftime('%H%M%S')}"

                    nome_arq = f"{titulo_limpo}.md"
                    caminho = os.path.join(VAULT_PATH, nome_arq)
                    try:
                        with open(caminho, 'w', encoding='utf-8') as f:
                            f.write(f"# {conteudo.capitalize()}\n\nNota criada em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
                        falar(f"Nota {titulo_limpo} criada com sucesso.")
                    except Exception as e:
                        falar(f"Erro ao criar nota: {e}")
                else:
                    falar("Diga o que deseja escrever na nota após o comando.")
                break
    elif any(p in n for p in ['atualizar lotofacil','atualiza lotofacil','baixar sorteio','novo sorteio']):
        falar("Atualizando Lotofácil e auditando o novo sorteio.")
        bat = os.path.join(VITORIA_PATH, "atualizar_e_auditar.bat")
        subprocess.Popen([bat], creationflags=subprocess.CREATE_NO_WINDOW)

    elif any(p in n for p in ['auditar ultimo','auditoria','auditar concurso']):
        falar("Rodando auditoria do último concurso no Obsidian.")
        script = os.path.join(VITORIA_SCRIPTS, "auditor_supremo.py")
        subprocess.Popen([sys.executable, script, '--ultimo'], creationflags=subprocess.CREATE_NO_WINDOW)

    elif _detectar_rei(n):
        rei = _detectar_rei(n)
        falar(f"Consultando {rei}...")
        frase = frase_para_voz(rei)
        falar(frase)
        relatorio = consultar_rei(rei)
        log(f"\n{relatorio}\n", cor="titan")

    elif 'status' in n:
        falar(f"TITAN online versão 5.0.0. {_contar_notas()} notas no cofre.")
    elif any(p in n for p in ['sair','encerrar','tchau','desligar']):
        falar("Até logo, Cornelio!")
        subprocess.Popen(['wsl', '--', 'pkill', 'ollama'],
            creationflags=subprocess.CREATE_NO_WINDOW)
        janela.after(2500, janela.destroy)
    elif any(p in n for p in ['pesquise','pesquisar','busque','buscar','procure','procurar']):
        # extrai o termo após o verbo
        for verbo in ['pesquise','pesquisar','busque','buscar','procure','procurar']:
            if verbo in n:
                termo = n.split(verbo, 1)[1].strip()
                if termo:
                    falar(_pesquisar_notas(termo))
                else:
                    falar("O que deseja pesquisar?")
                break
    elif any(p in n for p in [
        'poder de processamento','processamento','cpu',
        'memoria ram','ram','hardware','desempenho',
        'capacidade','quanto de memoria','status do sistema'
    ]):
        falar(_status_hardware())
    elif any(p in n for p in ['design','interface','layout','tipografia','cor para','paleta','ux','ui','fonte','botao','menu','tela']):
        falar("Consultando a base de design...")
        falar(_perguntar_design(texto))
    else:
        log(f"[IA] Consultando Agente Local (Ollama): '{texto}'", cor="titan")
        resposta = _agente_ia(texto)
        falar(resposta)

# ============================================================
# UTILIDADES
# ============================================================
def _status_hardware():
    import psutil
    cpu_pct = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq().current / 1000.0 if getattr(psutil, "cpu_freq", lambda: None)() else 0.0
    
    mem = psutil.virtual_memory()
    mem_used = mem.used / (1024**3)
    mem_total = mem.total / (1024**3)
    
    disk = psutil.disk_usage('/')
    disk_free = disk.free / (1024**3)
    
    return f"Meu processador está com {cpu_pct:.0f}% de uso, rodando a {cpu_freq:.1f} gigahertz. Memória RAM com {mem_used:.1f} de {mem_total:.0f} gigabytes utilizados. Disco com {disk_free:.0f} gigabytes livres."

def _clima():
    try:
        r = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
            f"&current=temperature_2m&timezone=America/Sao_Paulo", timeout=5)
        return f"Em Ribeirão Preto faz {r.json()['current']['temperature_2m']} graus."
    except:
        return "Sem conexão com o clima."

def _noticias():
    try:
        r = requests.get("https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", timeout=5)
        ts = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', r.text)[:3]
        return "Notícias: " + ". ".join(ts) if ts else "Sem notícias."
    except:
        return "Sem notícias."

# ============================================================
# INICIALIZAÇÃO
# ============================================================
# ============================================================
# LIVE API
# ============================================================
def _loop_live_api(tid: int):
    try:
        from google import genai
        from google.genai import types
        if not _GEMINI_API_KEY:
            raise Exception("API Key não encontrada.")
            
        client = genai.Client(api_key=_GEMINI_API_KEY)
        
        async def run_live():
            _set_estado("LIVE", "#00aaff")
            log("[LIVE] Iniciando conexão...", cor="titan")
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                system_instruction=types.Content(parts=[types.Part.from_text("Você é TITAN, assistente pessoal do Cornelio. Responda em português, de forma direta e concisa.")])
            )
            try:
                async with client.aio.live.connect(model="gemini-live-2.5-flash-preview", config=config) as session:
                    log("[LIVE] Conectado!", cor="titan")
                    
                    audio_queue = asyncio.Queue()
                    
                    def audio_callback(indata, frames, time, status):
                        if _pode_ouvir.is_set():
                            audio_queue.put_nowait(indata.copy())
                            
                    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16', callback=audio_callback)
                    stream.start()
                    
                    async def send_audio():
                        while _mic_ativo and tid == _thread_id:
                            data = await audio_queue.get()
                            try:
                                await session.send(input={"data": data.tobytes(), "mime_type": "audio/pcm;rate=16000"})
                            except AttributeError:
                                # Fallback se usarem um nome de metodo customizado na lib deles
                                await session.send_realtime_input([{"mime_type": "audio/pcm", "data": data.tobytes()}])
                                
                    async def receive_audio():
                        while _mic_ativo and tid == _thread_id:
                            async for response in session.receive():
                                server_content = response.server_content
                                if server_content and server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data:
                                            _pode_ouvir.clear() # Fica surdo enquanto toca
                                            try:
                                                audio_bytes = part.inline_data.data
                                                audio_arr = np.frombuffer(audio_bytes, dtype=np.int16)
                                                sd.play(audio_arr, samplerate=24000) # O modelo costuma retornar 24kHz
                                                sd.wait()
                                            except Exception as e:
                                                log(f"[LIVE] Erro ao tocar: {e}", cor="titan")
                                            finally:
                                                _pode_ouvir.set()
                                if response.tool_call:
                                    responses = []
                                    for fc in response.tool_call.function_calls:
                                        log(f"[LIVE] Executando ferramenta: {fc.name}", cor="titan")
                                        args_dict = dict(fc.args) if fc.args else {}
                                        res = _executar_tool(fc.name, args_dict)
                                        responses.append(
                                            types.FunctionResponse(
                                                name=fc.name,
                                                id=fc.id,
                                                response={"result": str(res)}
                                            )
                                        )
                                    await session.send(input=responses)
                                
                    await asyncio.gather(send_audio(), receive_audio())
                    stream.stop()
                    stream.close()
            except Exception as inner_e:
                log(f"[LIVE] Erro de sessao: {inner_e}", cor="titan")
                raise
                
        asyncio.run(run_live())
    except Exception as e:
        log(f"[LIVE] Falha ao iniciar Live API: {e}. Iniciando fallback para VAD...", cor="sistema")
        _loop_escuta(tid)

def _iniciar_mic():
    global _mic_ativo, _thread_id
    _mic_ativo = True
    _thread_id += 1
    # Usa a Live API como fluxo primário
    threading.Thread(target=_loop_live_api, args=(_thread_id,), daemon=True).start()

def inicializar():
    log(f"TITAN v{TITAN_VERSION} iniciado.", cor="titan")
    _pode_ouvir.clear()   # mic surdo até saudação terminar

    def _sequencia():
        h = datetime.datetime.now().hour
        saudacao = "Bom dia" if h < 12 else "Boa tarde" if h < 18 else "Boa noite"
        falar(f"{saudacao}, Cornelio.")  # falar() libera _pode_ouvir no finally
        _iniciar_mic()                 # mic só liga DEPOIS da saudação

    threading.Thread(target=_sequencia, daemon=True).start()

janela.after(500, inicializar)
log("[AGENTE] Gemini carregado OK sem erros", cor="titan")
janela.mainloop()

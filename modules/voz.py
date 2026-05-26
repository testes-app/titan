# ============================================================
# TITAN v1.0.0  Mdulo de Voz (Reconhecimento e Sntese)
# ============================================================
import threading
import queue
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import IDIOMA_VOZ, VELOCIDADE_FALA, VOLUME_FALA


class MotorVoz:
    """Motor de sntese de voz (Text-to-Speech)."""

    def __init__(self):
        self._engine = None
        self._lock = threading.Lock()
        self._inicializar()

    def _inicializar(self):
        """Inicializa o motor pyttsx3."""
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", VELOCIDADE_FALA)
            self._engine.setProperty("volume", VOLUME_FALA)
            
            # Tentar usar voz em portugus
            voices = self._engine.getProperty("voices")
            for voice in voices:
                if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
                    self._engine.setProperty("voice", voice.id)
                    break
            
            self.disponivel = True
        except Exception as e:
            print(f"[Voz] Motor TTS no disponvel: {e}")
            self.disponivel = False

    def falar(self, texto: str):
        """Fala o texto usando TTS."""
        if not self.disponivel or not self._engine:
            print(f"[TITAN diz]: {texto}")
            return
        
        def _falar_thread():
            with self._lock:
                try:
                    self._engine.say(texto)
                    self._engine.runAndWait()
                except Exception as e:
                    print(f"[Voz] Erro ao falar: {e}")
        
        thread = threading.Thread(target=_falar_thread, daemon=True)
        thread.start()

    def parar(self):
        """Para a fala atual."""
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass


class OuvidorVoz:
    """Reconhecimento de voz (Speech-to-Text)."""

    def __init__(self):
        self._recognizer = None
        self._microphone = None
        self.disponivel = False
        self.ouvindo = False
        self._fila = queue.Queue()
        self._inicializar()

    def _inicializar(self):
        """Inicializa o reconhecedor de voz."""
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.pause_threshold = 1.0
            
            try:
                self._microphone = sr.Microphone()
                # Calibrar rudo ambiente
                with self._microphone as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self.disponivel = True
            except Exception as mic_error:
                print(f"[Voz] Microfone (PyAudio) falhou: {mic_error}")
                self._microphone = None
                self.disponivel = False
                
        except Exception as e:
            print(f"[Voz] Biblioteca SpeechRecognition no disponvel: {e}")
            self.disponivel = False

    def ouvir(self, timeout: int = 5) -> dict:
        """
        Escuta o microfone e retorna o texto reconhecido.
        
        Returns:
            dict com 'sucesso', 'texto' e 'confianca'
        """
        if not self.disponivel:
            return {
                "sucesso": False,
                "texto": "",
                "erro": "Microfone no disponvel"
            }
        
        import speech_recognition as sr
        
        try:
            self.ouvindo = True
            with self._microphone as source:
                audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
            
            self.ouvindo = False
            
            # Reconhecer usando Google Speech API
            texto = self._recognizer.recognize_google(audio, language=IDIOMA_VOZ)
            
            return {
                "sucesso": True,
                "texto": texto,
                "erro": None
            }
        except sr.WaitTimeoutError:
            self.ouvindo = False
            return {
                "sucesso": False,
                "texto": "",
                "erro": "Tempo limite  no detectei fala"
            }
        except sr.UnknownValueError:
            self.ouvindo = False
            return {
                "sucesso": False,
                "texto": "",
                "erro": "No consegui entender"
            }
        except sr.RequestError as e:
            self.ouvindo = False
            return {
                "sucesso": False,
                "texto": "",
                "erro": f"Erro de conexo: {e}"
            }
        except Exception as e:
            self.ouvindo = False
            return {
                "sucesso": False,
                "texto": "",
                "erro": f"Erro: {e}"
            }

    def ouvir_async(self, callback):
        """Escuta de forma assncrona e chama o callback com o resultado."""
        def _thread():
            resultado = self.ouvir()
            callback(resultado)
        
        thread = threading.Thread(target=_thread, daemon=True)
        thread.start()
        return thread

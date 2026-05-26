# TITAN - Modulo de Voz com sounddevice
# Compativel com Python 3.14

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import speech_recognition as sr
import pyttsx3
import tempfile
import os

# --- CONFIGURACAO ---
SAMPLE_RATE = 16000
DURACAO_ESCUTA = 6  # segundos de escuta
VOLUME_MINIMO = 500  # ignora silencio abaixo deste nivel

engine = pyttsx3.init()

def configurar_voz():
    """Configura voz em portugues"""
    try:
        voices = engine.getProperty('voices')
        for voice in voices:
            if 'brazil' in voice.name.lower() or 'portuguese' in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        engine.setProperty('rate', 175)
        engine.setProperty('volume', 1.0)
    except Exception as e:
        print(f"Erro ao configurar voz: {e}")

def falar(texto):
    """TITAN fala em voz alta"""
    print(f"\nROBO TITAN: {texto}")
    try:
        engine.say(texto)
        engine.runAndWait()
    except Exception as e:
        print(f"Erro ao falar: {e}")

def ouvir():
    """Captura voz usando sounddevice e retorna texto"""
    print("\nOUVINDO... (fale agora por 6 segundos)")
    
    try:
        # Grava audio
        audio = sd.rec(
            int(DURACAO_ESCUTA * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16'
        )
        sd.wait()  # Espera terminar a gravacao

        # Verifica se tem audio (nao e silencio puro)
        volume = np.abs(audio).mean()
        if volume < VOLUME_MINIMO:
            print("AVISO: Silencio detectado - fale mais perto do microfone")
            return ""

        # Salva em arquivo WAV temporario
        wav_path = os.path.join(tempfile.gettempdir(), "titan_temp.wav")
        wav.write(wav_path, SAMPLE_RATE, audio)

        # Reconhece com Google
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            texto = recognizer.recognize_google(audio_data, language='pt-BR')
            print(f"VOCE DISSE: {texto}")
            return texto.lower()

    except sr.UnknownValueError:
        print("AVISO: Nao entendi - tente falar mais devagar")
        return ""
    except sr.RequestError:
        print("Erro: Sem conexao para reconhecimento de voz.")
        return ""
    except Exception as e:
        print(f"ERRO ao ouvir: {e}")
        return ""
    finally:
        # Limpa arquivo temporario
        try:
            if 'wav_path' in locals() and os.path.exists(wav_path):
                os.remove(wav_path)
        except:
            pass


# --- TESTE RAPIDO ---
if __name__ == "__main__":
    print("=" * 50)
    print("  TITAN - Teste de Voz com sounddevice")
    print("=" * 50)

    configurar_voz()

    print("\n[1/2] Testando sintese de voz...")
    falar("TITAN voz funcionando com sounddevice!")
    print("  OK Voz OK!")

    print("\n[2/2] Testando microfone...")
    print("  Fale uma frase curta agora...")
    resultado = ouvir()

    if resultado:
        print(f"\n  SUCESSO! Captado: '{resultado}'")
        falar(f"Voce disse: {resultado}")
    else:
        print("\n  AVISO: Nada captado - verifique o microfone")

    print("\n" + "=" * 50)
    print("Teste concluido!")

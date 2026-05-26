@echo off
title INSTALADOR TITAN v1.0.0
echo ==========================================
echo    FIX: INSTALANDO MICROFONE (PYAUDIO)
echo ==========================================
echo.
echo 1/3 Instalando ferramentas base...
python -m pip install --upgrade pip
python -m pip install pyttsx3 SpeechRecognition pywin32 comtypes

echo.
echo 2/3 Tentativa 1: Instalacao direta do PyAudio...
python -m pip install pyaudio

echo.
echo 3/3 Tentativa 2: Caso a primeira falhe (via pipwin)...
python -m pip install pipwin
python -m pip install wheel
python -m pipwin install pyaudio

echo.
echo ==========================================
echo TUDO PRONTO! Tente abrir o TITAN agora.
echo Se o erro do 'pipwin' aparecer de novo, ignore, 
echo pois a Tentativa 1 pode ter funcionado!
echo ==========================================
pause

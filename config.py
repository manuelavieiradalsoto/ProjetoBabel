# config.py
import os

CAMINHO_EXECUTOR_PIPER = "/home/manuela/Desktop/OFFLINE_CAPTURA_DE_AUDIO.manu.linux/myenv/bin/piper" 
PASTA_VOZ = "/home/manuela/Desktop/OFFLINE_CAPTURA_DE_AUDIO.manu.linux/voices"
MODELO_VOZ = os.path.join(PASTA_VOZ, "en_US-amy-medium.onnx")
PASTA_SAIDA = "outputs"
MODELO_RECONHECIMENTO_VOZ = "vosk-model-pt-fb-v0.1.1-pruned"
MODELO_TRADUCAO = "translate-pb_en-1_9.argosmodel"

SAMPLE_RATE = 16000
CHUNK_SIZE = 4096
FORMATO_AUDIO = 8 #pyaudio.paInt16
CANAIS_AUDIO = 1

# main.py
import os
import sys
import asyncio
import pyaudio
import pygame
from vosk import KaldiRecognizer

from config import SAMPLE_RATE, CHUNK_SIZE, FORMATO_AUDIO, CANAIS_AUDIO
from processamento import inicializar_ambiente, escuta_reconhece_traduz, gerando_arquivo_audio, tarefa_toca_audio

async def main():
    modelo_vosk = inicializar_ambiente()

    try:
        p = pyaudio.PyAudio()
        escuta = p.open(
            format=FORMATO_AUDIO,
            channels=CANAIS_AUDIO,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        reconhecimento_audio_vosk = KaldiRecognizer(modelo_vosk, SAMPLE_RATE)
    except Exception as e:
        print(f"***ERRO ao inicializar PyAudio: {e}")
        sys.exit(1)

    os.system('cls' if os.name == 'nt' else 'clear')
    
    fila_TEXTO = asyncio.Queue()
    fila_AUDIO = asyncio.Queue()

    listener = asyncio.create_task(escuta_reconhece_traduz(escuta, reconhecimento_audio_vosk, fila_TEXTO))
    generator = asyncio.create_task(gerando_arquivo_audio(fila_TEXTO, fila_AUDIO))
    player = asyncio.create_task(tarefa_toca_audio(fila_AUDIO))

    try:
        await asyncio.gather(listener, generator, player)
    except KeyboardInterrupt:
        print("\nInterrupção por teclado. Encerrando...")
    finally:
        if escuta:
            escuta.stop_stream()
            escuta.close()
        if p:
            p.terminate()
        pygame.quit()

if __name__ == "__main__":
    pygame.mixer.init()
    asyncio.run(main())
# processamento.py
import os
import sys
import json
import time
import asyncio
import pygame
import datetime
from vosk import Model
from argostranslate import package, translate
from subprocess import run, PIPE

from config import (
    CAMINHO_EXECUTOR_PIPER, MODELO_VOZ, PASTA_SAIDA,
    MODELO_RECONHECIMENTO_VOZ, MODELO_TRADUCAO,
    SAMPLE_RATE, CHUNK_SIZE
)


tempo_inicial = datetime.datetime.now()
def format_time():
    tempo = datetime.datetime.now() - tempo_inicial
    return str(tempo).split('.')[0] + '.' + str(int(tempo.microseconds / 10000))

def inicializar_ambiente():
    print(f"[{format_time()}] ***Inicializando o ambiente...")
    if not os.path.exists(PASTA_SAIDA):
        os.makedirs(PASTA_SAIDA)
        print(f"[{format_time()}] *-*-*Pasta '{PASTA_SAIDA}' criada para receber arquivos de áudio.")
    else:
        for item in os.listdir(PASTA_SAIDA):
            caminho_completo = os.path.join(PASTA_SAIDA, item)
            if os.path.isfile(caminho_completo):
                os.remove(caminho_completo)

    try:
        print(f"[{format_time()}] ***Carregando ARGOSTRANSLATE...")
        if not os.path.exists(MODELO_TRADUCAO):
            print(f"[{format_time()}] ***ERRO: '{MODELO_TRADUCAO}' não foi encontrado.")
            sys.exit(1)
        package.install_from_path(MODELO_TRADUCAO)

        # Download and install Argos Translate package
        #package.update_package_index()
        #available_packages = package.get_available_packages()
        #package_to_install = next(
        #    filter(
        #        lambda x: x.from_code == "pt" and x.to_code == "en", available_packages
        #    )
        #)
        #package.install_from_path(package_to_install.download())
        
        # --- ADIÇÃO DA SOLUÇÃO ---
        print(f"[{format_time()}] ***Pré-carregando o modelo do Argos Translate para evitar atrasos...")
        # Você pode usar um texto de teste em português (pt) e traduzi-lo para inglês (en)
        # para garantir que o modelo de destino também seja carregado.
        translate.translate("ola mundo", "pt", "en")
        print(f"[{format_time()}] *-*-*-*-*-*[PT] ---> [EN] PRONTO.")
    except Exception as e:
        print(f"[{format_time()}] ***ERRO: ARGOSTRANSLATE não foi carregado. Erro: {e}")
        sys.exit(1)

    try:
        if not os.path.exists(MODELO_RECONHECIMENTO_VOZ):
            print(f"[{format_time()}] ***ERRO: Modelo: '{MODELO_RECONHECIMENTO_VOZ}' não foi encontrado!")
            sys.exit(1)
        print(f"[{format_time()}] *-*-*Modelo encontrado: {MODELO_RECONHECIMENTO_VOZ}")
        vosk_model = Model(MODELO_RECONHECIMENTO_VOZ)
        return vosk_model
    except Exception as e:
        print(f"[{format_time()}] ***ERRO ao carregar modelo Vosk: {e}")
        sys.exit(1)


async def tts(texto):
    if not os.path.exists(CAMINHO_EXECUTOR_PIPER) or not os.path.exists(MODELO_VOZ):
        print(f"[{format_time()}] ***Erro: Caminho do Piper ou modelo ONNX inválido.")
        return None
    
    timestamp = int(time.time() * 1000)
    nome_audio = os.path.join(PASTA_SAIDA, f"translated_audio_{timestamp}.wav")
    
    try:
        cmd = [
            CAMINHO_EXECUTOR_PIPER,
            "--model", MODELO_VOZ,
            "--output_file", nome_audio,
            "--text", texto,
            "--input-espeak"
        ]
        
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run, cmd, PIPE)
        
        if os.path.exists(nome_audio) and os.path.getsize(nome_audio) > 0:
            print(f"[{format_time()}] ***Áudio gerado: '{os.path.basename(nome_audio)}'")
            return nome_audio
        else:
            print(f"[{format_time()}] ***Erro: O arquivo de áudio não foi criado ou está vazio.")
            return None
    except Exception as e:
        print(f"[{format_time()}] ***Erro na geração do TTS com Piper: {e}")
        return None

async def toca_deleta_audio(temp_audio_file):
    if not temp_audio_file or not os.path.exists(temp_audio_file):
        print(f"[{format_time()}] Aviso: Arquivo de áudio não encontrado para reprodução.")
        return
        
    try:
        print(f"[{format_time()}] Reproduzindo tradução...")
        pygame.mixer.music.load(temp_audio_file)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"[{format_time()}] Erro na reprodução do áudio: {e}")
    finally:
        try:
            pygame.mixer.music.unload()
            os.remove(temp_audio_file)
            print(f"[{format_time()}] Arquivo temporário excluído: '{os.path.basename(temp_audio_file)}'")
        except Exception as e:
            print(f"[{format_time()}] Erro ao excluir o arquivo de áudio: {e}")


async def gerando_arquivo_audio(queue_texto, queue_audio):
    while True:
        texto = await queue_texto.get()
        arquivo_de_audio = await tts(texto)
        if arquivo_de_audio:
            await queue_audio.put(arquivo_de_audio)
        queue_texto.task_done()

async def tarefa_toca_audio(queue_audio):
    while True:
        arquivo_de_audio = await queue_audio.get()
        await toca_deleta_audio(arquivo_de_audio)
        queue_audio.task_done()

async def escuta_reconhece_traduz(stream, recnhecedor_vosk, fila_texto):
    loop = asyncio.get_running_loop()
    print(f"\n[{format_time()}] Fale agora...")

    while True:
        data = await loop.run_in_executor(None, stream.read, CHUNK_SIZE, False)
        
        if recnhecedor_vosk.AcceptWaveform(data):
            resultado_json = json.loads(recnhecedor_vosk.Result())
            text = resultado_json.get('text', '')
            
            if text:
                cleaned_text = text.lower().strip()
                if cleaned_text.startswith(" "):
                    cleaned_text = cleaned_text[len(" "):].strip()
                
                if cleaned_text:
                    print(f"\r[{format_time()}] [PT]: {cleaned_text}", end='\n')
                    try:
                        translated_text = await loop.run_in_executor(
                            None, translate.translate, cleaned_text, "pt", "en"
                        )
                        print(f"[{format_time()}] [EN]: {translated_text}")
                        await fila_texto.put(translated_text)
                    except Exception as e:
                        print(f"[{format_time()}] Erro na tradução: {e}")
        else:
            partial_json = json.loads(recnhecedor_vosk.PartialResult())
            partial = partial_json.get('partial', '')
            sys.stdout.write(f'\r[{format_time()}] {partial}')
            sys.stdout.flush()

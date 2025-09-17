import os
import sys
import json
import pyaudio
import time
import asyncio
import pygame
import datetime
import glob
from vosk import Model, KaldiRecognizer
from argostranslate import package, translate
from subprocess import run, PIPE

# --- FUNÇÃO PARA FORMATAR O TEMPO ---
start_time = datetime.datetime.now()

def format_time():
    """Formata o tempo decorrido em hh:mm:ss.ms"""
    elapsed_time = datetime.datetime.now() - start_time
    return str(elapsed_time).split('.')[0] + '.' + str(int(elapsed_time.microseconds / 10000))

# --- CONFIGURAÇÃO DO PIPER TTS ---
PIPER_EXECUTABLE_PATH = "C:/Users/Manuela Dalsoto/Desktop/OFFLINE CAPTURA DE AUDIO.manu/venv/Scripts/piper.exe"
VOICES_DIR = os.path.join(os.path.dirname(__file__), "Voices")
MODEL_ONNX_PATH = os.path.join(VOICES_DIR, "en_US-amy-medium.onnx")

# --- CONFIGURAÇÃO DA PASTA DE SAÍDA ---
OUTPUTS_DIR = "outputs"
if not os.path.exists(OUTPUTS_DIR):
    os.makedirs(OUTPUTS_DIR)
    print(f"[{format_time()}] Pasta '{OUTPUTS_DIR}' criada para arquivos de áudio.")
else:
    for file in glob.glob(os.path.join(OUTPUTS_DIR, "*")):
        os.remove(file)

# --- CONFIGURAÇÃO E VERIFICAÇÃO DOS MODELOS ---
model_path = "vosk-model-pt-fb-v0.1.1-pruned"
if not os.path.exists(model_path):
    print(f"[{format_time()}] Modelo Vosk '{model_path}' não foi encontrado. Por favor, verifique o caminho.")
    exit(1)
print(f"[{format_time()}] Modelo Vosk encontrado: {model_path}")

try:
    vosk_model = Model(model_path)
except Exception as e:
    print(f"[{format_time()}] Erro ao carregar o modelo Vosk: {e}")
    exit(1)

# --- INICIALIZAÇÃO DO ARGOS TRANSLATE ---
local_argos_package_path = "translate-pb_en-1_9.argosmodel"
try:
    print(f"[{format_time()}] Verificando e carregando pacote do Argos Translate...")
    if not os.path.exists(local_argos_package_path):
        print(f"[{format_time()}] Erro: O arquivo '{local_argos_package_path}' não foi encontrado.")
        print(f"[{format_time()}] Certifique-se de que o arquivo está na mesma pasta do script.")
        exit(1)
    package.install_from_path(local_argos_package_path)
    print(f"[{format_time()}] Pacote pt->en do Argos Translate está pronto.")
    
    # --- PRÉ-CARREGAMENTO DO MODELO NA MEMÓRIA ---
    print(f"[{format_time()}] Pré-carregando o modelo do Argos Translate...")
    translate.translate("hello", "en", "pt")
    print(f"[{format_time()}] Pré-carregamento concluído.")
    
except Exception as e:
    print(f"[{format_time()}] Aviso: Não foi possível carregar o pacote do Argos Translate. Erro: {e}")

# --- FILAS PARA COMUNICAR ENTRE AS TAREFAS ASYNCIO ---
generation_queue = asyncio.Queue()
play_queue = asyncio.Queue()

# --- FUNÇÃO PARA GERAR O ÁUDIO TEMPORÁRIO (NÃO BLOQUEANTE) ---
async def generate_tts(text_to_speak):
    """
    Gera áudio usando o executável do Piper TTS e salva em arquivo temporário.
    """
    if not os.path.exists(PIPER_EXECUTABLE_PATH) or not os.path.exists(MODEL_ONNX_PATH):
        print(f"[{format_time()}] Erro: Caminho do Piper ou modelo ONNX inválido.")
        return None
    
    timestamp = int(time.time() * 1000)
    temp_audio_file = os.path.join(OUTPUTS_DIR, f"translated_audio_{timestamp}.wav")
    
    try:
        # Comando para chamar o Piper.exe com o argumento '--input-espeak'
        cmd = [
            PIPER_EXECUTABLE_PATH,
            "--model", MODEL_ONNX_PATH,
            "--output_file", temp_audio_file,
            "--text", text_to_speak,
            "--input-espeak"  # Adiciona o pré-processamento com eSpeak
        ]
        
        # Executa o comando em um executor para não bloquear o loop de eventos
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run, cmd, PIPE)
        
        if os.path.exists(temp_audio_file) and os.path.getsize(temp_audio_file) > 0:
            print(f"[{format_time()}] Áudio gerado: '{os.path.basename(temp_audio_file)}'")
            return temp_audio_file
        else:
            print(f"[{format_time()}] Erro: O arquivo de áudio não foi criado ou está vazio.")
            return None
            
    except Exception as e:
        print(f"[{format_time()}] Erro na geração do TTS com Piper: {e}")
        return None

# --- FUNÇÃO PARA REPRODUZIR E EXCLUIR O ÁUDIO (BLOQUEANTE, mas em sua própria tarefa) ---
async def play_and_delete_tts(temp_audio_file):
    """
    Reproduz o arquivo de áudio temporário e o exclui.
    """
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

# --- COROUTINE PARA GERAR ÁUDIO DA FILA DE GERAÇÃO ---
async def generate_audio_task():
    """Consome a fila de texto, gera o áudio e o coloca na fila de reprodução."""
    while True:
        text_to_speak = await generation_queue.get()
        audio_file = await generate_tts(text_to_speak)
        if audio_file:
            await play_queue.put(audio_file)
        generation_queue.task_done()

# --- COROUTINE PARA REPRODUZIR ÁUDIO DA FILA DE REPRODUÇÃO ---
async def play_audio_task():
    """Consome a fila de áudio e chama a função de reprodução e exclusão."""
    while True:
        audio_file = await play_queue.get()
        await play_and_delete_tts(audio_file)
        play_queue.task_done()

# --- COROUTINE PARA OUVIR E PROCESSAR A FALA ---
async def listen_and_process(stream, recognizer):
    """Ouve o microfone, reconhece a fala, traduz e coloca o resultado na fila de geração."""
    loop = asyncio.get_running_loop()
    chunk_size = 4096
    print(f"\n[{format_time()}] Fale agora...")

    while True:
        data = await loop.run_in_executor(None, stream.read, chunk_size, False)
        
        if recognizer.AcceptWaveform(data):
            result_json = json.loads(recognizer.Result())
            text = result_json.get('text', '')
            
            if text:
                # --- LÓGICA DE LIMPEZA DE TEXTO APRIMORADA ---
                words_to_remove = ["texto", "text"]
                cleaned_text = text.lower().strip()
                
                for word in words_to_remove:
                    if cleaned_text.startswith(word + " "):
                        cleaned_text = cleaned_text[len(word + " "):].strip()
                        break
                
                if cleaned_text:
                    print(f"\r[{format_time()}] [PT]: {cleaned_text}", end='\n')
                    
                    try:
                        translated_text = translate.translate(cleaned_text, "pt", "en")
                        print(f"[{format_time()}] [EN]: {translated_text}")
                        
                        await generation_queue.put(translated_text)
                        
                    except Exception as e:
                        print(f"[{format_time()}] Erro na tradução: {e}")
        else:
            partial_json = json.loads(recognizer.PartialResult())
            partial = partial_json.get('partial', '')
            sys.stdout.write(f'\r[{format_time()}] {partial}')
            sys.stdout.flush()

# --- Ponto de entrada do programa ---
async def main(stream, recognizer):
    listener = asyncio.create_task(listen_and_process(stream, recognizer))
    generator = asyncio.create_task(generate_audio_task())
    player = asyncio.create_task(play_audio_task())
    await asyncio.gather(listener, generator, player)

if __name__ == "__main__":
    sample_rate = 16000
    chunk_size = 4096
    format = pyaudio.paInt16
    channels = 1
    
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=format, channels=channels, rate=sample_rate, input=True, frames_per_buffer=chunk_size)
        recognizer = KaldiRecognizer(vosk_model, sample_rate)
    except Exception as e:
        print(f"[{format_time()}] Erro ao inicializar PyAudio: {e}")
        sys.exit(1)

    os.system('cls' if os.name == 'nt' else 'clear')
    try:
        pygame.mixer.init()
        asyncio.run(main(stream, recognizer))
    except KeyboardInterrupt:
        print(f"\n[{format_time()}] Interrupção por teclado. Encerrando...")
    finally:
        if 'stream' in locals() and stream is not None:
            stream.stop_stream()
            stream.close()
        if 'p' in locals() and p is not None:
            p.terminate()
        if 'pygame' in sys.modules:
            pygame.quit()
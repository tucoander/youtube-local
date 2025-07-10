from flask import Flask, request, send_file, redirect, url_for, render_template, send_from_directory, Response, stream_with_context, jsonify
import subprocess
import os
import re
import json 

def extrair_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

def carregar_info(video_id):
    json_path = os.path.join(DOWNLOAD_FOLDER, f'{video_id}.info.json')
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def carregar_videos():
    videos = []

    for filename in os.listdir(DOWNLOAD_FOLDER):
        if filename.endswith('.mp4'):
            video_id = filename.replace('.mp4', '')
            info = carregar_info(video_id)

            if info:
                videos.append({
                    'id': video_id,
                    'title': info.get('title'),
                    'channel': info.get('uploader'),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail')
                })
            else:
                videos.append({
                    'id': video_id,
                    'title': video_id,
                    'channel': 'N/A',
                    'duration': 'N/A',
                    'thumbnail': None
                })

    return videos



app = Flask(__name__, static_folder='static', template_folder='templates')
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

YTDLP_PATH = r'C:\Users\faa5lov\Documents\Apps\Video\yt-dlp.exe'  # Substitua pelo caminho real
FFMPEG_PATH = r"C:\Users\faa5lov\Documents\Apps\Video\ffmpeg-master-latest-win64-gpl-shared\bin\ffmpeg.exe"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/baixar')
def baixar():
    url = request.args.get('url')
    if not url:
        return "URL inválida", 400

    video_id = extrair_video_id(url)
    output_path = os.path.join(DOWNLOAD_FOLDER, f'{video_id}.mp4')

    try:
        
        subprocess.run([
            YTDLP_PATH,
            '--ffmpeg-location', FFMPEG_PATH,
            '--no-playlist',
            '--ignore-errors',
            '--merge-output-format', 'mp4',
            '--write-info-json',
            '-f', 'bestvideo[height>=720]+bestaudio/best[height>=720]',
            '-o', os.path.join(DOWNLOAD_FOLDER, f'{video_id}.%(ext)s'),
            url
        ], check=True)

    except subprocess.CalledProcessError as e:
        return f"Erro ao executar yt-dlp: {e}", 500

    return redirect(url_for('assistir', video_id=video_id))

@app.route('/assistir/<video_id>')
def assistir(video_id):
    return render_template('player.html', video_id=video_id)

@app.route('/video/<video_id>')
def video(video_id):
    video_path = os.path.join(DOWNLOAD_FOLDER, f'{video_id}.mp4')
    if not os.path.exists(video_path):
        return "Arquivo não encontrado", 404
    return send_file(video_path, mimetype='video/mp4')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/progresso')
def progresso():
    url = request.args.get('url')
    if not url:
        return "URL inválida", 400

    video_id = extrair_video_id(url)
    if not video_id:
        return "ID do vídeo não pôde ser extraído.", 400

    output_path = os.path.join(DOWNLOAD_FOLDER, f'{video_id}.mp4')

    # ✅ Se o vídeo já existe, redireciona direto para o player
    if os.path.exists(output_path):
        def generate():
            yield f"data: DONE::{video_id}\n\n"
        return Response(stream_with_context(generate()), mimetype='text/event-stream')

    # 🔁 Caso contrário, inicia o download e envia progresso via SSE
    def generate():
        yield f"data: Iniciando download...\n\n"
        process = subprocess.Popen([
            YTDLP_PATH,
            '--ffmpeg-location', FFMPEG_PATH,
            '--no-playlist',
            '--merge-output-format', 'mp4',
            '--write-info-json',
            '-f', 'bestvideo[height>=720]+bestaudio/best[height>=720]',
            '-o', output_path,
            url
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for line in process.stdout:
            if '[download]' in line and '%' in line:
                match = re.search(r'(\d{1,3}\.\d+)%', line)
                percent = match.group(1) if match else "..."
                yield f"data: {percent}%\n\n"

        process.wait()
        if process.returncode == 0:
            yield f"data: DONE::{video_id}\n\n"
        else:
            yield f"data: ERRO\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/aguardando')
def aguardando():
    return render_template('progresso.html')

@app.route('/galeria')
def galeria():
    videos = carregar_videos()
    return render_template('galeria.html', videos=videos, active='galeria')



@app.route('/deletar/<video_id>', methods=['POST'])
def deletar(video_id):
    video_path = os.path.join(DOWNLOAD_FOLDER, f'{video_id}.mp4')
    json_path = os.path.join(DOWNLOAD_FOLDER, f'{video_id}.info.json')
    deleted = False

    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            deleted = True

        if os.path.exists(json_path):
            os.remove(json_path)
            deleted = True
    except Exception as e:
        print(f"Erro ao deletar: {e}")

    videos = carregar_videos()
    return render_template('galeria.html', videos=videos, active='galeria')




if __name__ == '__main__':
    app.run(debug=True)

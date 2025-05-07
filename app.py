from flask import Flask, render_template, request, redirect, url_for, send_file
from convertors.tiktok_mp3 import convert_tiktok_to_mp3
from convertors.youtube_mp3 import convert_youtube_to_mp3
from convertors.youtube_mp4 import convert_youtube_to_mp4
from convertors.mp3_to_wav import convert_to_wav
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/youtube/mp3', methods=['GET','POST'])
def youtube_mp3():
    error = None
    if request.method == 'POST':
        url = request.form.get('url')
        try:
            path, name = convert_youtube_to_mp3(url, app.static_folder)
            return send_file(path,
                             mimetype='audio/mpeg',
                             as_attachment=True,
                             download_name=name)
        except Exception as e:
            error = str(e)
    return render_template('youtube_mp3.html', error=error)

@app.route('/youtube/mp4', methods=['GET','POST'])
def youtube_mp4():
    error = None
    if request.method == 'POST':
        url = request.form.get('url')
        try:
            path, name = convert_youtube_to_mp4(url, app.static_folder)
            return send_file(
                path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name=name
            )
        except Exception as e:
            error = str(e)
    return render_template('youtube_mp4.html', error=error, url=request.form.get('url', ''))

@app.route('/tiktok/mp3', methods=['GET', 'POST'])
def tiktok_mp3():
    if request.method == 'POST':
        url = request.form.get('url')
        try:
            mp3_path, filename = convert_tiktok_to_mp3(url)
            # Explicit MIME type ensures proper download
            return send_file(
                mp3_path,
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            return render_template('tiktok_mp3.html', error=str(e), url=url)
    return render_template('tiktok_mp3.html')

@app.route('/convert/to_wav', methods=['GET', 'POST'])
def convert_to_wav_route():
    error = None
    if request.method == 'POST':
        if 'audio_file' not in request.files:
            error = "No file part"
            return render_template('convert_to_wav.html', error=error)
            
        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            error = "No selected file"
            return render_template('convert_to_wav.html', error=error)
            
        if audio_file and audio_file.filename.lower().endswith(('.mp3', '.mp4', '.m4a')):
            try:
                # Save the uploaded file temporarily
                uploads_dir = os.path.join(app.static_folder, 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                temp_path = os.path.join(uploads_dir, audio_file.filename)
                audio_file.save(temp_path)
                
                # Convert the file to WAV
                wav_path, filename = convert_to_wav(temp_path, app.static_folder)
                
                # Clean up the temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                # Send the converted file
                return send_file(
                    wav_path,
                    mimetype='audio/wav',
                    as_attachment=True,
                    download_name=filename
                )
            except Exception as e:
                error = str(e)
        else:
            error = "Unsupported file format. Please upload an MP3 or MP4 audio file."
    
    return render_template('convert_to_wav.html', error=error)

if __name__ == '__main__':
    app.run(debug=True)
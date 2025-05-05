from flask import Flask, render_template, request, redirect, url_for, send_file
from convertors.tiktok_mp3 import convert_tiktok_to_mp3
from convertors.youtube_mp3 import convert_youtube_to_mp3
from convertors.youtube_mp4 import convert_youtube_to_mp4

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

if __name__ == '__main__':
    app.run(debug=True)
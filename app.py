from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, after_this_request
from convertors.tiktok_mp3 import convert_tiktok_to_mp3
from convertors.youtube_mp3 import convert_youtube_to_mp3
from convertors.youtube_mp4 import convert_youtube_to_mp4
from convertors.mp3_to_wav import convert_to_wav
from convertors.webp_to_png import convert_webp_to_png
import os
import re
import logging
import shutil
import time
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB max upload
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Don't cache files

@app.route('/')
def home():
    return render_template('home.html')

def sanitize_filename(filename):
    """Create a safe filename without any special characters"""
    # Extract base name and extension
    base_name, ext = os.path.splitext(filename)
    # Replace all non-alphanumeric chars
    safe_name = re.sub(r'[^\w\s-]', '', base_name)
    # Replace any whitespace with underscores
    safe_name = re.sub(r'\s+', '_', safe_name)
    # Return sanitized name with original extension
    return f"{safe_name}{ext}"

@app.route('/youtube/mp3', methods=['GET','POST'])
def youtube_mp3():
    error = None
    success = None
    download_id = None
    
    if request.method == 'POST':
        url = request.form.get('url')
        try:
            logger.debug(f"Starting YouTube to MP3 conversion for URL: {url}")
            
            # Create a timestamp-based ID for this conversion
            timestamp = int(time.time())
            conversion_id = f"{timestamp}"

            # Convert the YouTube video to MP3
            path, name = convert_youtube_to_mp3(url, app.static_folder)
            logger.debug(f"Conversion completed - Path: {path}, Name: {name}")
            
            # Additional safety check - if path doesn't exist, raise error
            if not os.path.exists(path):
                raise FileNotFoundError(f"The converted file does not exist at {path}")
                
            # Create an extremely safe download name
            safe_name = "youtube_audio.mp3"
            if name:
                safe_name = secure_filename(name)
                if not safe_name or safe_name == '.mp3':
                    safe_name = "youtube_audio.mp3"
            
            # Create a unique filename in downloads directory
            unique_filename = f"youtube_{conversion_id}.mp3"
            
            # Copy to a persistent location with a unique name
            downloads_dir = os.path.join(app.static_folder, 'downloads')
            os.makedirs(downloads_dir, exist_ok=True)
            
            dest_path = os.path.join(downloads_dir, unique_filename)
            shutil.copy2(path, dest_path)
            
            logger.debug(f"Copied file to {dest_path}")
            
            # Set success message and conversion ID for the template
            success = f"Successfully converted! File name: {safe_name}"
            download_id = conversion_id
            
        except Exception as e:
            logger.exception("Error in YouTube to MP3 conversion")
            error = str(e)
    
    return render_template('youtube_mp3.html', 
                           error=error, 
                           success=success,
                           download_id=download_id,
                           url=request.form.get('url', ''))

@app.route('/youtube/mp3/download/<download_id>')
def download_youtube_mp3(download_id):
    """Direct download endpoint for YouTube MP3 files"""
    try:
        # Construct the expected filename
        filename = f"youtube_{download_id}.mp3"

        # Path to the file
        downloads_dir = os.path.join(app.static_folder, 'downloads')
        file_path = os.path.join(downloads_dir, filename)

        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return "File not found. It may have expired.", 404

        # Set a generic but descriptive filename
        download_name = f"youtube_audio_{download_id}.mp3"

        # Schedule cleanup after a delay
        @after_this_request
        def cleanup_file(response):
            def delayed_cleanup():
                time.sleep(300)  # 5 minutes
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.debug(f"Removed MP3 file after delay: {file_path}")
                except Exception as e:
                    logger.error(f"Error removing file: {e}")

            import threading
            cleanup_thread = threading.Thread(target=delayed_cleanup)
            cleanup_thread.daemon = True
            cleanup_thread.start()
            return response

        # Use direct file send with attachment
        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='audio/mpeg'
        )

    except Exception as e:
        logger.exception(f"Error in download_youtube_mp3: {e}")
        return "An error occurred during download", 500

@app.route('/youtube/mp4', methods=['GET','POST'])
def youtube_mp4():
    error = None
    if request.method == 'POST':
        url = request.form.get('url')
        try:
            logger.debug(f"Starting YouTube to MP4 conversion for URL: {url}")
            
            # Convert the YouTube video to MP4
            path, name = convert_youtube_to_mp4(url, app.static_folder)
            logger.debug(f"Conversion completed - Path: {path}, Name: {name}")
            
            # Additional safety check - if path doesn't exist, raise error
            if not os.path.exists(path):
                raise FileNotFoundError(f"The converted file does not exist at {path}")
                
            # Extra sanitization of file before sending
            safe_name = "youtube_video.mp4"
            if name:
                # Create an extra-safe name with just alphanumeric chars
                safe_name = re.sub(r'[^\w]+', '', os.path.splitext(name)[0])
                safe_name = f"{safe_name}.mp4"
                
            logger.debug(f"Sending file with safe name: {safe_name}")
            
            return send_file(
                path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name=safe_name
            )
        except Exception as e:
            logger.exception("Error in YouTube to MP4 conversion")
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

@app.route('/convert/webp_to_png', methods=['GET', 'POST'])
def convert_webp_to_png_route():
    error = None
    if request.method == 'POST':
        if 'image_file' not in request.files:
            error = "No file part"
            return render_template('convert_webp_to_png.html', error=error)
            
        image_file = request.files['image_file']
        if image_file.filename == '':
            error = "No selected file"
            return render_template('convert_webp_to_png.html', error=error)
            
        if image_file and image_file.filename.lower().endswith('.webp'):
            try:
                # Save the uploaded file temporarily
                uploads_dir = os.path.join(app.static_folder, 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)
                temp_path = os.path.join(uploads_dir, image_file.filename)
                image_file.save(temp_path)
                
                # Convert the file to PNG
                png_path, filename = convert_webp_to_png(temp_path, app.static_folder)
                
                # Clean up the temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                # Send the converted file
                return send_file(
                    png_path,
                    mimetype='image/png',
                    as_attachment=True,
                    download_name=filename
                )
            except Exception as e:
                error = str(e)
        else:
            error = "Unsupported file format. Please upload a WebP image file."
    
    return render_template('convert_webp_to_png.html', error=error)

if __name__ == '__main__':
    app.run(debug=True)
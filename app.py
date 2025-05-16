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

import threading

# Track conversion status using a dictionary
conversion_status = {}

def background_youtube_conversion(url, video_id):
    """Process YouTube conversion in a background thread"""
    status_key = f"yt_{video_id}"
    
    try:
        # Set initial status
        conversion_status[status_key] = {
            'status': 'processing',
            'message': 'Download in progress...',
            'progress': 0,
            'filename': None,
            'url': url
        }
        
        # Convert the YouTube video to MP3
        path, name = convert_youtube_to_mp3(url, app.static_folder)
        logger.debug(f"Conversion completed - Path: {path}, Name: {name}")
        
        # Create a safe download name
        safe_name = secure_filename(name) if name else f"youtube_audio_{video_id}.mp3"
        if not safe_name or safe_name == '.mp3':
            safe_name = f"youtube_audio_{video_id}.mp3"
        
        # Verify file exists in downloads directory with expected naming pattern
        expected_path = os.path.join(app.static_folder, 'downloads', f"youtube_{video_id}.mp3")
        if not os.path.exists(expected_path) and os.path.exists(path):
            logger.info(f"Copying file to expected location: {expected_path}")
            shutil.copy2(path, expected_path)
        
        # Update status to complete
        conversion_status[status_key] = {
            'status': 'complete',
            'message': 'Conversion complete! Your file is ready for download.',
            'progress': 100,
            'filename': safe_name,
            'url': url
        }
    except Exception as e:
        logger.exception(f"Error in background YouTube conversion: {e}")
        # Update status to error
        conversion_status[status_key] = {
            'status': 'error',
            'message': f"Error: {str(e)}",
            'progress': 0,
            'url': url
        }

@app.route('/youtube/mp3', methods=['GET', 'POST'])
def youtube_mp3():
    """Handle YouTube to MP3 conversion requests with status updates"""
    error = None
    status_message = None
    video_id = None
    processing = False
    progress = 0
    
    # First, check if we're requesting status for an existing download
    if request.args.get('vid'):
        video_id = request.args.get('vid')
        status_key = f"yt_{video_id}"
        
        # Check if file exists
        expected_path = os.path.join(app.static_folder, 'downloads', f"youtube_{video_id}.mp3")
        
        if os.path.exists(expected_path):
            # File already exists, ready for download
            status_message = "Your file is ready for download!"
        elif status_key in conversion_status:
            current_status = conversion_status[status_key]
            if current_status['status'] == 'complete':
                status_message = "Your file is ready for download!"
            elif current_status['status'] == 'error':
                error = current_status['message']
            else:
                # Still processing
                status_message = current_status.get('message', 'Your file is being processed...')
                progress = current_status.get('progress', 0)
                processing = True
        else:
            error = "No download found with that ID. It may have expired."
    
    # Handle new conversion requests
    elif request.method == 'POST':
        url = request.form.get('url')
        try:
            # Extract video ID from URL
            if "v=" in url:
                video_id = url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]
            else:
                video_id = f"video_{int(time.time())}"
            
            logger.debug(f"Processing YouTube URL: {url}, Video ID: {video_id}")
            
            # Check if we already have the file
            expected_path = os.path.join(app.static_folder, 'downloads', f"youtube_{video_id}.mp3")
            status_key = f"yt_{video_id}"
            
            if os.path.exists(expected_path):
                # File already exists, show status page with download link
                status_message = "Your file is ready for download!"
            elif status_key in conversion_status:
                # Conversion already in progress, get status
                current_status = conversion_status[status_key]
                
                if current_status['status'] == 'complete':
                    status_message = "Your file is ready for download!"
                elif current_status['status'] == 'error':
                    error = current_status['message']
                else:
                    # Still processing
                    status_message = current_status.get('message', 'Your file is being processed...')
                    progress = current_status.get('progress', 0)
                    processing = True
            else:
                # Start a new background conversion
                conversion_thread = threading.Thread(
                    target=background_youtube_conversion,
                    args=(url, video_id)
                )
                conversion_thread.daemon = True
                conversion_thread.start()
                
                # Tell the user it's processing
                status_message = "Your download has started. Large files may take several minutes to process."
                processing = True
            
            # Always redirect to the status page after POST
            return redirect(url_for('youtube_mp3', vid=video_id))
                
        except Exception as e:
            logger.exception("Error initiating YouTube to MP3 conversion")
            error = str(e)
    
    # Ensure jsonify is imported for the API response
    from flask import jsonify
    
    # Ensure progress has a default value
    if not 'progress' in locals() or progress is None:
        progress = 0
        
    # If processing but progress is still 0, set to minimum value for better UX
    if processing and progress == 0:
        progress = 5
        
    return render_template('youtube_mp3.html', 
                          error=error, 
                          status_message=status_message,
                          video_id=video_id,
                          processing=processing,
                          progress=progress,
                          url=request.form.get('url', ''))
    
    
    @app.route('/api/youtube/status/<video_id>')
    def youtube_status_api(video_id):
        """API endpoint to get the current status of a YouTube conversion"""
        status_key = f"yt_{video_id}"
        response = {
            "status": "unknown",
            "progress": 0,
            "message": "No information available",
            "complete": False,
            "file_ready": False,
            "download_url": None
        }
        
        # Check if file exists
        expected_path = os.path.join(app.static_folder, 'downloads', f"youtube_{video_id}.mp3")
        
        if os.path.exists(expected_path):
            # File already exists, ready for download
            response.update({
                "status": "complete",
                "progress": 100,
                "message": "Your file is ready for download!",
                "complete": True,
                "file_ready": True,
                "download_url": f"/static/downloads/youtube_{video_id}.mp3"
            })
        elif status_key in conversion_status:
            # Get status from conversion status dictionary
            current_status = conversion_status[status_key]
            
            response.update({
                "status": current_status.get('status', 'processing'),
                "progress": current_status.get('progress', 0),
                "message": current_status.get('message', 'Processing...'),
                "complete": current_status.get('status') == 'complete',
                "file_ready": current_status.get('status') == 'complete'
            })
            # Print to console for immediate visibility
            print(f"Progress update for {video_id}: {percentage}% - {message}")
            
            # If complete, add download URL
            if current_status.get('status') == 'complete':
                response["download_url"] = f"/static/downloads/youtube_{video_id}.mp3"
        
        return jsonify(response)

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
        
        # Log file info for debugging
        file_size = os.path.getsize(file_path)
        logger.debug(f"Serving file: {file_path}, Size: {file_size} bytes")
        
        # Get status key
        status_key = f"yt_{download_id}"
        display_filename = f"youtube_audio_{download_id}.mp3"
        
        # Try to get a better filename from conversion status
        if status_key in conversion_status and conversion_status[status_key].get('filename'):
            display_filename = conversion_status[status_key]['filename']
        
        # Schedule cleanup after a delay
        def delayed_cleanup():
            time.sleep(1800)  # 30 minutes
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Removed MP3 file after delay: {file_path}")
                # Also remove from status tracking
                if status_key in conversion_status:
                    del conversion_status[status_key]
            except Exception as e:
                logger.error(f"Error removing file: {e}")
        
        cleanup_thread = threading.Thread(target=delayed_cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        # Two options:
        # 1. Send the file directly (more reliable for some browsers)
        return send_file(
            file_path,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=display_filename
        )
        
        # 2. Redirect to static file (fallback - commented out)
        # static_url = f"/static/downloads/{filename}"
        # return redirect(static_url)
    
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
from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, \
    after_this_request, flash
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

@app.route('/api/youtube/status/<video_id>')
def youtube_mp3_status_api(video_id):
    """API endpoint to get the current status of a YouTube MP3 conversion"""
    from flask import jsonify
    
    status_key = f"yt_{video_id}"
    response = {
        "status": "unknown",
        "progress": 0,
        "message": "No information available",
        "complete": False,
        "file_ready": False,
        "download_url": None,
        "error": False
    }
    
    # Check if file exists
    expected_path = os.path.join(app.static_folder, 'downloads', f"youtube_{video_id}.mp3")
    
    if os.path.exists(expected_path):
        # File already exists, ready for download
        file_size = os.path.getsize(expected_path)
        response.update({
            "status": "complete",
            "progress": 100,
            "message": "Your file is ready for download!",
            "complete": True,
            "file_ready": True,
            "download_url": f"/static/downloads/youtube_{video_id}.mp3",
            "file_size": file_size
        })
        logger.debug(f"API status check: MP3 file exists for {video_id}, size: {file_size} bytes")
    elif status_key in conversion_status:
        # Get status from conversion status dictionary
        current_status = conversion_status[status_key]
        
        # Check if there was an error
        if current_status.get('error', False):
            response.update({
                "status": "error",
                "message": current_status.get('message', 'An error occurred during conversion'),
                "error": True,
                "complete": True
            })
            logger.debug(f"API status check: Error state for MP3 {video_id}: {response['message']}")
        else:
            response.update({
                "status": "processing" if not current_status.get('complete', False) else "complete",
                "progress": current_status.get('progress', 0),
                "message": current_status.get('message', 'Processing...'),
                "complete": current_status.get('complete', False),
                "file_ready": current_status.get('complete', False) and os.path.exists(expected_path)
            })
            
            # If complete, add download URL but verify file exists
            if current_status.get('complete', False):
                if os.path.exists(expected_path):
                    response["download_url"] = f"/static/downloads/youtube_{video_id}.mp3"
                    response["file_ready"] = True
                else:
                    # This is a problem - marked complete but file doesn't exist
                    response["message"] = "Error: File not found. Please try again."
                    response["error"] = True
                    logger.warning(f"API status check: MP3 file missing for completed conversion {video_id}")
            
            logger.debug(f"API status check: Status for MP3 {video_id}: {response['status']}, progress: {response['progress']}%")
    else:
        logger.warning(f"API status check: No status found for MP3 {video_id}")
    
    return jsonify(response)

@app.route('/youtube/mp3', methods=['GET', 'POST'])
def youtube_mp3():
    """YouTube to MP3 converter page and API endpoint"""
    error = None
    status_message = None
    progress = 0
    processing = False
    video_id = request.args.get('vid')
    
    if request.method == 'POST':
        # Handle form submission - start new conversion
        url = request.form.get('url')
        if not url:
            error = "Please enter a valid YouTube URL"
        else:
            # Extract video ID from URL
            if "v=" in url:
                video_id = url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]
            else:
                error = "Could not extract video ID from URL. Please use a standard YouTube URL."
                
            if video_id and not error:
                logger.info(f"Starting YouTube to MP3 conversion for video ID: {video_id}")
                
                # Start a new conversion task in a background thread
                thread = threading.Thread(
                    target=background_youtube_conversion,
                    args=(url, video_id)
                )
                thread.daemon = True
                thread.start()
                logger.debug(f"Background conversion thread started for video ID: {video_id}")
                
                # Redirect to status page
                return redirect(url_for('youtube_mp3', vid=video_id))
    
    # Handle GET requests - status check or initial page load
    if video_id:
        # This is a status check
        status_key = f"yt_{video_id}"
        
        # Check if this is a completed download
        filename = f"youtube_{video_id}.mp3"
        file_path = os.path.join(app.static_folder, 'downloads', filename)
        
        if os.path.exists(file_path):
            # File exists - show download button
            status_message = "Your MP3 is ready for download!"
            processing = False
        elif status_key in conversion_status:
            # Conversion in progress
            current_status = conversion_status[status_key]
            progress = current_status.get('progress', 0)
            status_message = current_status.get('message', 'Processing...')
            processing = not current_status.get('complete', False)
        else:
            # No status found - offer to start new conversion
            error = "No download found with that ID. It may have expired."
            
    # Render template with appropriate context
    return render_template(
        'youtube_mp3.html', 
        error=error,
        status_message=status_message,
        progress=progress,
        processing=processing,
        video_id=video_id,
        url=request.form.get('url', '')
    )

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

def process_youtube_mp3(url, video_id, static_folder):
    """Background thread function to process YouTube MP3 conversions"""
    status_key = f"yt_{video_id}"
    try:
        # Make sure downloads directory exists
        downloads_dir = os.path.join(static_folder, 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        
        # First check if the file already exists (avoid redownloading)
        expected_file_path = os.path.join(downloads_dir, f"youtube_{video_id}.mp3")
        if os.path.exists(expected_file_path):
            logger.info(f"File already exists for video {video_id}, skipping download")
            
            # Update status to show completion
            conversion_status[status_key] = {
                'progress': 100,
                'message': 'Your MP3 is ready for download!',
                'complete': True,
                'filename': f"youtube_audio_{video_id}.mp3",
                'download_url': f"/youtube/mp3/download/{video_id}"
            }
            return
            
        # Update status to show we're starting
        conversion_status[status_key] = {
            'progress': 0,
            'message': 'Starting download...',
            'complete': False
        }
        
        # Define a progress callback function
        def progress_callback(percent, message, is_complete=False):
            # Update the global status dictionary
            conversion_status[status_key] = {
                'progress': percent,
                'message': message,
                'complete': is_complete
            }
            logger.debug(f"Progress update for {video_id}: {percent}% - {message} (Complete: {is_complete})")
            
        # Perform the actual conversion
        logger.debug(f"Starting YouTube to MP3 conversion for URL: {url}")
        file_path, filename = convert_youtube_to_mp3(url, static_folder, progress_callback)
        
        # Verify the file was created
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Expected MP3 file not found at {file_path}")
            
        # Double-check that the file is in the expected location
        if not os.path.exists(expected_file_path):
            logger.warning(f"File not in expected location. Copying from {file_path} to {expected_file_path}")
            shutil.copy2(file_path, expected_file_path)
        
        # Update status to show completion
        conversion_status[status_key] = {
            'progress': 100,
            'message': 'Your MP3 is ready for download!',
            'complete': True,
            'filename': filename or f"youtube_audio_{video_id}.mp3",
            'download_url': f"/youtube/mp3/download/{video_id}"
        }
        logger.info(f"YouTube to MP3 conversion completed: {filename}")
        
    except Exception as e:
        # Update status to show error
        conversion_status[status_key] = {
            'progress': 0,
            'message': f"Error: {str(e)}",
            'complete': True,
            'error': True
        }
        logger.exception(f"Error in YouTube to MP3 conversion: {e}")

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

@app.route('/external-seo-form', methods=['GET'])
def external_seo_form():
    return render_template('external_seo_form.html')

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

@app.route('/api/youtube/status/<video_id>')
def youtube_status_api(video_id):
    """API endpoint to get the current status of a YouTube conversion"""
    from flask import jsonify
    
    status_key = f"yt_{video_id}"
    response = {
        "status": "unknown",
        "progress": 0,
        "message": "No information available",
        "complete": False,
        "file_ready": False,
        "download_url": None,
        "error": False
    }
    
    # Check if file exists
    expected_path = os.path.join(app.static_folder, 'downloads', f"youtube_{video_id}.mp3")
    
    if os.path.exists(expected_path):
        # File already exists, ready for download
        file_size = os.path.getsize(expected_path)
        response.update({
            "status": "complete",
            "progress": 100,
            "message": "Your file is ready for download!",
            "complete": True,
            "file_ready": True,
            "download_url": f"/static/downloads/youtube_{video_id}.mp3",
            "file_size": file_size
        })
        logger.debug(f"API status check: File exists for {video_id}, size: {file_size} bytes")
    elif status_key in conversion_status:
        # Get status from conversion status dictionary
        current_status = conversion_status[status_key]
        
        # Check if there was an error
        if current_status.get('error', False):
            response.update({
                "status": "error",
                "message": current_status.get('message', 'An error occurred during conversion'),
                "error": True,
                "complete": True
            })
            logger.debug(f"API status check: Error state for {video_id}: {response['message']}")
        else:
            response.update({
                "status": "processing" if not current_status.get('complete', False) else "complete",
                "progress": current_status.get('progress', 0),
                "message": current_status.get('message', 'Processing...'),
                "complete": current_status.get('complete', False),
                "file_ready": current_status.get('complete', False) and os.path.exists(expected_path)
            })
            
            # If complete, add download URL but verify file exists
            if current_status.get('complete', False):
                if os.path.exists(expected_path):
                    response["download_url"] = f"/static/downloads/youtube_{video_id}.mp3"
                    response["file_ready"] = True
                else:
                    # This is a problem - marked complete but file doesn't exist
                    response["message"] = "Error: File not found. Please try again."
                    response["error"] = True
                    logger.warning(f"API status check: File missing for completed conversion {video_id}")
            
            logger.debug(f"API status check: Status for {video_id}: {response['status']}, progress: {response['progress']}%")
    else:
        logger.warning(f"API status check: No status found for {video_id}")
    
    return jsonify(response)
    
if __name__ == '__main__':
    app.run(debug=True)
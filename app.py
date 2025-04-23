from flask import Flask, request, jsonify, send_file
import requests
import os
import tempfile
from urllib.parse import unquote, urlparse
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_valid_youtube_url(url):
    """Validate YouTube URL"""
    try:
        parsed = urlparse(unquote(url))
        if not parsed.scheme in ('http', 'https'):
            return False
        return any(domain in parsed.netloc for domain in ('youtube.com', 'youtu.be'))
    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False

def download_video_file(download_url, file_path):
    """Download video from direct link"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        with requests.get(download_url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

@app.route('/yt', methods=['GET'])
def download_youtube():
    """YouTube download endpoint"""
    youtube_url = request.args.get('url')
    
    if not youtube_url:
        logger.warning("No URL provided")
        return jsonify({"error": "يجب تقديم رابط YouTube كمعامل url"}), 400
    
    youtube_url = unquote(youtube_url)
    
    if not is_valid_youtube_url(youtube_url):
        logger.warning(f"Invalid YouTube URL: {youtube_url}")
        return jsonify({"error": "رابط YouTube غير صالح"}), 400
    
    try:
        # Get download link from API
        api_url = "https://oo6o8y6la6.execute-api.eu-central-1.amazonaws.com/default/Upload-DownloadYoutubeLandingPage"
        payload = {
            "url": youtube_url,
            "app": "transkriptor",
            "is_only_download": True
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://transkriptor.com/"
        }
        
        logger.info(f"Requesting download link for: {youtube_url}")
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        download_url = data.get('download_url')
        
        if not download_url:
            logger.error("No download URL received from API")
            return jsonify({"error": "لا يتوفر رابط تحميل"}), 404
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_path = temp_file.name
        temp_file.close()
        
        # Download video
        logger.info(f"Downloading video from: {download_url}")
        if not download_video_file(download_url, temp_path):
            os.unlink(temp_path)
            return jsonify({"error": "فشل تحميل الفيديو"}), 500
        
        # Send file with cleanup
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name="video.mp4",
            mimetype='video/mp4'
        )
        
        # Cleanup temp file after sending
        @response.call_on_close
        def remove_temp_file():
            try:
                os.unlink(temp_path)
                logger.info("Temporary file cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning temp file: {e}")
                
        return response
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return jsonify({"error": f"خطأ في الاتصال: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": f"حدث خطأ غير متوقع: {str(e)}"}), 500

# Vercel handler
def handler(request):
    with app.app_context():
        from flask import Request
        environ = {
            'REQUEST_METHOD': request.method,
            'PATH_INFO': request.path,
            'QUERY_STRING': request.query_string.decode('utf-8'),
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'wsgi.input': None,
            'wsgi.url_scheme': 'https',
        }
        
        # Add headers
        for key, value in request.headers.items():
            environ[f'HTTP_{key.upper().replace("-", "_")}'] = value

        # Create Flask request
        with app.test_request_context(environ):
            try:
                response = app.full_dispatch_request()
                return {
                    'statusCode': response.status_code,
                    'headers': dict(response.headers),
                    'body': response.get_data(as_text=True) if not response.direct_passthrough else None,
                    'isBase64Encoded': False
                }
            except Exception as e:
                logger.error(f"Handler error: {e}")
                return {
                    'statusCode': 500,
                    'body': str(e)
                }

if __name__ == '__main__':
    app.run()

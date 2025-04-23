from flask import Flask, request, jsonify
import requests
import tempfile
import os
from urllib.parse import unquote, urlparse

app = Flask(__name__)

def is_valid_youtube_url(url):
    parsed = urlparse(unquote(url))
    return any(domain in parsed.netloc for domain in ('youtube.com', 'youtu.be'))

def get_download_link(youtube_url):
    api_url = "https://oo6o8y6la6.execute-api.eu-central-1.amazonaws.com/default/Upload-DownloadYoutubeLandingPage"
    payload = {"url": youtube_url, "app": "transkriptor", "is_only_download": True}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://transkriptor.com/"
    }
    response = requests.post(api_url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json().get('download_url')

@app.route('/yt', methods=['GET'])
def download_youtube():
    youtube_url = request.args.get('url')
    if not youtube_url:
        return jsonify({"error": "YouTube URL is required"}), 400
    
    if not is_valid_youtube_url(youtube_url):
        return jsonify({"error": "Invalid YouTube URL"}), 400

    try:
        download_url = get_download_link(unquote(youtube_url))
        if not download_url:
            return jsonify({"error": "No download link available"}), 404
        
        # Return the download URL instead of the file
        return jsonify({
            "status": "success",
            "download_url": download_url,
            "original_url": youtube_url
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Connection error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

# Vercel serverless handler
def handler(event, context):
    from flask import Request
    from io import BytesIO
    
    # Convert Vercel event to Flask request
    body = event.get('body', '')
    headers = event.get('headers', {})
    query = event.get('queryStringParameters', {})
    method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    
    environ = {
        'REQUEST_METHOD': method,
        'PATH_INFO': path,
        'QUERY_STRING': '&'.join([f"{k}={v}" for k,v in query.items()]),
        'wsgi.input': BytesIO(body.encode() if body else b''),
        'wsgi.url_scheme': headers.get('x-forwarded-proto', 'https'),
        'SERVER_NAME': headers.get('host', 'localhost'),
        'SERVER_PORT': headers.get('x-forwarded-port', '443'),
    }
    
    # Add headers to environ
    for key, value in headers.items():
        environ[f'HTTP_{key.upper().replace("-", "_")}'] = value

    # Create Flask request context
    with app.request_context(environ):
        try:
            response = app.full_dispatch_request()
            return {
                'statusCode': response.status_code,
                'headers': dict(response.headers),
                'body': response.get_data(as_text=True)
            }
        except Exception as e:
            return {
                'statusCode': 500,
                'body': str(e)
            }

if __name__ == '__main__':
    app.run(debug=True)

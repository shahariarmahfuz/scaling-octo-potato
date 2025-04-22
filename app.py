import subprocess
import os
import sys
import time
import logging
import threading
import http.server
import socketserver
import shutil

# --- Configuration ---
# Default YouTube URL (replace with actual URL when running)
# THIS IS AN INVALID EXAMPLE URL PROVIDED BY USER. USE A REAL ONE.
DEFAULT_YOUTUBE_URL = "https://www.youtube.com/live/emNjUeezimE?si=gFsJqQEargWpR0Z0"
HLS_OUTPUT_DIR = "/app/hls_output"  # Must match Dockerfile RUN mkdir
HTTP_PORT = 8000

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global variable to hold FFmpeg process ---
ffmpeg_process = None

# --- Functions ---

def get_stream_url(youtube_url):
    """
    Uses yt-dlp to get the best available direct stream URL.
    """
    logging.info(f"Attempting to get stream URL for: {youtube_url}")
    try:
        # '-f best' tries to get the best quality muxed stream
        # '-g' gets the direct URL
        command = ['yt-dlp', '-f', 'best', '-g', youtube_url]
        process = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        stream_url = process.stdout.strip()
        if not stream_url.startswith(('http://', 'https://')):
            logging.error(f"yt-dlp did not return a valid URL: {stream_url}")
            logging.error(f"yt-dlp stderr: {process.stderr}")
            return None
        logging.info(f"Successfully obtained stream URL.")
        return stream_url
    except subprocess.CalledProcessError as e:
        logging.error(f"yt-dlp failed: {e}")
        logging.error(f"Stderr: {e.stderr}")
        return None
    except subprocess.TimeoutExpired:
        logging.error("yt-dlp command timed out.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while running yt-dlp: {e}")
        return None

def start_ffmpeg(stream_url):
    """
    Starts the FFmpeg process to convert the input stream to HLS.
    """
    global ffmpeg_process
    # Clean HLS output directory before starting
    if os.path.exists(HLS_OUTPUT_DIR):
        shutil.rmtree(HLS_OUTPUT_DIR)
    os.makedirs(HLS_OUTPUT_DIR, exist_ok=True)

    # FFmpeg command
    # -i {stream_url}: Input stream URL
    # -c:v copy -c:a copy: Copy video and audio codecs without re-encoding (faster, less CPU)
    # -f hls: Output format HLS
    # -hls_time 4: Segment duration in seconds
    # -hls_list_size 5: Number of segments in the playlist
    # -hls_flags delete_segments: Delete old segments
    # -hls_segment_filename: Pattern for segment filenames
    # {HLS_OUTPUT_DIR}/live.m3u8: Output playlist file
    ffmpeg_command = [
        'ffmpeg',
        '-i', stream_url,
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-f', 'hls',
        '-hls_time', '4',
        '-hls_list_size', '5',
        '-hls_flags', 'delete_segments+omit_endlist', # omit_endlist makes it look like a live stream
        '-hls_segment_filename', os.path.join(HLS_OUTPUT_DIR, 'segment%03d.ts'),
        os.path.join(HLS_OUTPUT_DIR, 'live.m3u8')
    ]

    logging.info("Starting FFmpeg process...")
    logging.info(f"Command: {' '.join(ffmpeg_command)}") # Log the command for debugging

    # Start FFmpeg as a subprocess
    # Use Popen for non-blocking execution
    try:
        ffmpeg_process = subprocess.Popen(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True # Decode stdout/stderr as text
        )
        logging.info(f"FFmpeg process started with PID: {ffmpeg_process.pid}")

        # Optional: Monitor FFmpeg output in a separate thread
        def monitor_ffmpeg(proc):
            # Monitor stdout
            # for line in proc.stdout:
            #     logging.debug(f"FFmpeg stdout: {line.strip()}")
            # Monitor stderr
            for line in proc.stderr:
                logging.info(f"FFmpeg stderr: {line.strip()}") # FFmpeg often logs progress to stderr
            proc.wait()
            logging.info(f"FFmpeg process exited with code: {proc.returncode}")

        monitor_thread = threading.Thread(target=monitor_ffmpeg, args=(ffmpeg_process,))
        monitor_thread.daemon = True # Allow program to exit even if this thread is running
        monitor_thread.start()

    except Exception as e:
        logging.error(f"Failed to start FFmpeg: {e}")
        ffmpeg_process = None

def start_http_server():
    """
    Starts a simple HTTP server to serve the HLS files.
    """
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=HLS_OUTPUT_DIR, **kwargs)

        # Optional: Add CORS headers if needed for browser players
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            super().end_headers()

    # Run the server in a separate thread
    def server_thread():
        with socketserver.TCPServer(("", HTTP_PORT), Handler) as httpd:
            logging.info(f"Serving HLS files on port {HTTP_PORT}")
            logging.info(f"Access the stream at: http://<your-ip>:{HTTP_PORT}/live.m3u8")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                logging.info("HTTP server shutting down.")
                httpd.shutdown()

    thread = threading.Thread(target=server_thread)
    thread.daemon = True # Allows main thread to exit even if server is running
    thread.start()
    logging.info("HTTP server thread started.")

# --- Main Execution ---
if __name__ == "__main__":
    # --- DISCLAIMER ---
    logging.warning("********************************************************************")
    logging.warning("EDUCATIONAL PURPOSE ONLY. DO NOT USE WITH COPYRIGHTED MATERIAL.")
    logging.warning("Running this script with actual YouTube streams may violate YouTube's")
    logging.warning("Terms of Service and copyright laws. Use responsibly and ethically.")
    logging.warning("********************************************************************")

    # Get YouTube URL from command-line argument or use default
    youtube_url_to_use = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_YOUTUBE_URL

    if youtube_url_to_use == DEFAULT_YOUTUBE_URL:
        logging.warning(f"Using default invalid URL: {DEFAULT_YOUTUBE_URL}")
        logging.warning("Please provide a valid YouTube video/live URL as a command-line argument.")
        # sys.exit(1) # Exit if you want to force providing a URL

    # 1. Get the direct stream URL
    stream_url = get_stream_url(youtube_url_to_use)

    if not stream_url:
        logging.error("Could not obtain a valid stream URL. Exiting.")
        sys.exit(1)

    # 2. Start the HTTP server in a background thread
    start_http_server()
    # Give the server a moment to start up
    time.sleep(2)

    # 3. Start the FFmpeg process
    start_ffmpeg(stream_url)

    # Keep the main thread alive while FFmpeg runs (or until interrupted)
    if ffmpeg_process:
        try:
            while ffmpeg_process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Ctrl+C received. Shutting down FFmpeg...")
            if ffmpeg_process:
                ffmpeg_process.terminate() # Send SIGTERM
                try:
                    ffmpeg_process.wait(timeout=10) # Wait for graceful shutdown
                except subprocess.TimeoutExpired:
                    logging.warning("FFmpeg did not terminate gracefully. Sending SIGKILL.")
                    ffmpeg_process.kill() # Force kill
            logging.info("FFmpeg shutdown complete.")
        finally:
            if ffmpeg_process and ffmpeg_process.poll() is None:
                 ffmpeg_process.terminate() # Ensure termination on other exits
    else:
        logging.error("FFmpeg process failed to start.")

    logging.info("Application finished.")

import os
import json
import subprocess
import time

# ✅ Configuration
PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")
OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")
RETRY_DELAY = 60

if not RTMP_URL:
    print("❌ ERROR: RTMP_URL environment variable is NOT set!")
    exit(1)

if not os.path.exists(PLAY_FILE):
    print(f"❌ ERROR: {PLAY_FILE} not found!")
    exit(1)

if not os.path.exists(OVERLAY):
    print(f"❌ ERROR: Overlay image '{OVERLAY}' not found!")
    exit(1)

if not os.path.exists(FONT_PATH):
    print(f"❌ ERROR: Font file '{FONT_PATH}' not found!")
    exit(1)

def load_movies():
    try:
        with open(PLAY_FILE, "r") as f:
            movies = json.load(f)
        if not movies:
            print("❌ ERROR: No movies in play.json!")
            return []
        return movies
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ ERROR loading play.json - {str(e)}")
        return []

def escape_drawtext(text):
    return text.replace('\\', '\\\\\\\\').replace(':', '\\:').replace("'", "\\'")

def stream_movie(movie):
    title = movie.get("title", "Unknown Title")
    url = movie.get("url")
    if not url:
        print(f"❌ Missing URL for movie '{title}'")
        return

    overlay_text = escape_drawtext(title)

    command = [
        "ffmpeg",
        "-rw_timeout", "5000000",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-probesize", "1M",
        "-analyzeduration", "2M",
        "-i", url,
        "-i", OVERLAY,
        "-filter_complex",
        f"[0:v]scale=w=854:h=480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2[vscaled];" +
        f"[vscaled][1:v]overlay=0:0[voverlay];" +
        f"[voverlay]drawtext=fontfile='{FONT_PATH}':text='{overlay_text}':fontcolor=white:fontsize=18:x=20:y=20",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "24",
        "-tune", "zerolatency",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-vsync", "2",
        "-fps_mode", "auto",
        "-c:a", "aac",
        "-b:a", "96k",
        "-ar", "44100",
        "-movflags", "+faststart",
        "-f", "flv",
        RTMP_URL
    ]

    print(f"🎬 Streaming: {title}")
    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        for line in process.stderr:
            print(line, end="")
        process.wait()
    except Exception as e:
        print(f"❌ FFmpeg failed: {e}")

def main():
    movies = load_movies()
    if not movies:
        print(f"🔄 Retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)
        return main()

    index = 0
    while True:
        stream_movie(movies[index])
        index = (index + 1) % len(movies)
        print("🔄 Movie ended. Next one...")

if __name__ == "__main__":
    main()

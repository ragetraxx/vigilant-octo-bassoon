import os
import json
import subprocess
import time

# ✅ Configuration
PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")
OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")  # Full path to your font file
RETRY_DELAY = 60

# ✅ Check if RTMP_URL is set
if not RTMP_URL:
    print("❌ ERROR: RTMP_URL environment variable is NOT set! Check configuration.")
    exit(1)

# ✅ Ensure required files exist
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
    """Load all movies from play.json."""
    try:
        with open(PLAY_FILE, "r") as f:
            movies = json.load(f)
        if not movies:
            print("❌ ERROR: No movies found in play.json!")
            return []
        return movies
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ ERROR: Failed to load {PLAY_FILE} - {str(e)}")
        return []

def escape_drawtext(text):
    """Escape special characters for FFmpeg drawtext."""
    return text.replace('\\', '\\\\\\\\').replace(':', '\\:').replace("'", "\\'")

def stream_movie(movie):
    """Stream a single movie using FFmpeg."""
    title = movie.get("title", "Unknown Title")
    url = movie.get("url")

    if not url:
        print(f"❌ ERROR: Missing URL for movie '{title}'")
        return

    overlay_text = escape_drawtext(title)

    command = [
        "ffmpeg",
        "-rw_timeout", "5000000",               # 5s timeout on remote reads
        "-reconnect", "1",                      # Auto reconnect input
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-probesize", "512k",
        "-analyzeduration", "1M",
        "-i", url,
        "-i", OVERLAY,
        "-filter_complex",
        f"[0:v][1:v]scale2ref[v0][v1];[v0][v1]overlay=0:0,drawtext=fontfile='{FONT_PATH}':text='{overlay_text}':fontcolor=white:fontsize=20:x=35:y=35",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "50",
        "-keyint_min", "50",
        "-sc_threshold", "0",
        "-b:v", "2500k",
        "-maxrate", "2500k",
        "-bufsize", "500k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-f", "flv",
        RTMP_URL
    ]

    print(f"🎬 Now Streaming: {title}")

    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        for line in process.stderr:
            print(line, end="")  # Show FFmpeg output
        process.wait()
    except Exception as e:
        print(f"❌ ERROR: FFmpeg failed for '{title}' - {str(e)}")

def main():
    """Continuously play movies from play.json in a loop."""
    movies = load_movies()

    if not movies:
        print(f"🔄 No movies found! Retrying in {RETRY_DELAY} seconds...")
        time.sleep(RETRY_DELAY)
        return main()

    index = 0

    while True:
        movie = movies[index]
        stream_movie(movie)
        index = (index + 1) % len(movies)
        print("🔄 Movie ended. Playing next movie...")

if __name__ == "__main__":
    main()

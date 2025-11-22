import os
import json
import subprocess
import time

# ----------------------------------------------------
# Configuration
# ----------------------------------------------------
PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")
OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")
RETRY_DELAY = 60

# ----------------------------------------------------
# Sanity Checks
# ----------------------------------------------------
if not RTMP_URL:
    print("❌ ERROR: RTMP_URL is not set!")
    exit(1)

for path, name in [(PLAY_FILE, "Playlist JSON"), (OVERLAY, "Overlay Image"), (FONT_PATH, "Font File")]:
    if not os.path.exists(path):
        print(f"❌ ERROR: {name} '{path}' not found!")
        exit(1)

# ----------------------------------------------------
# Helpers
# ----------------------------------------------------
def load_movies():
    try:
        with open(PLAY_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception as e:
        print(f"❌ Failed to load {PLAY_FILE}: {e}")
        return []

def escape_drawtext(text):
    return (
        text.replace('\\', '\\\\\\\\')
            .replace(':', '\\:')
            .replace("'", "\\'")
    )

# ----------------------------------------------------
# FFmpeg Command (with 404-bypass headers)
# ----------------------------------------------------
def build_ffmpeg_command(url, title):
    text = escape_drawtext(title)

    # Android Chrome headers that work for: http://103.236.179.86:80/...
    input_headers = (
        "User-Agent: Dalvik/2.1.0 (Linux; U; Android 10; Mobile) Chrome/120.0.0.0\r\n"
        "Accept: */*\r\n"
        "Range: bytes=0-\r\n"
        "Connection: keep-alive\r\n"
        "Icy-MetaData: 1\r\n"
    )

    return [
        "ffmpeg",

        # No timeout issues
        "-timeout", "0",
        "-rw_timeout", "-1",
        "-http_persistent", "1",

        # Auto reconnect on all errors
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_delay_max", "10",
        "-reconnect_on_network_error", "1",
        "-reconnect_on_http_error", "4xx,5xx",

        # Stability flags
        "-fflags", "+igndts+discardcorrupt+nobuffer",
        "-flags", "low_delay",
        "-threads", "1",

        # Android spoof
        "-user_agent", "Dalvik/2.1.0 (Linux; U; Android 10; Mobile) Chrome/120.0.0.0",
        "-headers", input_headers,

        # Movie input
        "-i", url,

        # Overlay
        "-i", OVERLAY,
        "-filter_complex",
        (
            "[0:v]scale=1280:720:flags=lanczos,"
            "unsharp=5:5:0.8:5:5:0.0[v];"
            "[1:v]scale=1280:720[ol];"
            "[v][ol]overlay=0:0[vo];"
            f"[vo]drawtext=fontfile='{FONT_PATH}':text='{text}':"
            "fontcolor=white:fontsize=20:x=35:y=35"
        ),

        # Output encoder
        "-r", "29.97",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-maxrate", "2000k",
        "-b:v", "1500k",
        "-bufsize", "2000k",

        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",

        "-f", "flv",
        RTMP_URL,
    ]

# ----------------------------------------------------
# Stream execution
# ----------------------------------------------------
def stream_movie(movie):
    title = movie.get("title", "Untitled")
    url = movie.get("url")

    if not url:
        print(f"❌ Skipping '{title}': Missing URL")
        return

    print(f"\n🎬 Now streaming: {title}")
    print(f"🌐 Source: {url}")

    command = build_ffmpeg_command(url, title)

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )

        for line in process.stderr:
            if "404" in line:
                print(f"🚫 404 from server → Forcing retry: {title}")
                process.kill()
                return

            print(line.strip())

        process.wait()
        print(f"✔ Finished streaming: {title}")

    except Exception as e:
        print(f"❌ FFmpeg crashed: {e}")

# ----------------------------------------------------
# Main loop
# ----------------------------------------------------
def main():
    while True:
        movies = load_movies()

        if not movies:
            print(f"📂 No movies found in {PLAY_FILE}. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            continue

        for movie in movies:
            stream_movie(movie)
            print("⏭️ Next movie in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()

import os
import json
import subprocess
import time

# Configuration
PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")
OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")
RETRY_DELAY = 60

# Sanity Checks
if not RTMP_URL:
    print("❌ ERROR: RTMP_URL is not set!")
    exit(1)

for path, name in [(PLAY_FILE, "Playlist JSON"), (OVERLAY, "Overlay Image"), (FONT_PATH, "Font File")]:
    if not os.path.exists(path):
        print(f"❌ ERROR: {name} '{path}' not found!")
        exit(1)

def load_movies():
    try:
        with open(PLAY_FILE, "r") as f:
            return json.load(f) or []
    except:
        return []

def escape_drawtext(text):
    return text.replace('\\', '\\\\\\\\').replace(':', '\\:').replace("'", "\\'")

def build_ffmpeg_command(url, title):
    text = escape_drawtext(title)

    # Android headers (works with your server)
    header_string = (
        "User-Agent: Dalvik/2.1.0 (Linux; U; Android 10; Mobile) Chrome/120.0.0.0\r\n"
        "Accept: */*\r\n"
        "Range: bytes=0-\r\n"
        "Connection: keep-alive\r\n"
    )

    return [
        "ffmpeg",
        "-re",

        "-http_persistent", "1",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_delay_max", "10",

        "-user_agent", "Dalvik/2.1.0 (Linux; U; Android 10; Mobile) Chrome/120.0.0.0",
        "-headers", header_string,

        "-i", url,   # NO -ss BEFORE THIS

        "-i", OVERLAY,
        "-filter_complex",
        f"[0:v]scale=1280:720:flags=lanczos,unsharp=5:5:0.8:5:5:0.0[v];"
        f"[1:v]scale=1280:720[ol];"
        f"[v][ol]overlay=0:0[vo];"
        f"[vo]drawtext=fontfile='{FONT_PATH}':text='{text}':fontcolor=white:fontsize=20:x=35:y=35",

        "-r", "29.97",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-b:v", "1500k",
        "-maxrate", "2000k",
        "-bufsize", "2000k",

        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",

        "-f", "flv",
        RTMP_URL
    ]

def stream_movie(movie):
    title = movie.get("title", "Untitled")
    url = movie.get("url")

    if not url:
        print(f"❌ Skipping '{title}': no URL")
        return

    print(f"🎬 Now streaming: {title}")

    process = subprocess.Popen(
        build_ffmpeg_command(url, title),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True
    )

    for line in process.stderr:
        print(line.strip())

    process.wait()

def main():
    while True:
        movies = load_movies()
        if not movies:
            print("📂 No entries. Retrying...")
            time.sleep(RETRY_DELAY)
            continue

        for movie in movies:
            stream_movie(movie)
            print("⏭️ Next movie in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()

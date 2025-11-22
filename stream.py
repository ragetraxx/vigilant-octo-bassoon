import os
import json
import subprocess
import time

PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")
OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")

RETRY_DELAY = 60
MAX_RETRY_404 = 10

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
    except Exception as e:
        print(f"❌ Failed to load {PLAY_FILE}: {e}")
        return []

def escape_drawtext(text):
    return text.replace('\\', '\\\\\\\\').replace(':', '\\:').replace("'", "\\'")

def build_ffmpeg_command(url, title):
    text = escape_drawtext(title)

    headers = (
        "User-Agent: Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36\r\n"
        "Accept: */*\r\n"
        "Accept-Language: en-US,en;q=0.9\r\n"
        "Referer: https://hollymoviehd.cc/\r\n"
        "Origin: https://hollymoviehd.cc\r\n"
        "Connection: keep-alive\r\n"
    )

    return [
        "ffmpeg",
        "-re",
        "-seekable", "0",
        "-fflags", "+discardcorrupt",
        "-http_persistent", "1",

        "-user_agent",
        "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",

        "-headers", headers,

        "-i", url,
        "-i", OVERLAY,

        "-filter_complex",
        (
            "[0:v]scale=1280:720:flags=lanczos,unsharp=5:5:0.8:5:5:0.0[v];"
            "[1:v]scale=1280:720[ol];"
            "[v][ol]overlay=0:0[vo];"
            f"[vo]drawtext=fontfile='{FONT_PATH}':text='{text}':fontcolor=white:"
            "fontsize=20:x=35:y=35"
        ),

        "-r", "29.97",
        "-c:v", "libx264",
        "-preset", "fast",
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

    print(f"\n🎬 Streaming: {title}")
    print(f"🔗 URL: {url}")

    retry = 0
    while retry < MAX_RETRY_404:
        command = build_ffmpeg_command(url, title)
        process = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)

        hit_404 = False

        for line in process.stderr:
            line = line.strip()
            print(line)

            if "404" in line or "Not Found" in line:
                hit_404 = True
                break

        process.kill()

        if hit_404:
            retry += 1
            print(f"⚠️ 404 detected! Retrying {retry}/{MAX_RETRY_404}…")
            time.sleep(2)
            continue

        break

    if retry >= MAX_RETRY_404:
        print(f"❌ Skipped {title} — too many 404 errors.")

def main():
    while True:
        movies = load_movies()
        if not movies:
            print(f"📂 No entries in {PLAY_FILE}. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            continue

        for movie in movies:
            stream_movie(movie)
            print("\n⏭ Next movie in 5 seconds…")
            time.sleep(5)

if __name__ == "__main__":
    main()

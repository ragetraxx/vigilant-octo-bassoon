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
PREBUFFER_SECONDS = 5

# ✅ Sanity Checks
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

    # ✅ Your Exact Spoof Parameters (Extracted cleanly)
    UA_STRING = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    
    # ✅ Integrated your customized headers, timeout strings, and reconnect logic
    input_options = [
        "-user_agent", UA_STRING,

        # We append User-Agent here too because FFmpeg drops the standalone flag on sub-playlists/segments
        "-headers", (
            "Referer: https://screenify.fun/\r\n"
            "Origin: https://screenify.fun\r\n"
            f"User-Agent: {UA_STRING}\r\n"
        ),

        "-rw_timeout", "15000000",
        "-timeout", "15000000",

        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_delay_max", "5",

        "-fflags", "+genpts+async",
    ]

    return [
        "ffmpeg",
        *input_options,
        "-ss", str(PREBUFFER_SECONDS),
        "-i", url,
        "-i", OVERLAY,
        
        # ✅ Forces track isolation (solves multiple track buffering/freezing loops)
        "-map", "0:v:0",
        "-map", "0:a:0",
        "-map", "1:v:0", 
        
        "-filter_complex",
        f"[0:v:0]scale=1280:720:flags=lanczos,unsharp=5:5:0.8:5:5:0.0[v];"
        f"[1:v:0]scale=1280:720[ol];"
        f"[v][ol]overlay=0:0[vo];"
        f"[vo]drawtext=fontfile='{FONT_PATH}':text='{text}':fontcolor=white:fontsize=20:x=35:y=35",
        
        "-r", "29.97",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-b:v", "1000k",
        "-maxrate", "1500k",
        "-bufsize", "3000k", 
        "-pix_fmt", "yuv420p",
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
    command = build_ffmpeg_command(url, title)

    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        
        # ✅ Integrated your exact loop and real-time response checks
        for line in process.stderr:
            print(line.strip())

            if "404" in line:
                print(f"❌ Stream URL expired: {title}")
                process.kill()
                return

            if "403" in line:
                print(f"❌ Access denied: {title}")
                process.kill()
                return

        process.wait()
    except Exception as e:
        print(f"❌ FFmpeg crashed: {e}")

def main():
    while True:
        movies = load_movies()
        if not movies:
            print(f"📂 No entries in {PLAY_FILE}. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            continue

        for movie in movies:
            stream_movie(movie)
            print("⏭️  Next movie in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()

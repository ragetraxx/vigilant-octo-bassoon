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

    input_options = [
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "-headers", "Referer: https://www.google.com/\r\nOrigin: https://www.google.com\r\n"
    ]

    return [
        "ffmpeg",
        "-fflags", "+genpts+discardcorrupt+nobuffer",  # regenerate PTS, drop broken packets, no read buffer
        "-flags", "low_delay",
        "-thread_queue_size", "1024",
        "-threads", "4",
        "-use_wallclock_as_timestamps", "1",          # real-time ordering
        "-probesize", "32",                           # minimal probe
        "-analyzeduration", "0",                      # no deep analysis
        "-rtbufsize", "2M",                           # slightly bigger to absorb jitter
        *input_options,
        "-i", url,
        "-i", OVERLAY,
        "-filter_complex",
        f"[0:v]scale=1920:1080:flags=lanczos,unsharp=7:7:1.0:7:7:0.0[v];"
        f"[1:v]scale=1920:1080[ol];"
        f"[v][ol]overlay=0:0[vo];"
        f"[vo]drawtext=fontfile='{FONT_PATH}':text='{text}':fontcolor=white:fontsize=30:x=40:y=40",
        "-r", "30",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level:v", "4.0",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "30",               # keyframe every second
        "-keyint_min", "30",
        "-sc_threshold", "0",
        "-b:v", "3500k",
        "-maxrate", "4000k",
        "-bufsize", "4000k",       # slightly larger for stability
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-profile:a", "aac_low",
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

    print(f"🎬 Streaming: {title}")
    command = build_ffmpeg_command(url, title)

    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        for line in process.stderr:
            if "403 Forbidden" in line:
                print(f"🚫 403 Forbidden! Skipping: {title}")
                process.kill()
                return
            print(line.strip())
        process.wait()
    except Exception as e:
        print(f"❌ FFmpeg crashed: {e}")

def main():
    movies = load_movies()
    if not movies:
        print(f"📂 No entries in {PLAY_FILE}. Retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)
        return main()

    index = 0
    while True:
        stream_movie(movies[index])
        index = (index + 1) % len(movies)
        print("⏭️  Next movie in 5s...")
        time.sleep(5)

if __name__ == "__main__":
    main()

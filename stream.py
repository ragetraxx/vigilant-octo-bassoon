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
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Failed to load {PLAY_FILE}: {e}")
        return []

def escape_drawtext(text):
    return text.replace('\\', '\\\\\\\\').replace(':', '\\:').replace("'", "\\'")

def build_ffmpeg_command(url, title):
    text = escape_drawtext(title)

    # ✅ Headers required to bypass some site protections
    input_options = [
        "-user_agent", "VLC/3.0.18 LibVLC/3.0.18",
        "-headers", "Referer: https://hollymoviehd.cc\r\n",
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5"
    ]

    return [
        "ffmpeg",
        "-re",
        "-fflags", "+nobuffer+genpts",
        "-flags", "low_delay",
        "-threads", "2",
        "-ss", str(PREBUFFER_SECONDS),
        *input_options,
        "-i", url,
        "-i", OVERLAY,
        "-filter_complex",
        # Video: Scale, sharpen, and add the overlay + title text
        f"[0:v]scale=1280:720:flags=lanczos,unsharp=5:5:0.8:5:5:0.0[v];"
        f"[1:v]scale=1280:720[ol];"
        f"[v][ol]overlay=0:0[vo];"
        f"[vo]drawtext=fontfile='{FONT_PATH}':text='{text}':fontcolor=white:fontsize=20:x=35:y=35[outv]",
        
        # ✅ THE MAGIC: Automated Audio Logic
        "-map", "[outv]", 
        "-map", "0:a:m:language:eng?", # 1. Seek English specifically
        "-map", "0:a:0?",              # 2. Fallback to track 1
        "-map", "0:a:1?",              # 3. Fallback to track 2
        
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "60",
        "-b:v", "2500k",               # Increased for better quality
        "-pix_fmt", "yuv420p",
        
        # ✅ Audio encoding for FLV (RTMP Standard)
        "-c:a", "aac",
        "-b:a", "128k",
        "-ac", "2",                    # Downmix 5.1 to Stereo so voices aren't lost
        "-ar", "44100",
        "-af", "aresample=async=1",    # Keeps A/V synced
        
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
        for line in process.stderr:
            if "403 Forbidden" in line:
                print(f"🚫 403 Forbidden on: {title}")
                process.terminate()
                return
            # Uncomment below to debug audio stream mapping in console
            # print(line.strip())
        process.wait()
    except Exception as e:
        print(f"❌ FFmpeg Error: {e}")

def main():
    while True:
        movies = load_movies()
        if not movies:
            time.sleep(10)
            continue

        for movie in movies:
            stream_movie(movie)
            time.sleep(5)

if __name__ == "__main__":
    main()

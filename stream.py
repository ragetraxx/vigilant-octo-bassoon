import os
import json
import subprocess
import time

# ────────────────────────────────────────────────
#                  CONFIGURATION
# ────────────────────────────────────────────────
PLAY_FILE       = "play.json"
RTMP_URL        = os.getenv("RTMP_URL")
OVERLAY         = os.path.abspath("overlay.png")
FONT_PATH       = os.path.abspath("Roboto-Black.ttf")
RETRY_DELAY     = 60
PREBUFFER_SECONDS = 1   # small value – large seek can skip audio init in HLS

# ────────────────────────────────────────────────
#                  SANITY CHECKS
# ────────────────────────────────────────────────
if not RTMP_URL:
    print("❌ ERROR: RTMP_URL environment variable is not set!")
    exit(1)

for path, name in [
    (PLAY_FILE, "Playlist JSON"),
    (OVERLAY,   "Overlay Image"),
    (FONT_PATH, "Font File")
]:
    if not os.path.exists(path):
        print(f"❌ ERROR: {name} not found at '{path}'")
        exit(1)

def load_movies():
    try:
        with open(PLAY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Failed to load {PLAY_FILE}: {e}")
        return []

def escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter"""
    return text.replace('\\', '\\\\\\\\').replace(':', '\\:').replace("'", "\\'").replace('%', '\\%')

def build_ffmpeg_command(url: str, title: str) -> list:
    safe_title = escape_drawtext(title or "Untitled")

    input_options = [
        "-user_agent",      "VLC/3.0.18 LibVLC/3.0.18",
        "-headers",         "Referer: https://screenify.fun/\r\n",
        "-headers",         "Origin: https://screenify.fun\r\n",
        "-headers",         "Accept: */*\r\n",
        "-http_persistent", "1",
    ]

    return [
        "ffmpeg",
        "-re",
        "-fflags",          "+nobuffer",
        "-flags",           "low_delay",
        "-threads",         "1",
        # "-ss",              str(PREBUFFER_SECONDS),   # comment out if audio keeps dropping
        *input_options,
        "-i",               url,                                    # 0: source (HLS most likely)
        "-f", "lavfi",      "-i", "anullsrc=r=48000:cl=stereo",     # 1: silent fallback audio
        "-i",               OVERLAY,                                # 2: overlay png
        "-filter_complex",
        f"[0:v]scale=1280:720:flags=lanczos,unsharp=5:5:0.8:5:5:0.0[v];"
        f"[2:v]scale=1280:720[ol];"
        f"[v][ol]overlay=0:0[vo];"
        f"[vo]drawtext=fontfile='{FONT_PATH}':text='{safe_title}':"
        f"fontcolor=white:fontsize=20:x=35:y=35:borderw=1.2:bordercolor=black[final]",
        "-map",             "[final]",      # filtered video
        "-map",             "0:a?",         # real audio if present (optional)
        "-map",             "1:a",          # silent audio fallback
        "-map_metadata",    "-1",
        "-bsf:a",           "aac_adtstoasc",  # fixes many HLS AAC-in-TS issues
        "-r",               "29.97",
        "-c:v",             "libx264",
        "-preset",          "ultrafast",
        "-tune",            "zerolatency",
        "-g",               "60",
        "-keyint_min",      "60",
        "-sc_threshold",    "0",
        "-b:v",             "1500k",
        "-maxrate",         "2000k",
        "-bufsize",         "2000k",
        "-pix_fmt",         "yuv420p",
        "-c:a",             "aac",
        "-b:a",             "96k",          # lower is fine for silence too
        "-ar",              "48000",
        "-ac",              "2",
        "-shortest",                        # crucial with infinite anullsrc
        "-f",               "flv",
        RTMP_URL
    ]

def stream_movie(movie: dict):
    title = movie.get("title", "Untitled")
    url   = movie.get("url")

    if not url:
        print(f"❌ Skipping '{title}': no URL provided")
        return

    print(f"🎬 Streaming: {title}")
    print(f"   URL: {url}")

    cmd = build_ffmpeg_command(url, title)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout = subprocess.DEVNULL,
            stderr = subprocess.PIPE,
            text   = True,
            bufsize = 1,           # line buffered
            universal_newlines = True
        )

        for line in proc.stderr:
            line = line.strip()
            if not line:
                continue

            if "403 Forbidden" in line or "HTTP error 403" in line:
                print(f"🚫 403 Forbidden → probably bad referer/headers for {title}")
                proc.kill()
                return

            if any(x in line.lower() for x in ["audio", "aac", "stereo", "mono", "silence", "anullsrc"]):
                print(f"   {line}")

            # optional: show progress / errors
            if "time=" in line or "speed=" in line or "Error" in line or "failed" in line:
                print(f"   {line}")

        ret = proc.wait()
        if ret != 0:
            print(f"⚠️  FFmpeg exited with code {ret}")

    except Exception as e:
        print(f"❌ FFmpeg process failed: {e}")

def main():
    while True:
        movies = load_movies()
        if not movies:
            print(f"📂 {PLAY_FILE} is empty or invalid. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            continue

        print(f"Loaded {len(movies)} movie(s) from {PLAY_FILE}")

        for movie in movies:
            stream_movie(movie)
            print("⏭️  Next movie in 5 seconds...\n")
            time.sleep(5)

if __name__ == "__main__":
    print("Starting 24/7 RTMP movie streamer...")
    main()

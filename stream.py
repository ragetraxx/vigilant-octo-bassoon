import os
import json
import subprocess
import time
import urllib.request

# ✅ Configuration
PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")
OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")
RETRY_DELAY = 60
PREBUFFER_SECONDS = 5


# ✅ Escape text for drawtext
def escape_drawtext(text):
    if not text:
        return ""
    return text.replace(":", r"\:").replace("'", r"\'")


# ✅ Download logo if URL exists
def download_logo(url, filename="current_logo.png"):
    try:
        urllib.request.urlretrieve(url, filename)
        return filename
    except Exception as e:
        print(f"⚠️ Failed to download logo: {e}")
        return None


# ✅ Build FFmpeg command with overlay + logo/title
def build_ffmpeg_command(url, title, logo_file):
    text = escape_drawtext(title)

    # ✅ Case 1: Logo exists → overlay.png + logo (no title)
    if logo_file:
        filter_complex = (
            f"[0:v]scale=1280:720:flags=lanczos,format=yuv420p[v];"
            f"[1:v]scale=1280:720,format=rgba[ol];"
            f"[2:v]scale=-1:80,format=rgba[logo];"  # limit height to 80px
            f"[v][ol]overlay=0:0[tmp];"
            f"[tmp][logo]overlay=10:10[vo]"
        )
        inputs = ["-i", url, "-i", OVERLAY, "-i", logo_file]

    # ✅ Case 2: No logo → overlay.png + title
    else:
        filter_complex = (
            f"[0:v]scale=1280:720:flags=lanczos,format=yuv420p[v];"
            f"[1:v]scale=1280:720,format=rgba[ol];"
            f"[v][ol]overlay=0:0[vo];"
            f"[vo]drawtext=fontfile='{FONT_PATH}':text='{text}':"
            f"fontcolor=white:fontsize=25:x=35:y=35"
        )
        inputs = ["-i", url, "-i", OVERLAY]

    return [
        "ffmpeg",
        "-re",
        "-fflags", "+nobuffer",
        "-flags", "low_delay",
        "-threads", "1",
        "-ss", str(PREBUFFER_SECONDS),
        *inputs,
        "-filter_complex", filter_complex,
        "-r", "29.97003",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level:v", "3.2",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-b:v", "1500k",
        "-maxrate", "2000k",
        "-bufsize", "2000k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-profile:a", "aac_low",
        "-b:a", "128k",
        "-ar", "48000",
        "-ac", "2",
        "-f", "flv",
        RTMP_URL,
    ]


# ✅ Play stream list
def play_streams():
    if not os.path.exists(PLAY_FILE):
        print(f"❌ {PLAY_FILE} not found")
        return

    with open(PLAY_FILE, "r", encoding="utf-8") as f:
        movies = json.load(f)

    if not movies:
        print("❌ No movies in play.json")
        return

    for movie in movies:
        title = movie.get("title", "Untitled")
        url = movie.get("url")
        logo_url = movie.get("logo")

        if not url:
            print(f"⚠️ Skipping {title} (no URL)")
            continue

        # ✅ Download logo if present
        logo_file = download_logo(logo_url, "current_logo.png") if logo_url else None

        print(f"🎬 Now streaming: {title}")
        cmd = build_ffmpeg_command(url, title, logo_file)

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ FFmpeg crashed for {title}, retrying in {RETRY_DELAY}s... {e}")
            time.sleep(RETRY_DELAY)


# ✅ Main entry
if __name__ == "__main__":
    print("🚀 Starting stream with buffering optimizations...")
    play_streams()

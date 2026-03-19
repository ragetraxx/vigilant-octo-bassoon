import os
import json
import subprocess
import time

# ✅ Configuration
PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")
OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")
PREBUFFER_SECONDS = 1  # Reduced for faster non-stop transitions

# ✅ Sanity Checks
if not RTMP_URL:
    print("❌ ERROR: RTMP_URL is not set!")
    exit(1)

def load_movies():
    try:
        if not os.path.exists(PLAY_FILE):
            return []
        with open(PLAY_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) and len(data) > 0 else []
    except Exception as e:
        print(f"❌ Failed to load {PLAY_FILE}: {e}")
        return []

def escape_drawtext(text):
    return text.replace('\\', '\\\\\\\\').replace(':', '\\:').replace("'", "\\'")

def build_ffmpeg_command(url, title):
    safe_title = escape_drawtext(title.upper())

    # ✅ NON-STOP INPUT LOGIC: Aggressive reconnection and buffer management
    input_options = [
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "-headers", "Referer: https://screenify.fun/\r\nOrigin: https://screenify.fun\r\n",
        "-reconnect", "1", 
        "-reconnect_at_eof", "1", 
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",      # Fast reconnect
        "-fflags", "+nobuffer+genpts+igndts+flush_packets", 
        "-probesize", "20M",              # High probe for instant audio detection
        "-analyzeduration", "20M"
    ]

    filter_string = (
        f"[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720[main];" # Fits any aspect ratio
        f"[1:v]scale=1280:720[ol];"
        f"[main][ol]overlay=0:0[v_base];"
        f"[v_base]drawbox=y=ih-45:color=black@0.6:width=iw:height=45:t=fill[v_bar];" 
        f"[v_bar]drawtext=fontfile='{FONT_PATH}':text='NOW PLAYING\\: {safe_title}':"
        f"fontcolor=white:fontsize=24:y=h-32:x=w-mod(t*90\\,w+1000)[outv]" 
    )

    return [
        "ffmpeg",
        "-re",
        *input_options,
        "-i", url,
        "-i", OVERLAY,
        "-filter_complex", filter_string,
        "-map", "[outv]", 
        "-map", "0:a:m:language:eng?", 
        "-map", "0:a:0?", 
        "-c:v", "libx264",
        "-preset", "ultrafast", # Fastest encoding for 24/7 stability
        "-tune", "zerolatency",
        "-g", "60",
        "-b:v", "2500k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ac", "2",
        "-ar", "44100",
        "-af", "aresample=async=1",
        "-f", "flv",
        "-flvflags", "no_duration_filesize", # Optimized for streaming
        RTMP_URL
    ]

def stream_loop():
    print("🎬 Starting 24/7 Non-Stop Broadcast...")
    
    while True:
        movies = load_movies()
        
        if not movies:
            print("📂 Playlist is empty or play.json missing. Waiting 10s...")
            time.sleep(10)
            continue

        for movie in movies:
            title = movie.get("title", "Feature Film")
            url = movie.get("url")
            
            if not url:
                continue

            print(f"📡 Now Playing: {title}")
            command = build_ffmpeg_command(url, title)

            try:
                # Start FFmpeg
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                
                # We monitor for fatal errors to skip bad links quickly
                for line in process.stderr:
                    if "403 Forbidden" in line or "Server returned 404" in line:
                        print(f"⚠️ Link expired/blocked: {title}. Skipping...")
                        process.terminate()
                        break
                
                process.wait() # Wait for movie to finish normally
            except Exception as e:
                print(f"🔥 FFmpeg Encountered an Error: {e}")
                time.sleep(2) # Brief pause before next movie
            
            print("⏭️ Moving to next program immediately...")

if __name__ == "__main__":
    stream_loop()

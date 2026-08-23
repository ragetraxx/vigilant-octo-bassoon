import os
import json
import subprocess
import time
import signal

# ============================================================
# CONFIGURATION
# ============================================================

PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")

OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")

RETRY_DELAY = 60
MAX_STREAM_RETRIES = 3
NEXT_MOVIE_DELAY = 5

# Video settings
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 29.97

VIDEO_BITRATE = "2500k"
VIDEO_MAXRATE = "3000k"
VIDEO_BUFSIZE = "6000k"

AUDIO_BITRATE = "128k"
AUDIO_RATE = "48000"

# ============================================================
# SANITY CHECKS
# ============================================================

if not RTMP_URL:
    print("❌ ERROR: RTMP_URL is not set!")
    exit(1)

required_files = [
    (PLAY_FILE, "Playlist JSON"),
    (OVERLAY, "Overlay Image"),
    (FONT_PATH, "Font File"),
]

for path, name in required_files:
    if not os.path.exists(path):
        print(f"❌ ERROR: {name} '{path}' not found!")
        exit(1)


# ============================================================
# LOAD PLAYLIST
# ============================================================

def load_movies():
    try:
        with open(PLAY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("❌ ERROR: play.json must contain a JSON list.")
            return []

        return data

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {PLAY_FILE}: {e}")
        return []

    except Exception as e:
        print(f"❌ Failed to load {PLAY_FILE}: {e}")
        return []


# ============================================================
# ESCAPE DRAWTEXT
# ============================================================

def escape_drawtext(text):
    """
    Escape characters that have special meaning in FFmpeg drawtext.
    """

    text = str(text)

    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    text = text.replace("%", "\\%")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")

    return text


# ============================================================
# BUILD FFMPEG COMMAND
# ============================================================

def build_ffmpeg_command(movie):

    title = movie.get("title", "Untitled")
    url = movie.get("url")

    text = escape_drawtext(title)

    # --------------------------------------------------------
    # NETWORK INPUT OPTIONS
    # --------------------------------------------------------

    input_options = [
        # Automatic reconnect
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "10",

        # Network timeout
        "-rw_timeout", "60000000",

        # HTTP connection handling
        "-http_persistent", "1",
        "-http_multiple", "1",

        # More time/data for stream detection
        "-analyzeduration", "10M",
        "-probesize", "10M",

        # Browser-like User-Agent
        "-user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36",
    ]

    # --------------------------------------------------------
    # OPTIONAL REFERER
    # --------------------------------------------------------

    referer = movie.get("referer")

    custom_headers = movie.get("headers")

    header_str = ""

    if referer:
        header_str += f"Referer: {referer}\r\n"

    if custom_headers:
        header_str += f"{custom_headers}\r\n"

    if header_str:
        input_options.extend([
            "-headers",
            header_str
        ])

    # --------------------------------------------------------
    # FILTER
    # --------------------------------------------------------

    filter_complex = (
        f"[0:v]"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:flags=bicubic"
        f"[v];"

        f"[1:v]"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
        f"[ol];"

        f"[v][ol]"
        f"overlay=0:0"
        f"[vo];"

        f"[vo]"
        f"drawtext="
        f"fontfile='{FONT_PATH}':"
        f"text='{text}':"
        f"fontcolor=white:"
        f"fontsize=20:"
        f"x=35:"
        f"y=35"
    )

    # --------------------------------------------------------
    # FFMPEG COMMAND
    # --------------------------------------------------------

    command = [
        "ffmpeg",

        # Do NOT use -re here.
        # Network/HLS input should be read as data arrives.
        
        "-hide_banner",

        "-loglevel", "info",

        "-fflags",
        "+genpts+discardcorrupt",

        *input_options,

        # ----------------------------------------------------
        # MAIN VIDEO INPUT
        # ----------------------------------------------------

        "-thread_queue_size", "4096",
        "-i", url,

        # ----------------------------------------------------
        # OVERLAY INPUT
        # ----------------------------------------------------

        "-loop", "1",
        "-framerate", str(VIDEO_FPS),
        "-thread_queue_size", "1024",
        "-i", OVERLAY,

        # ----------------------------------------------------
        # VIDEO FILTER
        # ----------------------------------------------------

        "-filter_complex",
        filter_complex,

        "-map", "[vo]",
        "-map", "0:a?",

        # ----------------------------------------------------
        # VIDEO ENCODING
        # ----------------------------------------------------

        "-r", str(VIDEO_FPS),

        "-c:v", "libx264",

        "-preset", "veryfast",

        "-tune", "zerolatency",

        "-g", "60",

        "-keyint_min", "60",

        "-sc_threshold", "0",

        "-b:v", VIDEO_BITRATE,

        "-maxrate", VIDEO_MAXRATE,

        "-bufsize", VIDEO_BUFSIZE,

        "-pix_fmt", "yuv420p",

        # ----------------------------------------------------
        # AUDIO ENCODING
        # ----------------------------------------------------

        "-c:a", "aac",

        "-b:a", AUDIO_BITRATE,

        "-ar", AUDIO_RATE,

        "-ac", "2",

        "-af", "aresample=async=1:first_pts=0",

        # ----------------------------------------------------
        # RTMP OUTPUT
        # ----------------------------------------------------

        "-f", "flv",

        RTMP_URL,
    ]

    return command


# ============================================================
# STREAM ONE MOVIE
# ============================================================

def stream_movie(movie):

    title = movie.get("title", "Untitled")
    url = movie.get("url")

    if not url:
        print(f"❌ Skipping '{title}': no URL")
        return

    retries = 0

    while retries < MAX_STREAM_RETRIES:

        print()
        print("=" * 70)
        print(
            f"🎬 Now streaming: {title} "
            f"(Attempt {retries + 1}/{MAX_STREAM_RETRIES})"
        )
        print("=" * 70)

        command = build_ffmpeg_command(movie)

        process = None

        try:

            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            fatal_error = False

            # ------------------------------------------------
            # READ FFMPEG OUTPUT
            # ------------------------------------------------

            for line in process.stderr:

                line_str = line.strip()

                if not line_str:
                    continue

                print(line_str)

                lower_line = line_str.lower()

                # ------------------------------------------------
                # PERMANENT URL ERRORS
                # ------------------------------------------------

                if (
                    "403 forbidden" in lower_line
                    or "404 not found" in lower_line
                    or "server returned 404" in lower_line
                    or "http error 403" in lower_line
                    or "http error 404" in lower_line
                ):

                    print()
                    print(
                        f"🚫 Permanent HTTP error detected for '{title}'."
                    )

                    fatal_error = True

                    try:
                        process.kill()
                    except Exception:
                        pass

                    break

            # ------------------------------------------------
            # WAIT FOR FFMPEG
            # ------------------------------------------------

            process.wait()

            return_code = process.returncode

            if fatal_error:

                print(
                    f"⏭️ Skipping '{title}' because the source URL "
                    f"returned a permanent HTTP error."
                )

                return

            # ------------------------------------------------
            # NORMAL COMPLETION
            # ------------------------------------------------

            if return_code == 0:

                print()
                print(f"✅ Finished playing: {title}")

                return

            # ------------------------------------------------
            # FFMPEG FAILURE
            # ------------------------------------------------

            print()
            print(
                f"⚠️ FFmpeg stopped with exit code "
                f"{return_code}."
            )

            retries += 1

            if retries < MAX_STREAM_RETRIES:

                print(
                    "🔄 Restarting current movie in 3 seconds..."
                )

                time.sleep(3)

        except KeyboardInterrupt:

            print()
            print("🛑 Stopping streamer...")

            if process:

                try:
                    process.terminate()
                    process.wait(timeout=5)

                except Exception:

                    try:
                        process.kill()
                    except Exception:
                        pass

            raise

        except Exception as e:

            print()
            print(f"❌ FFmpeg exception: {e}")

            retries += 1

            if retries < MAX_STREAM_RETRIES:
                time.sleep(3)

    # --------------------------------------------------------
    # MAX RETRIES
    # --------------------------------------------------------

    print()
    print(
        f"❌ Max retries reached for '{title}'. "
        f"Moving to next movie."
    )


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    print()
    print("=" * 70)
    print("📺 24/7 RTMP STREAMER")
    print("=" * 70)
    print(f"📂 Playlist: {PLAY_FILE}")
    print(f"🖼️ Overlay: {OVERLAY}")
    print(f"🔤 Font: {FONT_PATH}")
    print("=" * 70)
    print()

    while True:

        movies = load_movies()

        if not movies:

            print(
                f"📂 No entries found in {PLAY_FILE}. "
                f"Retrying in {RETRY_DELAY} seconds..."
            )

            time.sleep(RETRY_DELAY)
            continue

        # ----------------------------------------------------
        # PLAY EACH MOVIE
        # ----------------------------------------------------

        for movie in movies:

            try:

                stream_movie(movie)

            except KeyboardInterrupt:

                print()
                print("🛑 Streamer stopped by user.")
                return

            except Exception as e:

                print(
                    f"❌ Unexpected error while processing movie: {e}"
                )

            print()
            print(
                f"⏭️ Next movie in {NEXT_MOVIE_DELAY} seconds..."
            )

            time.sleep(NEXT_MOVIE_DELAY)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print("🛑 Streamer stopped.")

import os
import json
import subprocess
import time

# ============================================================
# CONFIGURATION
# ============================================================

PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")

OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")

RETRY_DELAY = 60
MAX_STREAM_RETRIES = 3


# ============================================================
# SANITY CHECKS
# ============================================================

if not RTMP_URL:
    print("❌ ERROR: RTMP_URL is not set!")
    exit(1)

for path, name in [
    (PLAY_FILE, "Playlist JSON"),
    (OVERLAY, "Overlay Image"),
    (FONT_PATH, "Font File")
]:
    if not os.path.exists(path):
        print(f"❌ ERROR: {name} '{path}' not found!")
        exit(1)


# ============================================================
# LOAD PLAYLIST
# ============================================================

def load_movies():

    try:
        with open(PLAY_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or []

    except Exception as e:

        print(f"❌ Failed to load {PLAY_FILE}: {e}")
        return []


# ============================================================
# ESCAPE DRAWTEXT
# ============================================================

def escape_drawtext(text):

    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


# ============================================================
# BUILD FFMPEG COMMAND
# ============================================================

def build_ffmpeg_command(movie):

    title = movie.get("title", "Untitled")
    url = movie.get("url")

    text = escape_drawtext(title)

    # --------------------------------------------------------
    # NETWORK OPTIONS
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # These are kept very close to your ORIGINAL settings.
    # Only the timeout has been increased.
    #
    # --------------------------------------------------------

    input_options = [
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "10",

        # 60 seconds instead of the original 15 seconds
        "-rw_timeout", "60000000",

        "-analyzeduration", "10000000",
        "-probesize", "10000000",

        "-user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ]


    # --------------------------------------------------------
    # OPTIONAL REFERER / HEADERS
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
        f"scale=1280:720:flags=bicubic"
        f"[v];"

        f"[1:v]"
        f"scale=1280:720"
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


    # ========================================================
    # FFMPEG
    # ========================================================

    return [

        "ffmpeg",

        # ----------------------------------------------------
        # IMPORTANT:
        # REMOVED "-re"
        #
        # The source is already a network stream.
        # -re can unnecessarily throttle the input.
        # ----------------------------------------------------

        "-fflags",
        "+genpts+discardcorrupt",

        *input_options,


        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        "-thread_queue_size",
        "4096",

        "-i",
        url,


        # ----------------------------------------------------
        # OVERLAY
        # ----------------------------------------------------

        "-thread_queue_size",
        "1024",

        "-i",
        OVERLAY,


        # ----------------------------------------------------
        # VIDEO FILTER
        # ----------------------------------------------------

        "-filter_complex",
        filter_complex,


        # ----------------------------------------------------
        # OUTPUT
        # ----------------------------------------------------

        "-r",
        "29.97",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-g",
        "60",

        "-keyint_min",
        "60",

        "-sc_threshold",
        "0",

        "-b:v",
        "2500k",

        "-maxrate",
        "3000k",

        "-bufsize",
        "6000k",

        "-pix_fmt",
        "yuv420p",


        # ----------------------------------------------------
        # AUDIO
        # ----------------------------------------------------

        "-c:a",
        "aac",

        "-b:a",
        "128k",

        "-ar",
        "48000",

        "-ac",
        "2",

        "-af",
        "aresample=async=1",


        # ----------------------------------------------------
        # RTMP
        # ----------------------------------------------------

        "-f",
        "flv",

        RTMP_URL
    ]


# ============================================================
# STREAM MOVIE
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
        print(
            f"🎬 Now streaming: {title} "
            f"(Attempt {retries + 1}/{MAX_STREAM_RETRIES})"
        )


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
            # MONITOR FFMPEG
            # ------------------------------------------------

            for line in process.stderr:

                line_str = line.strip()

                if not line_str:
                    continue

                print(line_str)


                # --------------------------------------------
                # ONLY TREAT 403/404 AS PERMANENT ERRORS
                # --------------------------------------------

                if any(
                    error in line_str
                    for error in [
                        "403 Forbidden",
                        "404 Not Found",
                        "Server returned 404"
                    ]
                ):

                    print(
                        f"🚫 Stream URL error (403/404)! "
                        f"Skipping: {title}"
                    )

                    fatal_error = True

                    try:
                        process.kill()
                    except Exception:
                        pass

                    break


            process.wait()


            # ------------------------------------------------
            # PERMANENT ERROR
            # ------------------------------------------------

            if fatal_error:
                return


            # ------------------------------------------------
            # MOVIE FINISHED
            # ------------------------------------------------

            if process.returncode == 0:

                print(
                    f"✅ Finished playing: {title}"
                )

                return


            # ------------------------------------------------
            # STREAM FAILED
            # ------------------------------------------------

            print(
                f"⚠️ FFmpeg stopped with code "
                f"{process.returncode}."
            )

            retries += 1


            if retries < MAX_STREAM_RETRIES:

                print(
                    "🔄 Retrying current movie in 3 seconds..."
                )

                time.sleep(3)


        except Exception as e:

            print(
                f"❌ FFmpeg exception: {e}"
            )

            retries += 1

            time.sleep(3)


    print(
        f"❌ Max retries reached for '{title}'. "
        f"Moving to next movie."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    while True:

        movies = load_movies()


        if not movies:

            print(
                f"📂 No entries in {PLAY_FILE}. "
                f"Retrying in {RETRY_DELAY}s..."
            )

            time.sleep(RETRY_DELAY)

            continue


        for movie in movies:

            stream_movie(movie)

            print(
                "⏭️ Next movie in 5s..."
            )

            time.sleep(5)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print("🛑 Streamer stopped.")

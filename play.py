import json
import random

MOVIE_FILE = "movies.json"  # Permanent source JSON file
PLAY_FILE = "play.json"  # Stores selected movies
INTRO_VIDEO = {
    "title": "RageTV",
    "url": "https://video.gumlet.io/68b208ee7faf3595aba2a60b/68b20a2814a50ac8634389e2/68b20a2814a50ac8634389e2_0_720p.m3u8"
}

def load_movies(filename):
    """Load movies from a specified JSON file"""
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_play_movies(movies):
    """Overwrite play.json with new selected movies and insert intro video before each"""
    updated_list = []
    for movie in movies:
        updated_list.append(INTRO_VIDEO)  # Add intro first
        updated_list.append(movie)        # Then the actual movie

    with open(PLAY_FILE, "w", encoding="utf-8") as file:
        json.dump(updated_list, file, indent=4)

def update_play_json():
    """Randomly select 5 movies not already played and overwrite play.json"""
    all_movies = load_movies(MOVIE_FILE)  # Load all available movies
    played_movies = load_movies(PLAY_FILE)  # Load previously played movies

    # Normalize played_movies to only objects with title
    normalized_played = []
    for m in played_movies:
        if isinstance(m, dict):
            if m.get("title") != "RageTV":  # Ignore intro
                normalized_played.append(m)
        else:
            # If it's a string (old format), keep it
            normalized_played.append(m)

    # Filter out movies that have already been played
    available_movies = [movie for movie in all_movies if movie not in normalized_played]

    # If there are not enough movies left, reset the cycle
    if len(available_movies) < 5:
        print("All movies have been played. Restarting the cycle.")
        available_movies = all_movies  # Reset to all movies

    # Randomly select 5 new movies
    selected_movies = random.sample(available_movies, 5)

    # Save intro + movies to play.json
    save_play_movies(selected_movies)
    print("✅ Updated play.json with RageTV intro before each movie.")

if __name__ == "__main__":
    update_play_json()

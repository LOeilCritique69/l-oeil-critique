from flask import Flask, render_template
from bs4 import BeautifulSoup

app = Flask(__name__)
import xml.etree.ElementTree as ET

import requests

TMDB_API_KEY = "2cf75db44f938aeaf1e7d873a38fdcaa"
from playwright.sync_api import sync_playwright

def get_trailers():
    upcoming_url = "https://api.themoviedb.org/3/movie/upcoming"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "fr-FR",
        "region": "FR",
        "page": 1
    }

    response = requests.get(upcoming_url, params=params)
    movies = response.json().get("results", [])
    all_trailers = []

    for movie in movies:
        movie_id = movie["id"]
        title = movie["title"]

        videos_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos"
        res = requests.get(videos_url, params={"api_key": TMDB_API_KEY})
        videos = res.json().get("results", [])

        for v in videos:
            if v["site"] == "YouTube" and v["type"] == "Trailer":
                published_at = v.get("published_at")
                if published_at:
                    all_trailers.append({
                        "title": title,
                        "published_at": published_at,
                        "iframe": f"https://www.youtube.com/embed/{v['key']}"
                    })

    # Trie tous les trailers par date décroissante
    sorted_trailers = sorted(all_trailers, key=lambda x: x["published_at"], reverse=True)

    return sorted_trailers[:10]

@app.route("/")
def index():
    trailers = get_trailers()
    print(trailers)  # 👁️ Pour debug
    return render_template("index.html", trailers=trailers)

if __name__ == "__main__":
    app.run(debug=True)
# AniListrr

Parses the MyAnimeList API and outputs json to `filtered_anime.json` and `filtered_anime_movies.json` that is usable in Sonarr/Radarr (list of tvdb/tmdb IDs). The conditions for the list are: airing in the current season, rating of 7.7 or above, and at least 1000 user votes.

The script can be run using `python main.py`

The environment variable `MAL_CLIENT_ID` must be set to the API client ID found in your MAL profile settings.

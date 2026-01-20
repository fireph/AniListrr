import os
import requests
import yaml
import json
from datetime import datetime

def get_current_season_and_year(neg_seasons=0):
    """
    Returns the current anime season ('winter', 'spring', 'summer', or 'fall')
    and the current year as integers.
    """
    now = datetime.now()
    month = now.month - (neg_seasons * 3)
    year = now.year

    if month < 1:
        month = 12 + month
        year = year - 1

    # Define season by month:
    #   winter: 1,2,3
    #   spring: 4,5,6
    #   summer: 7,8,9
    #   fall:   10,11,12
    if month in [1, 2, 3]:
        season = "winter"
    elif month in [4, 5, 6]:
        season = "spring"
    elif month in [7, 8, 9]:
        season = "summer"
    else:
        season = "fall"

    return season, year

def get_seasonal_anime(year, season, limit=100):
    """
    Fetch up to 'limit' anime from MyAnimeList for a given season and year.
    Returns the raw list of anime data from the MAL response.
    """
    url = f"https://api.myanimelist.net/v2/anime/season/{year}/{season}"
    params = {
        "sort": "anime_score",
        "limit": limit,
        # Request the media_type field so we can distinguish between "tv", "movie", etc.
        "fields": "mean,num_scoring_users,media_type"
    }

    # Retrieve MAL Client ID from environment variable
    mal_client_id = os.environ.get("MAL_CLIENT_ID", "")
    if not mal_client_id:
        raise ValueError("MAL_CLIENT_ID environment variable is not set!")

    headers = {
        "X-MAL-CLIENT-ID": mal_client_id
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()

    # Return the "data" list for further filtering
    return data.get("data", [])

def filter_anime_entries(entries, min_score=7.7, min_votes=1000, media_type_filter=None):
    """
    Given a list of MAL anime entries, filter them by:
      - Minimum score
      - Minimum number of votes
      - Optional media_type (e.g., "movie" for anime movies)
    Returns a list of MAL IDs.
    """
    filtered_ids_and_titles = []
    for entry in entries:
        anime_data = entry.get("node", {})
        mal_id = anime_data.get("id")
        score = float(anime_data.get("mean", 0))
        title = anime_data.get("title")
        num_scoring_users = int(anime_data.get("num_scoring_users", 0))
        media_type = anime_data.get("media_type", "").lower()  # "tv", "movie", etc.

        # If media_type_filter is specified, skip entries that don't match
        if media_type_filter and media_type != media_type_filter.lower():
            continue

        if score >= min_score and num_scoring_users >= min_votes:
            filtered_ids_and_titles.append([mal_id, title])

    return filtered_ids_and_titles

def create_mal_to_db_mapping():
    mapping_url = "https://raw.githubusercontent.com/Fribb/anime-lists/refs/heads/master/anime-list-mini.json"
    response = requests.get(mapping_url)
    response.raise_for_status()

    # Parse the JSON (it’s an array of objects)
    data = response.json()  # This will be a list of dicts

    # Create a dict mapping MAL ID -> DB field (if present)
    mal_to_db_map = {}
    for item in data:
        # Each item has "mal_id", "thetvdb_id", "themoviedb_id", etc.
        # Some entries might not have a valid 'mal_id' or the requested db field
        if "mal_id" in item:
            mal_id = item.get("mal_id")
            tvdb_id = item.get("tvdb_id")
            tmdb_id = item.get("themoviedb_id")
            if mal_id is not None and (tvdb_id is not None or tmdb_id is not None):
                mal_to_db_map[int(mal_id)] = {
                    "tvdb_id": tvdb_id,
                    "tmdb_id": tmdb_id
                }

    return mal_to_db_map

def map_mal_to_db(mal_ids_and_titles, mal_to_db_map, db="tvdb"):
    """
    Given a list of MAL IDs, map them to the IDs of indicated DB by using the YAML mapping
    from varoOP/shinkro-mapping on GitHub.
    """

    # Map each MAL ID to DB ID (if it exists in the YAML)
    db_ids = set()
    found_titles = []
    unknown_titles = []
    for mal_id, title in mal_ids_and_titles:
        dbs = mal_to_db_map.get(int(mal_id))
        prefix_str = str(mal_id) + "->?" + ": "
        if dbs is not None:
            db_id = dbs.get(f"{db}_id")
            prefix_str = str(mal_id) + "->" + str(db_id) + ": "
            if db_id is None:
                unknown_titles.append(prefix_str + title)
            elif db_id not in db_ids:
                db_ids.add(int(db_id))
                found_titles.append(prefix_str + title)
        else:
            unknown_titles.append(prefix_str + title)

    print(f"Found {db} mappings for: {found_titles}")
    if (len(unknown_titles) > 0):
        print(f"Could not find {db} mappings for: {unknown_titles}!")
    return list(db_ids), found_titles

def main():
    mal_to_db_map = create_mal_to_db_mapping()

    # get anime of the last 4 seasons
    raw_entries = []
    for i in range(4):
        season, year = get_current_season_and_year(i)
        print(f"Processing {season.capitalize()} {year} anime season...")
        # Fetch and extend raw entries with the current season's data
        season_entries = get_seasonal_anime(year, season, limit=100)
        raw_entries.extend(season_entries)

    # Filter anime TV
    tv_mal_ids_and_titles = filter_anime_entries(
        raw_entries,
        min_score=7.8,
        min_votes=1000,
        media_type_filter="tv"
    )

    # Filter anime ONA
    ona_mal_ids_and_titles = filter_anime_entries(
        raw_entries,
        min_score=7.8,
        min_votes=1000,
        media_type_filter="ona"
    )

    # Combine TV and ONA entries
    combined_mal_ids_and_titles = tv_mal_ids_and_titles + ona_mal_ids_and_titles

    tvdb_ids, tv_titles = map_mal_to_db(combined_mal_ids_and_titles, mal_to_db_map, "tvdb")
    print(f"Found {len(tvdb_ids)} TV/ONA anime IDs that match the score/vote criteria.")

    # Filter anime movies
    movies_mal_ids_and_titles = filter_anime_entries(
        raw_entries,
        min_score=7.7,
        min_votes=1000,
        media_type_filter="movie"
    )
    tmdb_ids_movies, movie_titles = map_mal_to_db(movies_mal_ids_and_titles, mal_to_db_map, "tmdb")
    print(f"Found {len(tmdb_ids_movies)} movies anime IDs that match the score/vote criteria.")

    sonarr_list = []
    for tvdb_id in sorted(tvdb_ids):
        sonarr_list.append({"tvdbId": str(tvdb_id)})

    # Print the final list of TVDB IDs
    print(f"TVDB IDs that passed the filter: {sonarr_list}")

    with open("filtered_anime.json", "w", encoding="utf-8") as f:
        json.dump(sonarr_list, f, separators=(',', ':'))

    with open("filtered_anime.txt", "w", encoding="utf-8") as f:
        f.write("MAL->TVDB: Title\n" + "\n".join(sorted(tv_titles)))

    radarr_list = []
    for tmdb_id in sorted(tmdb_ids_movies):
        radarr_list.append({"id": str(tmdb_id)})

    # Print the final list of TMDB IDs
    print(f"TMDB IDs that passed the filter: {radarr_list}")

    with open("filtered_anime_movies.json", "w", encoding="utf-8") as f:
        json.dump(radarr_list, f, separators=(',', ':'))

    with open("filtered_anime_movies.txt", "w", encoding="utf-8") as f:
        f.write("MAL->TMDB: Title\n" + "\n".join(sorted(movie_titles)))

if __name__ == "__main__":
    main()

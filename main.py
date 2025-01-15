import os
import requests
import yaml
import json
from datetime import datetime

def get_current_season_and_year():
    """
    Returns the current anime season ('winter', 'spring', 'summer', or 'fall')
    and the current year as integers.
    """
    now = datetime.now()
    month = now.month
    year = now.year
    
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

def get_seasonal_anime_ids(year, season, limit=100, min_score=7.5, min_votes=1000):
    """
    Fetch top 'limit' anime from MyAnimeList for a given season and year,
    filtered by min_score and min_votes.
    Returns a list of MAL anime IDs.
    """
    
    # 1. Construct the seasonal anime endpoint
    # Add fields=mean,scored_by so we can filter by score and votes in a single request
    url = f"https://api.myanimelist.net/v2/anime/season/{year}/{season}"
    params = {
        "sort": "anime_score",
        "limit": limit,
        "fields": "mean,num_scoring_users"
    }

    # Read MAL Client ID from environment variable
    mal_client_id = os.environ.get("MAL_CLIENT_ID", "")
    if not mal_client_id:
        raise ValueError("MAL_CLIENT_ID environment variable is not set!")
    
    # 2. Make the request to MAL
    headers = {
        "X-MAL-CLIENT-ID": mal_client_id
    }
    response = requests.get(url, headers=headers, params=params)
    
    # Raise an exception if the request failed
    response.raise_for_status()
    
    data = response.json()
    
    # 3. Filter anime based on score and number of votes
    filtered_ids = []
    for entry in data.get("data", []):
        anime_data = entry.get("node", {})
        mal_id = anime_data.get("id")
        score = float(anime_data.get("mean", 0))
        num_scoring_users = int(anime_data.get("num_scoring_users", 0))
        
        if score >= min_score and num_scoring_users >= min_votes:
            filtered_ids.append(mal_id)
    
    return filtered_ids

def map_mal_to_tvdb(mal_ids):
    """
    Given a list of MAL IDs, map them to TVDB IDs by using the YAML mapping
    from varoOP/shinkro-mapping on GitHub.
    """
    
    # 1. Fetch the YAML mapping from GitHub
    mapping_url = "https://raw.githubusercontent.com/varoOP/shinkro-mapping/refs/heads/main/tvdb-mal.yaml"
    response = requests.get(mapping_url)
    response.raise_for_status()
    
    # 2. Load YAML data
    data = yaml.safe_load(response.text)

    # Convert the YAML list into a dict { malid: tvdbid, ... }
    # Some YAMLs might store malid as strings, but typically these are integers
    # We'll unify everything as int to avoid mismatch.
    anime_map = data.get("AnimeMap", [])
    mal_to_tvdb_map = {int(item["malid"]): item["tvdbid"] for item in anime_map if "malid" in item and "tvdbid" in item}
    
    # 3. Map each MAL ID to TVDB ID (if it exists in the YAML)
    tvdb_ids = []
    for mal_id in mal_ids:
        if mal_id in mal_to_tvdb_map:
            tvdb_ids.append(mal_to_tvdb_map[mal_id])
    
    return tvdb_ids

def main():
    # 1. Get the current season and year
    season, year = get_current_season_and_year()
    print(f"Detected {season.capitalize()} {year} as the current anime season.")
    
    # 2. Get MAL IDs of anime meeting the criteria
    mal_ids = get_seasonal_anime_ids(year, season, limit=100, min_score=7.5, min_votes=1000)
    print(f"Found {len(mal_ids)} anime IDs that match the score/vote criteria.")
    
    # 2. Convert those MAL IDs to TVDB IDs
    tvdb_ids = map_mal_to_tvdb(mal_ids)

    sonarr_list = []
    for tvdb_id in tvdb_ids:
    	sonarr_list.append({"tvdbId": tvdb_id})
    
    # 3. Print the final list of TVDB IDs
    print("TVDB IDs that passed the filter:")
    print(sonarr_list)

    with open("filtered_anime.json", "w", encoding="utf-8") as f:
        json.dump(sonarr_list, f, indent=2)

if __name__ == "__main__":
    main()

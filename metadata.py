from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TDRC, TCON, USLT, Encoding 
import requests
from urllib.parse import quote
import os
from bs4 import BeautifulSoup

GENIUS_API_KEY = "f-STK_KYiwc0xlEI3heyY9O9HPvQFdnfo2_vl6YKS_H_yfbH65reCTGtQlOCtUyR"
LRCLIB_BASE_URL = "https://lrclib.net"  # Public LRCLib instance

def is_valid_lyrics(lyrics, title):
    """
    Checks if the lyrics seem valid.
    Heuristic:
      - Reject if lyrics is empty or contains "Lyrics not found".
      - If there are more than 50 lines and the average line length is below 20 chars,
        consider it invalid (likely a listing of track names).
      - Optionally, if the title doesn't appear anywhere in the lyrics and there are many lines,
        consider it invalid.
    """
    if not lyrics or "Lyrics not found" in lyrics:
        return False
    lines = [line.strip() for line in lyrics.strip().splitlines() if line.strip()]
    if not lines:
        return False
    if len(lines) > 100:
       
        return False
    # Optional check: if the title (or a significant portion) is not present in the lyrics,
    # and there are a fair number of lines, consider it invalid.
    if title.lower() not in lyrics.lower():
        return False
    return True

def fetch_lyrics(title, artistt=None, isFromYoutube=False):
    """
    Attempts to fetch lyrics for a given track using LRCLib as a priority.
    If an artist is provided and is not "Unknown Artist", it calls the LRCLib API
    to retrieve lyrics (preferring syncedLyrics). If that fails, or if no valid
    lyrics are returned, it falls back to fetching from Genius.
    """
    # Normalize artist: if it's a list or a string with commas, use only the first artist.
    #if artist and artist.lower() != "unknown artist":
    if isinstance(artistt, list):
            artistt = artistt[0]
    elif isinstance(artistt, str) and "," in artistt:
            artistt = artistt.split(",")[0].strip()
    artist = "; ".join(artistt) if isinstance(artistt, list) else artistt
    # Try LRCLib if a valid artist is provided
    if artist and artist.lower() != "unknown artist":
        try:
            lrclib_url = f"{LRCLIB_BASE_URL}/api/get"
            params = {"track_name": title, "artist_name": artist}
            response = requests.get(lrclib_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Prefer synced lyrics if available; otherwise plain lyrics.
                if data.get("syncedLyrics") and not isFromYoutube:
                    return data.get("syncedLyrics")
                elif data.get("plainLyrics"):
                    return data.get("plainLyrics")
            else:
                print(f"LRCLib API returned status {response.status_code} for '{title}' by '{artist}'.")
        except Exception as e:
            print(f"LRCLib fetch error: {e}")
    
    # Fallback: Genius API
    try:
        query = f"{title} {artist}" if artist else title
        search_query = quote(query)
        search_url = f"https://api.genius.com/search?q={search_query}"
        headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
        response = requests.get(search_url, headers=headers, timeout=10).json()
        hits = response.get("response", {}).get("hits", [])
        if not hits:
            return None
        song_url = hits[0]["result"]["url"]
        song_page = requests.get(song_url, timeout=10).text
        soup = BeautifulSoup(song_page, "html.parser")
        lyrics_divs = soup.find_all("div", {"data-lyrics-container": "true"})
        if lyrics_divs:
            lyrics = "\n".join([div.get_text(separator="\n").strip() for div in lyrics_divs])
        else:
            # Fallback to another lyrics API if Genius page parsing fails
            alt_url = f"https://api.lyrics.ovh/v1/{artist}/{title}" if artist else f"https://api.lyrics.ovh/v1/{title}"
            response = requests.get(alt_url, timeout=10)
            lyrics = response.json().get("lyrics", "Lyrics not found")
        if is_valid_lyrics(lyrics, title):
            return lyrics
        else:
            print(f"Genius returned invalid or unrelated lyrics for '{title}' by '{artist}'.")
            return None
    except Exception as e:
        print(f"Genius fetch error: {e}")
        return None


def add_metadata(file_path, title, artists, album, year, genre, thumbnail_url, isFromYoutube,otl,arti):
    try:
        try:
            audio = ID3(file_path)
        except Exception:
            audio = ID3()
        audio = ID3(file_path)
        audio.delete()
        artist_text = "; ".join(artists) if isinstance(artists, list) else artists
        print(artist_text)

        if artist_text != "Unknown Artist":
            if isFromYoutube:

              lyrics = fetch_lyrics(title, arti ,isFromYoutube)
            else:
              lyrics = fetch_lyrics(title, artists ,isFromYoutube)

        else:
            lyrics = fetch_lyrics(title,isFromYoutube)
        if lyrics:
            audio.add(USLT(
                encoding=Encoding.UTF8,
                lang='eng',
                desc='Lyrics',
                text=lyrics
            ))
            print(f"Added lyrics for: {title}")
        else:
            print(f"No valid lyrics found for: {title}")

        if isFromYoutube and not lyrics:
            audio.add(TIT2(encoding=Encoding.UTF8, text=otl))
            
            audio.add(TPE1(encoding=Encoding.UTF8, text=artist_text))
        elif isFromYoutube and lyrics:
            audio.add(TIT2(encoding=Encoding.UTF8, text=title))
            audio.add(TPE1(encoding=Encoding.UTF8, text=arti))
        else:
            audio.add(TIT2(encoding=Encoding.UTF8, text=title))
            audio.add(TPE1(encoding=Encoding.UTF8, text=artist_text))
            
            

        if album != "Unknown Album":
            audio.add(TALB(encoding=Encoding.UTF8, text=album))
            
        audio.add(TDRC(encoding=Encoding.UTF8, text=year))
        if genre != "Unknown Genre":
            audio.add(TCON(encoding=Encoding.UTF8, text=genre))
        
        if thumbnail_url:
            try:
                image_data = requests.get(thumbnail_url, timeout=10).content
                audio.add(APIC(
                    encoding=Encoding.UTF8,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=image_data
                ))
            except Exception as e:
                print(f"Thumbnail error: {e}")
        
        # Use LRCLib first if artist is known; otherwise, fallback to Genius.
        
        audio.save(file_path)
        print(f"Metadata added: {title} - {artist_text}")
    except Exception as e:
        print(title, artists, album, year, genre, file_path, thumbnail_url)
        print(f"Metadata error: {e}")

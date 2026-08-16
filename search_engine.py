import re
import requests
from urllib.parse import quote

SEARCH_URL = "https://www.jiosaavn.com/api.php?__call=autocomplete.get&_format=json&_marker=0&cc=in&includeMetaTags=1&query="

def _norm(value):
    value = str(value or "").lower()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def _tokens(value):
    return [x for x in _norm(value).split() if x]

def _artists(item):
    info = item.get("more_info") or {}
    if isinstance(info, str):
        m = re.search(r"primary_artists=([^;}]*)", info)
        return m.group(1).strip() if m else ""
    return (
        info.get("primary_artists")
        or info.get("singers")
        or item.get("primary_artists")
        or item.get("singers")
        or ""
    )

def _language(item):
    info = item.get("more_info") or {}
    if isinstance(info, str):
        m = re.search(r"language=([^;}]*)", info)
        return m.group(1).strip() if m else ""
    return info.get("language") or item.get("language") or ""

def _normalize_song(item):
    artists = _artists(item)
    return {
        "id": str(item.get("id") or ""),
        "song": str(item.get("title") or item.get("song") or ""),
        "title": str(item.get("title") or item.get("song") or ""),
        "album": str(item.get("album") or ""),
        "image": str(item.get("image") or ""),
        "url": str(item.get("url") or ""),
        "perma_url": str(item.get("url") or item.get("perma_url") or ""),
        "primary_artists": artists,
        "artist": artists,
        "singers": artists,
        "language": _language(item),
        "type": str(item.get("type") or "song"),
        "description": str(item.get("description") or ""),
        "source": "jiosaavn_autocomplete",
    }

def _score(item, query):
    q = _norm(query)
    qt = _tokens(query)

    title = _norm(item.get("title") or item.get("song"))
    artist = _norm(item.get("primary_artists") or item.get("artist") or item.get("singers"))
    album = _norm(item.get("album"))

    score = 0

    # Strongest signal: exact title.
    if title == q:
        score += 1000

    # Query contains complete title.
    if title and title in q:
        score += 500

    # Exact artist phrase.
    if artist and artist in q:
        score += 400

    # Artist tokens appearing in query.
    artist_tokens = _tokens(artist)
    artist_hits = sum(1 for token in artist_tokens if token in qt)
    score += artist_hits * 120

    # Title token coverage.
    title_tokens = _tokens(title)
    if title_tokens:
        title_hits = sum(1 for token in title_tokens if token in qt)
        score += int(350 * title_hits / len(title_tokens))

    # Query token coverage against title + artist.
    combined = f"{title} {artist}"
    if qt:
        hits = sum(1 for token in qt if token in combined)
        score += int(150 * hits / len(qt))

    # Album is weaker than title/artist.
    album_tokens = _tokens(album)
    score += sum(1 for token in album_tokens if token in qt) * 10

    return score

def search(query):
    query = str(query or "").strip()
    if not query:
        return []

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
    }

    url = SEARCH_URL + quote(query, safe="")
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    candidates = []

    # Main song results.
    songs = ((data.get("songs") or {}).get("data") or [])
    for item in songs:
        if isinstance(item, dict):
            candidates.append(item)

    # JioSaavn's highly relevant top query must also be included.
    topquery = ((data.get("topquery") or {}).get("data") or [])
    for item in topquery:
        if isinstance(item, dict) and item.get("type") == "song":
            candidates.append(item)

    # Dedupe by song id.
    unique = {}
    for item in candidates:
        sid = str(item.get("id") or "")
        if not sid:
            continue

        normalized = _normalize_song(item)

        # Only actual songs.
        if normalized["type"] not in ("song", ""):
            continue

        unique[sid] = normalized

    results = list(unique.values())

    for item in results:
        item["_score"] = _score(item, query)

    # Highest relevance first.
    results.sort(
        key=lambda x: (
            -x["_score"],
            -len(_tokens(x.get("primary_artists"))),
            x.get("title", "").lower(),
        )
    )

    for item in results:
        item.pop("_score", None)

    return results

import json
import re
from traceback import print_exc

import requests
import endpoints
import helper


def _get_json(response):
    response.raise_for_status()
    raw = response.text.lstrip('\ufeff')

    try:
        return response.json()
    except (ValueError, json.JSONDecodeError):
        pass

    cleaned = re.sub(
        r'\\\\?\(From "([^"]+)"\\\\?\)',
        r"(From '\1')",
        raw
    )

    try:
        return json.loads(cleaned)
    except (ValueError, json.JSONDecodeError):
        pass

    unicode_fixed = re.sub(
        r'\\u([0-9a-fA-F]{4})',
        lambda m: chr(int(m.group(1), 16)),
        cleaned
    )

    return json.loads(unicode_fixed)


def _get(url, **kwargs):
    headers = kwargs.pop("headers", None)

    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.jiosaavn.com/",
        }

    kwargs["headers"] = headers
    kwargs.setdefault("timeout", 20)

    return requests.get(url, **kwargs)


def _normalize(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text):
    return [x for x in _normalize(text).split() if len(x) > 1]


def _extract_search_songs(data):
    """
    Supports both old autocomplete.get and newer search.getResults
    response shapes.
    """

    candidates = []

    if not isinstance(data, dict):
        return candidates

    songs = data.get("songs")

    if isinstance(songs, dict):
        for key in ("results", "data"):
            value = songs.get(key)
            if isinstance(value, list):
                candidates.extend(value)

    for key in ("results", "data"):
        value = data.get(key)
        if isinstance(value, list):
            candidates.extend(value)

    return candidates


def _song_text(song):
    if not isinstance(song, dict):
        return ""

    parts = [
        song.get("title"),
        song.get("song"),
        song.get("album"),
        song.get("primary_artists"),
        song.get("singers"),
        song.get("music"),
        song.get("artist"),
    ]

    return " ".join(str(x or "") for x in parts)


def _score_song(song, query):
    """
    Generic relevance score.

    Higher score means the result better matches the user's
    title/artist query. This is intentionally generic and does
    not contain any song-specific rules.
    """

    q = _normalize(query)
    q_tokens = set(_tokens(query))

    if not q_tokens:
        return 0

    text = _normalize(_song_text(song))
    title = _normalize(song.get("title") or song.get("song") or "")
    artist = _normalize(
        song.get("primary_artists")
        or song.get("singers")
        or song.get("music")
        or ""
    )

    score = 0

    if q and q in text:
        score += 100

    if title and title in q:
        score += 80

    title_tokens = set(_tokens(title))
    artist_tokens = set(_tokens(artist))
    text_tokens = set(_tokens(text))

    score += len(q_tokens & title_tokens) * 30
    score += len(q_tokens & artist_tokens) * 25
    score += len(q_tokens & text_tokens) * 8

    if title_tokens and title_tokens.issubset(q_tokens):
        score += 60

    return score


def _search_once(query):
    query = str(query or "").strip()

    if not query:
        return []

    url = endpoints.search_base_url + requests.utils.quote(query)

    response = _get(url)
    data = _get_json(response)

    return _extract_search_songs(data)


def _build_query_variants(query):
    """
    Generate generic search variants.

    No song-specific hardcoding.
    """

    original = str(query or "").strip()

    if not original:
        return []

    normalized = re.sub(r"\s+", " ", original)

    variants = [normalized]

    tokens = _tokens(normalized)

    if len(tokens) > 2:
        # Full title-oriented query.
        # Useful when the user types: title + artist.
        variants.append(" ".join(tokens[:2]))

        # Artist/title alternate ordering.
        variants.append(" ".join(tokens[2:] + tokens[:2]))

        # Remove likely filler words.
        filler = {
            "song",
            "songs",
            "music",
            "track",
            "audio",
            "official",
            "video",
            "full",
        }

        filtered = [x for x in tokens if x not in filler]

        if filtered:
            variants.append(" ".join(filtered))

    elif len(tokens) == 2:
        variants.append(tokens[0])
        variants.append(tokens[1])

    # Preserve order and remove duplicates.
    result = []

    for value in variants:
        value = value.strip()

        if value and value not in result:
            result.append(value)

    return result


def _collect_search_results(query):
    """
    Multi-pass generic JioSaavn search.

    We query several normalized variants, merge the result sets,
    deduplicate by song ID, then rank by relevance.
    """

    all_songs = []
    seen_ids = set()

    variants = _build_query_variants(query)

    for variant in variants:
        try:
            results = _search_once(variant)

            for song in results:
                if not isinstance(song, dict):
                    continue

                song_id = str(
                    song.get("id")
                    or song.get("songid")
                    or song.get("e_songid")
                    or ""
                ).strip()

                if not song_id:
                    continue

                if song_id in seen_ids:
                    continue

                seen_ids.add(song_id)
                all_songs.append(song)

        except Exception:
            print_exc()

    all_songs.sort(
        key=lambda song: _score_song(song, query),
        reverse=True
    )

    return all_songs


def search_for_song(query, lyrics, songdata):
    query = str(query or "").strip()

    if not query:
        return []

    if query.startswith("http") and "saavn.com" in query:
        song_id = get_song_id(query)
        return get_song(song_id, lyrics)

    song_response = _collect_search_results(query)

    if not songdata:
        return song_response

    songs = []

    for song in song_response:
        song_id = (
            song.get("id")
            or song.get("songid")
            or song.get("e_songid")
        )

        if not song_id:
            continue

        song_data = get_song(song_id, lyrics)

        if song_data:
            songs.append(song_data)

    return songs


def get_song(song_id, lyrics):
    try:
        url = endpoints.song_details_base_url + str(song_id)
        data = _get_json(_get(url))

        song_data = data.get(str(song_id))

        if not song_data:
            return None

        formatted = helper.format_song(song_data, lyrics)

        return formatted if formatted else None

    except Exception:
        return None


def get_song_id(url):
    res = _get(url)

    try:
        return res.text.split('"pid":"')[1].split('","')[0]
    except IndexError:
        return (
            res.text
            .split('"song":{"type":"')[1]
            .split('","image":')[0]
            .split('"id":"')[-1]
        )


def get_album(album_id, lyrics):
    try:
        response = _get(
            endpoints.album_details_base_url + str(album_id)
        )

        return (
            helper.format_album(_get_json(response), lyrics)
            if response.ok
            else None
        )

    except Exception as exc:
        print(exc)
        return None


def get_album_id(input_url):
    res = _get(input_url)

    try:
        return res.text.split('"album_id":"')[1].split('"')[0]
    except IndexError:
        return res.text.split('"page_id","')[1].split('","')[0]


def get_playlist(list_id, lyrics):
    try:
        response = _get(
            endpoints.playlist_details_base_url + str(list_id)
        )

        return (
            helper.format_playlist(_get_json(response), lyrics)
            if response.ok
            else None
        )

    except Exception:
        print_exc()
        return None


def get_playlist_id(input_url):
    res = _get(input_url).text

    try:
        return res.split('"type":"playlist","id":"')[1].split('"')[0]
    except IndexError:
        return res.split('"page_id","')[1].split('","')[0]


def get_lyrics(song_id):
    url = endpoints.lyrics_base_url + str(song_id)
    lyrics_text = _get_json(_get(url))
    return lyrics_text["lyrics"]

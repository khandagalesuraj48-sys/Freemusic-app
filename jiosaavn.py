import json
import re
from traceback import print_exc

import requests
import endpoints
import helper


def _get_json(response):
    """Parse JioSaavn JSON without the legacy unicode-escape corruption step."""
    response.raise_for_status()
    raw = response.text.lstrip('\ufeff')

    # Normal JSON first. This preserves \uXXXX escapes correctly.
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError):
        pass

    # JioSaavn has historically returned strings containing literal
    # \(From \"Artist\"\) fragments. Convert only that known fragment.
    cleaned = re.sub(r'\\\\?\(From "([^"]+)"\\\\?\)', r"(From '\1')", raw)
    try:
        return json.loads(cleaned)
    except (ValueError, json.JSONDecodeError):
        pass

    # Last compatibility attempt: decode only escaped unicode, while keeping
    # JSON structural escaping intact. Do not use unicode-escape globally.
    unicode_fixed = re.sub(
        r'\\u([0-9a-fA-F]{4})',
        lambda m: chr(int(m.group(1), 16)),
        cleaned,
    )
    return json.loads(unicode_fixed)


def _get(url, **kwargs):
    kwargs.setdefault('headers', {'User-Agent': 'Mozilla/5.0'})
    kwargs.setdefault('timeout', 20)
    return requests.get(url, **kwargs)


def search_for_song(query, lyrics, songdata):
    if query.startswith('http') and 'saavn.com' in query:
        song_id = get_song_id(query)
        return get_song(song_id, lyrics)

    search_base_url = endpoints.search_base_url + query
    response = _get(search_base_url)
    data = _get_json(response)
    song_response = data.get('songs', {}).get('data', [])

    if not songdata:
        return song_response

    songs = []
    for song in song_response:
        song_id = song.get('id')
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
        song_data = helper.format_song(data[str(song_id)], lyrics)
        return song_data if song_data else None
    except Exception:
        return None


def get_song_id(url):
    res = _get(url)
    try:
        return res.text.split('"pid":"')[1].split('","')[0]
    except IndexError:
        return res.text.split('"song":{"type":"')[1].split('","image":')[0].split('"id":"')[-1]


def get_album(album_id, lyrics):
    try:
        response = _get(endpoints.album_details_base_url + str(album_id))
        return helper.format_album(_get_json(response), lyrics) if response.ok else None
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
        response = _get(endpoints.playlist_details_base_url + str(list_id))
        return helper.format_playlist(_get_json(response), lyrics) if response.ok else None
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
    return lyrics_text['lyrics']

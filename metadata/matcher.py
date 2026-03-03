import os
import re

from rapidfuzz import fuzz
from mutagen import File as MutagenFile

_TITLE_CLEAN_RE = re.compile(
    r"\s*[\(\[\{][^)\]\}]*?(official|music video|video|lyric|audio|visualizer|full video|hd|4k)[^)\]\}]*?[\)\]\}]\s*",
    re.IGNORECASE,
)
_TITLE_TRAIL_RE = re.compile(
    r"\s*-\s*(official|music video|video|lyric|audio|visualizer|full video).*$",
    re.IGNORECASE,
)
_VEVO_SUFFIX_RE = re.compile(r"(vevo)$", re.IGNORECASE)


def parse_source(meta, file_path):
    title = _clean_title((meta or {}).get("title") or "")
    artist = _clean_artist((meta or {}).get("artist") or "")
    album = _clean_title((meta or {}).get("album") or "")
    source_title = title or os.path.splitext(os.path.basename(file_path))[0]

    if not artist and " - " in source_title:
        parts = source_title.split(" - ", 1)
        artist = _clean_artist(parts[0].strip())
        title = _clean_title(parts[1].strip()) if len(parts) > 1 else title
    if not title:
        title = _clean_title(source_title)

    return {
        "artist": artist.strip() if artist else "",
        "title": title.strip() if title else "",
        "album": album.strip() if album else "",
        "source_title": source_title,
    }


def get_duration_seconds(file_path):
    try:
        audio = MutagenFile(file_path)
        if audio and audio.info and audio.info.length:
            return int(round(audio.info.length))
    except Exception:
        return None
    return None


def merge_candidates(existing, extra):
    by_id = {}
    for item in existing or []:
        key = item.get("recording_id") or id(item)
        by_id[key] = item
    for item in extra or []:
        key = item.get("recording_id") or id(item)
        if key not in by_id:
            by_id[key] = item
    return list(by_id.values())


def select_best_match(source, candidates, duration):
    best = None
    best_score = 0.0
    best_breakdown = {}
    for candidate in candidates or []:
        breakdown = score_match(source, candidate, duration)
        score = float(breakdown.get("total_score") or 0.0)
        if score > best_score:
            best = candidate
            best_score = score
            best_breakdown = breakdown
    return best, int(round(best_score)), best_breakdown


def score_match(source, candidate, duration):
    source_artist = source.get("artist")
    source_title = source.get("title")
    source_album = source.get("album")

    candidate_artist = candidate.get("artist")
    candidate_title = candidate.get("track") or candidate.get("title")
    candidate_album = candidate.get("album")

    artist_score = _fuzzy_score(source_artist, candidate_artist)
    title_score = _fuzzy_score(source_title, candidate_title)
    album_score = _fuzzy_score(source_album, candidate_album) if source_album else 0

    # Per-field weighted points (0-100 total):
    # - artist: 45
    # - track/title: 40
    # - album: 10
    # - duration: 5
    artist_points = (artist_score / 100.0) * 45.0 if source_artist else 0.0
    title_points = (title_score / 100.0) * 40.0 if source_title else 0.0
    album_points = (album_score / 100.0) * 10.0 if source_album else 0.0

    duration_points = 0.0
    duration_score = 0
    if duration and candidate.get("duration"):
        try:
            cand_duration = int(round(candidate["duration"]))
        except Exception:
            cand_duration = None
        if cand_duration is not None:
            diff = abs(cand_duration - duration)
            if diff <= 2:
                duration_points = 5.0
                duration_score = 100
            elif diff <= 5:
                duration_points = 2.5
                duration_score = 50

    total_score = artist_points + title_points + album_points + duration_points
    return {
        "artist_score": int(round(artist_score)),
        "track_score": int(round(title_score)),
        "album_score": int(round(album_score)),
        "duration_score": int(round(duration_score)),
        "artist_points": artist_points,
        "track_points": title_points,
        "album_points": album_points,
        "duration_points": duration_points,
        "total_score": total_score,
    }


def _fuzzy_score(left, right):
    if not left or not right:
        return 0
    return int(fuzz.token_set_ratio(left, right))


def _clean_title(value):
    if not value:
        return ""
    cleaned = _TITLE_CLEAN_RE.sub(" ", value)
    cleaned = _TITLE_TRAIL_RE.sub("", cleaned)
    return " ".join(cleaned.split())


def _clean_artist(value):
    if not value:
        return ""
    cleaned = value.strip()
    if cleaned.startswith("@"):
        cleaned = cleaned.lstrip("@").strip()
    cleaned = _VEVO_SUFFIX_RE.sub("", cleaned).strip()
    return cleaned

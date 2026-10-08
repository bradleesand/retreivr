import re
from pathlib import Path

from yt_dlp import YoutubeDL

_JOB_QUEUE = (Path(__file__).resolve().parents[1] / "engine" / "job_queue.py").read_text(encoding="utf-8")

# Filesystems limit filenames to 255 *bytes* (ext4), not characters. Leave room for the
# longest sidecar/intermediate suffix yt-dlp adds, e.g. ".f2567784650351946v.mp4" or ".info.json".
_NAME_MAX_BYTES = 255
_SUFFIX_HEADROOM_BYTES = 30

# Worst case: every character is multibyte (3 bytes for CJK / fullwidth "｜", 2 for "·").
_INFO = {
    "id": "1631661805240892",
    "ext": "mp4",
    "title": "348K views · 308K reactions ｜ " + "あ" * 300 + " ｜ Rebuild Different",
    "uploader": "é" * 200,
}


def _title_templates():
    return re.findall(r'"([^"\n]*%\(title\)\.\d+[sB][^"\n]*)"', _JOB_QUEUE)


def test_title_templates_are_found() -> None:
    # Guard against the regex silently matching nothing if the templates are reworded.
    assert len(_title_templates()) >= 4


def test_title_templates_truncate_by_bytes() -> None:
    for template in _title_templates():
        assert re.search(r"%\(title\)\.\d+B", template), f"character-based title cap: {template}"
        assert not re.search(r"%\((?:title|uploader)\)\.\d+s", template), template


def test_rendered_filenames_fit_the_filesystem_limit() -> None:
    for template in _title_templates():
        name = YoutubeDL({"outtmpl": template, "quiet": True}).prepare_filename(_INFO)
        size = len(Path(name).name.encode("utf-8"))
        assert size + _SUFFIX_HEADROOM_BYTES <= _NAME_MAX_BYTES, (template, size)


def test_character_based_template_would_overflow() -> None:
    # Documents the bug: the old character cap is not safe for multibyte titles.
    old = "%(title).200s - %(uploader).120s - %(id)s.%(ext)s"
    name = YoutubeDL({"outtmpl": old, "quiet": True}).prepare_filename(_INFO)
    assert len(Path(name).name.encode("utf-8")) > _NAME_MAX_BYTES

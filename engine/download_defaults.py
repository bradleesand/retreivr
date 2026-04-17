from __future__ import annotations


def normalize_download_media_mode(
    media_mode: str | None = None,
    *,
    media_type: str | None = None,
    music_mode: bool | None = None,
) -> str:
    normalized = str(media_mode or "").strip().lower()
    if normalized in {"video", "music", "music_video"}:
        return normalized
    if bool(music_mode):
        return "music"
    normalized_type = str(media_type or "").strip().lower()
    if normalized_type in {"music", "audio"}:
        return "music"
    return "video"


def resolve_effective_download_settings(
    config: dict | None,
    *,
    media_mode: str | None = None,
    media_type: str | None = None,
    music_mode: bool | None = None,
    destination: str | None = None,
    final_format_override: str | None = None,
    fallback_destination: str = ".",
    fallback_video_format: str = "mkv",
    fallback_music_format: str = "mp3",
) -> dict[str, str]:
    cfg = config if isinstance(config, dict) else {}
    normalized_mode = normalize_download_media_mode(
        media_mode,
        media_type=media_type,
        music_mode=music_mode,
    )
    explicit_destination = str(destination or "").strip()
    explicit_final_format = str(final_format_override or "").strip()

    if normalized_mode == "music":
        resolved_destination = (
            explicit_destination
            or str(
                cfg.get("home_music_download_folder")
                or cfg.get("music_download_folder")
                or cfg.get("single_download_folder")
                or fallback_destination
            ).strip()
        )
        resolved_final_format = (
            explicit_final_format
            or str(
                cfg.get("home_music_final_format")
                or cfg.get("music_final_format")
                or cfg.get("audio_final_format")
                or fallback_music_format
            ).strip()
        )
    elif normalized_mode == "music_video":
        resolved_destination = (
            explicit_destination
            or str(
                cfg.get("home_music_video_download_folder")
                or cfg.get("single_download_folder")
                or fallback_destination
            ).strip()
        )
        resolved_final_format = (
            explicit_final_format
            or str(
                cfg.get("home_music_video_final_format")
                or cfg.get("final_format")
                or cfg.get("video_final_format")
                or fallback_video_format
            ).strip()
        )
    else:
        resolved_destination = (
            explicit_destination
            or str(
                cfg.get("single_download_folder")
                or fallback_destination
            ).strip()
        )
        resolved_final_format = (
            explicit_final_format
            or str(
                cfg.get("final_format")
                or cfg.get("video_final_format")
                or fallback_video_format
            ).strip()
        )

    return {
        "media_mode": normalized_mode,
        "destination": resolved_destination or fallback_destination,
        "final_format": resolved_final_format or (
            fallback_music_format if normalized_mode == "music" else fallback_video_format
        ),
    }

"""Shared configuration constants for CLI and GUI."""

VIDEO_QUALITIES = {
    "Best": "best",
    "1080p": "1080",
    "720p": "720",
    "480p": "480",
}

VIDEO_QUALITY_LABELS_CLI = {
    "1": "best",
    "2": "1080",
    "3": "720",
    "4": "480",
}

AUDIO_QUALITIES = {
    "Best (320kbps)": "best",
    "256kbps": "256",
    "192kbps": "192",
    "128kbps": "128",
    "96kbps": "96",
    "64kbps": "64",
}

AUDIO_QUALITY_LABELS_CLI = {
    "1": "best",
    "2": "256",
    "3": "192",
    "4": "128",
    "5": "96",
    "6": "64",
}

AUDIO_CODECS = {
    "AAC (m4a)": "aac",
    "MP3": "mp3",
    "OPUS": "opus",
    "FLAC (lossless)": "flac",
    "Vorbis (ogg)": "vorbis",
}

AUDIO_CODEC_LABELS_CLI = {
    "1": "aac",
    "2": "mp3",
    "3": "opus",
    "4": "flac",
    "5": "vorbis",
}

DEFAULT_MAX_CONCURRENT_DOWNLOADS = 3
DELAY_BETWEEN_DOWNLOADS = 1.5

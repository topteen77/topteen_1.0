"""Local psychometric report graph image paths and URL helpers."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from django.conf import settings

_GRAPH_TYPES = frozenset({'personality', 'interest', 'intelligence'})


def sanitize_graph_user_name(user_name: str) -> str:
    """Normalize display name for graph filenames (spaces → underscores)."""
    return ' '.join(str(user_name or '').split()).replace(' ', '_')


def graph_images_directory() -> Path:
    """Directory under MEDIA_ROOT where matplotlib graphs are stored."""
    directory = Path(settings.MEDIA_ROOT) / 'graph_images'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def graph_image_filename(user_name: str, user_id: int | str, chart_type: str) -> str:
    """Filesystem basename for a user's assessment chart PNG."""
    if chart_type not in _GRAPH_TYPES:
        raise ValueError(f'chart_type must be one of {sorted(_GRAPH_TYPES)}')
    safe_name = sanitize_graph_user_name(user_name)
    return f'{safe_name}-{user_id}_{chart_type}_Assessment.png'


def graph_image_path(user_name: str, user_id: int | str, chart_type: str) -> str:
    """Absolute filesystem path for a graph PNG."""
    return os.path.join(
        graph_images_directory(),
        graph_image_filename(user_name, user_id, chart_type),
    )


def graph_image_media_url(user_name: str, user_id: int | str, chart_type: str) -> str:
    """Browser URL for a graph PNG (encodes any remaining special characters)."""
    filename = graph_image_filename(user_name, user_id, chart_type)
    encoded_name = quote(filename, safe='-_.')
    return f'/media/graph_images/{encoded_name}'


def graph_image_basenames(user_name: str, user_id: int | str) -> list[str]:
    """All three chart filenames for existence checks."""
    return [
        graph_image_filename(user_name, user_id, chart_type)
        for chart_type in ('personality', 'interest', 'intelligence')
    ]

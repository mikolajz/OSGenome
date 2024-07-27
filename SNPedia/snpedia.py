import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from dataclasses_json import DataClassJsonMixin

from data_types import Rsid

RSID_REGEXP = re.compile(r'^[a-zA-Z][a-zA-Z0-9]*$')


@dataclass(frozen=True)
class _CacheMetadata(DataClassJsonMixin):
    http_response: int
    last_modified: Optional[str]
    timestamp: float


class SnpediaWithCache:
    def __init__(self, data_dir: Path) -> None:
        self._snpedia_cache_dir = data_dir / "snpedia_cache"

    def _data_and_meta_paths(self, rsid: Rsid) -> tuple[Path, Path]:
        assert RSID_REGEXP.match(rsid)
        return (
            self._snpedia_cache_dir / f"{rsid}.html",
            self._snpedia_cache_dir / f"{rsid}.meta",
        )

    def load_rsid(self, rsid: Rsid, session: requests.Session) -> Optional[bytes]:
        url = f"https://bots.snpedia.com/index.php/{rsid}"

        try:
            response = session.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            print(f"{url} was not found or contained no valid information")
            return None

        html = response.content

        cache_metadata = _CacheMetadata(
            http_response=response.status_code,  # May be useful for debugging.
            last_modified=response.headers.get("Last-Modified"),
            timestamp=time.time()
        )

        self._snpedia_cache_dir.mkdir(exist_ok=True)
        data_path, meta_path = self._data_and_meta_paths(rsid)
        data_path.write_bytes(html)
        meta_path.write_text(cache_metadata.to_json())

        return html

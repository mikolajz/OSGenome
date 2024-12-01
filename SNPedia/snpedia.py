from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Mapping

import requests
from bs4 import BeautifulSoup, Tag
from dataclasses_json import DataClassJsonMixin

from data_types import Rsid, Orientation, ReferenceBuild
from genotype import Genotype

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
        if (cached_html := self.get_from_cache(rsid)) is not None:
            return cached_html

        url = f"https://bots.snpedia.com/index.php/{rsid}"

        try:
            response = session.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.warning(f"{url} was not found or contained no valid information ({e})")
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

    def get_from_cache(self, rsid: Rsid) -> Optional[bytes]:
        data_path, meta_path = self._data_and_meta_paths(rsid)
        if not data_path.exists():
            return None

        html = data_path.read_bytes()
        if not html:
            return None

        return html


@dataclass(frozen=True)
class GenotypeSummary(DataClassJsonMixin):
    genotype_str: Genotype
    magnitude: Optional[float]
    description: Optional[str]


@dataclass(frozen=True)
class SnpediaSnpInfo:
    description: Optional[str]
    genotype_summaries: list[GenotypeSummary]
    stabilized_orientation: Optional[Orientation]
    orientation: Optional[Orientation]
    reference_build: Optional[str]

    def get_reference_build(self) -> ReferenceBuild:
        our_build = self.reference_build
        if our_build is None:
            return ReferenceBuild.BUILD38  # Reasonable default?

        for build in ReferenceBuild:
            # See snpedia_name docstring for why we use startswith.
            if our_build.startswith(build.value.snpedia_name):
                return build

        return ReferenceBuild.BUILD38


class SnpPage:

    DATA_FORMAT_VERSION = 3  # Bump by 1 each time the format of rsidList.json changes.

    def __init__(self, html: bytes):
        self._html = html

    def parse(self) -> SnpediaSnpInfo:
        bs = BeautifulSoup(self._html, "html.parser")

        return SnpediaSnpInfo(
            description=self._find_description(bs),
            genotype_summaries=self._find_genotype_summaries(bs),
            stabilized_orientation=self._find_stable_orientation(bs),
            orientation=self._find_orientation(bs),
            reference_build=self._find_reference_build(bs),
        )

    def _find_stable_orientation(self, bs: BeautifulSoup) -> Optional[Orientation]:
        # Orientation Finder
        orientation = bs.find("td", string="Rs_StabilizedOrientation")
        if orientation is not None and orientation.parent is not None:
            plus = orientation.parent.find("td", string="plus")
            minus = orientation.parent.find("td", string="minus")

            if plus:
                return Orientation.PLUS
            if minus:
                return Orientation.MINUS

        link = bs.find("a", {"title": "StabilizedOrientation"})
        if link is not None and link.parent is not None and link.parent.parent is not None:
            table_row = link.parent.parent
            plus = table_row.find("td", string="plus")
            minus = table_row.find("td", string="minus")
            if plus:
                return Orientation.PLUS
            if minus:
                return Orientation.MINUS

        return None

    def _find_orientation(self, bs: BeautifulSoup) -> Optional[Orientation]:
        link = bs.find("a", {"title": "Orientation"})
        if link is not None and link.parent is not None and link.parent.parent is not None:
            table_row = link.parent.parent
            plus = table_row.find("td", string="plus")
            minus = table_row.find("td", string="minus")
            if plus:
                return Orientation.PLUS
            if minus:
                return Orientation.MINUS

        return None

    def _find_reference_build(self, bs: BeautifulSoup) -> Optional[str]:
        cell = bs.find("td", string="Reference")
        if cell is not None and cell.parent is not None:
            table_row = cell.parent
            if (a_elem := table_row.find("a")) is not None:
                assert isinstance(a_elem, Tag)
                return str(a_elem.string)

        return None

    def _find_description(self, bs: BeautifulSoup) -> Optional[str]:
        description_element = bs.find(
            'table',
            {'style': 'border: 1px; background-color: #FFFFC0; border-style: solid; margin:1em; width:90%;'},
        )
        if description_element:
            d1 = self._table_to_list(description_element)
            result = d1[0][0]
            return result

        return None

    def _find_genotype_summaries(self, bs: BeautifulSoup) -> list[GenotypeSummary]:
        table = bs.find("table", {"class": "sortable smwtable"})
        if table:
            d2 = self._table_to_list(table)
            genotype_summaries = [
                GenotypeSummary(
                    genotype_str=Genotype.from_string(row[0]),
                    magnitude=float(row[1]) if row[1] else None,
                    description=row[2],
                )
                for row in d2[1:]
            ]
            return genotype_summaries

        return []

    def _table_to_list(self, table) -> list[list[str]]:
        rows = table.find_all('tr')
        data = []
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            data.append(cols)
        return data


@dataclass
class _ParsedSnpsFileContents(DataClassJsonMixin):
    version: int
    snps: dict[Rsid, SnpediaSnpInfo]


class ParsedSnpsStorage:

    def __init__(
            self,
            contents: _ParsedSnpsFileContents,
            file_path: Path,
    ):
        self._contents = contents
        self._file_path = file_path

    @staticmethod
    def load(data_dir: Path, snpedia: SnpediaWithCache) -> "ParsedSnpsStorage":
        file_path = data_dir / "rsidDict.json"
        contents = json.loads(file_path.read_bytes())

        version = contents.get("version", 0)
        if version == SnpPage.DATA_FORMAT_VERSION:
            return ParsedSnpsStorage(
                contents=_ParsedSnpsFileContents.from_dict(contents),
                file_path=file_path,
            )

        new_version = SnpPage.DATA_FORMAT_VERSION
        print(f"{file_path} uses old format version {version}. Upgrading to {new_version}.")
        new_snps = {}
        for rsid in contents.get("snps", {}).keys():
            html = snpedia.get_from_cache(rsid)

            if html is None:
                continue

            new_snps[rsid] = SnpPage(html).parse()

        result = ParsedSnpsStorage(
            contents=_ParsedSnpsFileContents(
                version=new_version,
                snps=new_snps,
            ),
            file_path=file_path,
        )
        result.export()
        print("Upgrade complete.")

        return result

    def export(self) -> None:
        self._file_path.write_text(self._contents.to_json())

    def snp_infos(self) -> Mapping[Rsid, SnpediaSnpInfo]:
        return self._contents.snps

    def set_snp(self, rsid: Rsid, info: SnpediaSnpInfo) -> None:
        self._contents.snps[rsid] = info

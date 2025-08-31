from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dataclasses_json import DataClassJsonMixin

from base.data_types import Rsid
from snpedia.snp_page import SnpPage, SnpediaSnpInfo
from snpedia.snpedia_with_cache import SnpediaWithCache


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

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Optional

from base.chromosome import Location
from base.data_types import Rsid, ReferenceBuild
from base.genotype import Genotype
from inputs.formats import InputRecord


class PersonalData:

    _SNPDICT_META_BUILD_KEY = Rsid("__meta__build__")
    _FILE_VERSION = 2

    def __init__(self, snpdict: Mapping[Rsid, InputRecord], reference_build: ReferenceBuild) -> None:
        self.snpdict = snpdict
        self.snps = list(snpdict.keys())
        self._reference_build = reference_build

    @staticmethod
    def from_input_file(filepath: Path, format_hint: Optional[str], approved) -> PersonalData:
        from inputs.formats import create_reader
        data_input = create_reader(filepath, format_hint)
        accepted_set = set(approved.accepted)
        snpdict = {input_record.rsid: input_record for input_record in data_input.read(accepted_set)}
        build = data_input.get_reference_build()

        return PersonalData(snpdict, build)

    @staticmethod
    def from_cache(data_dir: Path) -> PersonalData:
        with PersonalData._get_file_path(data_dir).open("r") as jsonfile:
            file_contents = json.load(jsonfile)

        if (version := file_contents.get("version")) != PersonalData._FILE_VERSION:
            raise RuntimeError(f"Old version of cache file ({version}). Please rerun DataCrawler.py")

        build_name = file_contents["build"]
        build = ReferenceBuild[build_name]

        return PersonalData(
            {snp["rsid"]: InputRecord(**snp) for snp in file_contents["snps"]},
            build,
        )

    def get_reference_build(self) -> ReferenceBuild:
        return self._reference_build

    def export(self, data_dir: Path) -> None:
        with self._get_file_path(data_dir).open("w") as jsonfile:
            json.dump({
                "version": self._FILE_VERSION,
                "build": self._reference_build.name,
                "snps": [asdict(value) for value in self.snpdict.values()]
            }, jsonfile)

    def has_genotype(self, rsid) -> bool:
        input_record = self.snpdict.get(rsid)
        return input_record is not None and not input_record == "(-;-)"

    def get_genotype(self, rsid: Rsid) -> Genotype:
        return Genotype.from_string(self.snpdict[rsid].genotype)

    def get_genotype_and_location(self, rsid: Rsid) -> tuple[Genotype, Location]:
        input_record = self.snpdict[rsid]
        return Genotype.from_string(input_record.genotype), input_record.get_location()

    @staticmethod
    def _get_file_path(data_dir: Path) -> Path:
        return data_dir / "snpDict.json"

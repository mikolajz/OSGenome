from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, List, Optional

import requests

from data_types import Rsid, ReferenceBuild
from genotype import Genotype
from inputs.formats import InputFormat, create_reader
from utils import get_default_data_dir


class PersonalData:

    _SNPDICT_META_BUILD_KEY = Rsid("__meta__build__")

    def __init__(self, snpdict: Mapping[Rsid, str], reference_build: ReferenceBuild) -> None:
        self.snpdict = snpdict
        self.snps = list(snpdict.keys())
        self._reference_build = reference_build

    @staticmethod
    def from_input_file(filepath: Path, format_hint: Optional[str], approved: Approved) -> PersonalData:
        data_input = create_reader(filepath, format_hint)
        accepted_set = set(approved.accepted)
        snpdict = {rsid: genotype for rsid, genotype in data_input.read(accepted_set)}
        build = data_input.get_reference_build()

        snpdict[PersonalData._SNPDICT_META_BUILD_KEY] = build.name
        return PersonalData(snpdict, build)

    @staticmethod
    def from_cache(data_dir: Path) -> PersonalData:
        with PersonalData._get_file_path(data_dir).open("r") as jsonfile:
            snpdict = json.load(jsonfile)

        try:
            build_name = snpdict[PersonalData._SNPDICT_META_BUILD_KEY]
        except KeyError:
            raise RuntimeError("Old version of cache file. Please rerun DataCrawler.py")
        build = ReferenceBuild[build_name]

        return PersonalData(snpdict, build)

    def get_reference_build(self) -> ReferenceBuild:
        return self._reference_build

    def export(self, data_dir: Path) -> None:
        with self._get_file_path(data_dir).open("w") as jsonfile:
            json.dump(self.snpdict, jsonfile)

    def has_genotype(self, rsid) -> bool:
        if rsid == self._SNPDICT_META_BUILD_KEY:
            return False
        genotype = self.snpdict.get(rsid)
        return genotype is not None and not genotype == "(-;-)"

    def get_genotype(self, rsid: Rsid) -> Genotype:
        if rsid == self._SNPDICT_META_BUILD_KEY:
            raise KeyError(rsid)
        return Genotype.from_string(self.snpdict[rsid])

    @staticmethod
    def _get_file_path(data_dir: Path) -> Path:
        return data_dir / "snpDict.json"


class Approved:
    def __init__(self, data_dir: Path) -> None:
        self._file_path = data_dir / 'approved.json'
        if not self._file_path.is_file():
            self.accepted = self._crawl()
            self.export()
        else:
            self.accepted = self._load(self._file_path)

    @staticmethod
    def _load(file_path: Path) -> List[Rsid]:
        with file_path.open("r") as f:
            return json.load(f)

    @staticmethod
    def _crawl(cmcontinue=None) -> List[Rsid]:
        count = 0
        accepted = []
        print("Grabbing approved SNPs")
        if not cmcontinue:
            curgen = "https://bots.snpedia.com/api.php?action=query&list=categorymembers&cmtitle=Category:Is_a_snp&cmlimit=500&format=json"
            response = requests.get(curgen)
            jd = response.json()

            cur = jd["query"]["categorymembers"]
            for item in cur:
                accepted += [Rsid(item["title"].lower())]
            cmcontinue = jd["continue"]["cmcontinue"]

        while cmcontinue:
            curgen = "https://bots.snpedia.com/api.php?action=query&list=categorymembers&cmtitle=Category:Is_a_snp&cmlimit=500&format=json&cmcontinue=" \
                    + cmcontinue
            response = requests.get(curgen)
            jd = response.json()
            cur = jd["query"]["categorymembers"]
            for item in cur:
                accepted += [Rsid(item["title"].lower())]
            try:
                cmcontinue = jd["continue"]["cmcontinue"]
            except KeyError:
                cmcontinue = None
            count += 1

        return accepted

    def export(self):
        with self._file_path.open("w") as jsonfile:
            json.dump(self.accepted, jsonfile)

#https://bots.snpedia.com/api.php?action=query&list=categorymembers&cmtitle=Category:Is_a_snp&cmlimit=500&format=json


if __name__ == "__main__":

    

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--filepath', help='Filepath for json dump to be used for import', required=False)

    args = vars(parser.parse_args())

    if args["filepath"]:
        data_dir = get_default_data_dir()
        rsids_on_snpedia = Approved(data_dir=data_dir)
        pd = PersonalData.from_input_file(filepath=args["filepath"], format_hint=None, approved=rsids_on_snpedia)
        print(pd.snps[:50])
        print(list(pd.snpdict.keys())[:10])
        print(list(pd.snpdict.values())[:10])

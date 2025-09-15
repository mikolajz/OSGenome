from __future__ import annotations

import json
from pathlib import Path
from typing import List

import requests

from base.data_types import Rsid


class SnpediaIndex:
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
        self._file_path.parent.mkdir(exist_ok=True, parents=True)
        with self._file_path.open("w") as jsonfile:
            json.dump(self.accepted, jsonfile)

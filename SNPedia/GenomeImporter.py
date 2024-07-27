from __future__ import annotations

import argparse
import os
import string
import json
from pathlib import Path
from typing import Mapping, List

import requests
import pprint

from data_types import Rsid
from utils import get_default_data_dir


class PersonalData:
    def __init__(self, snpdict: Mapping[Rsid, str]) -> None:
        self.snpdict = snpdict
        self.snps = list(snpdict.keys())

    @staticmethod
    def from_input_file(filepath: Path, approved: Approved) -> PersonalData:
        with open(filepath) as file:
            relevant_data = [line for line in file.readlines() if line[0] != "#"]
            file.close()

        accepted_set = set(approved.accepted)
        personaldata = [line.split("\t") for line in relevant_data]
        filtered_personal_data = [pd for pd in personaldata if pd[0].lower() in accepted_set]
        print(f"{len(filtered_personal_data)}/{len(personaldata)} SNPs from personal data present also in SNPedia.")
        
        snpdict = {Rsid(item[0].lower()): "(" + item[3].rstrip()[0] + ";" + item[3].rstrip()[-1] + ")"
                   for item in filtered_personal_data}

        return PersonalData(snpdict)

    @staticmethod
    def from_cache(data_dir: Path) -> PersonalData:
        with PersonalData._get_file_path(data_dir).open("r") as jsonfile:
            snpdict = json.load(jsonfile)

        return PersonalData(snpdict)

    def export(self, data_dir: Path) -> None:
        with self._get_file_path(data_dir).open("w") as jsonfile:
            json.dump(self.snpdict, jsonfile)

    def has_genotype(self, rsid) -> bool:
        genotype = self.snpdict.get(rsid)
        return genotype is not None and not genotype == "(-;-)"

    def get_genotype(self, rsid: Rsid) -> str:
        return self.snpdict.get(rsid, "(-;-)")

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
    def _load(file_path: Path) -> List[str]:
        with file_path.open("r") as f:
            return json.load(f)

    @staticmethod
    def _crawl(cmcontinue=None) -> List[str]:
        count = 0
        accepted = []
        print("Grabbing approved SNPs")
        if not cmcontinue:
            curgen = "https://bots.snpedia.com/api.php?action=query&list=categorymembers&cmtitle=Category:Is_a_snp&cmlimit=500&format=json"
            response = requests.get(curgen)
            jd = response.json()

            cur = jd["query"]["categorymembers"]
            for item in cur:
                accepted += [item["title"].lower()]
            cmcontinue = jd["continue"]["cmcontinue"]

        while cmcontinue:
            curgen = "https://bots.snpedia.com/api.php?action=query&list=categorymembers&cmtitle=Category:Is_a_snp&cmlimit=500&format=json&cmcontinue=" \
                    + cmcontinue
            response = requests.get(curgen)
            jd = response.json()
            cur = jd["query"]["categorymembers"]
            for item in cur:
                accepted += [item["title"].lower()]
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
        pd = PersonalData.from_input_file(filepath=args["filepath"], approved=rsids_on_snpedia)
        print(pd.snps[:50])
        print(list(pd.snpdict.keys())[:10])
        print(list(pd.snpdict.values())[:10])

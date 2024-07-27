import logging
import re
from pathlib import Path
from typing import Optional, Sequence, Any, Dict

import requests
from bs4 import BeautifulSoup

import json
import argparse
import random

from GenomeImporter import PersonalData, Approved
from data_types import Rsid
from snpedia import SnpediaWithCache
from utils import get_default_data_dir

COMPLEMENTS = {
    "A": "T",
    "T": "A",
    "C": "G",
    "G": "C",
}

VARIANT_REGEXP = re.compile(r'\(([ACTG-]);([ACTG-])\)')


class SNPCrawl:
    def __init__(self, data_dir: Path, snppath=None) -> None:
        self._data_dir = data_dir
        self._rsid_list_path = data_dir / "rsidDict.json"
        if self._rsid_list_path.exists():
            self.rsidDict = self.import_dict(self._rsid_list_path)
        else:
            self.rsidDict = {}

        self._snpedia = SnpediaWithCache(data_dir=data_dir)

    def crawl(self, rsids: Sequence[str]) -> None:
        normalized_rsids = [Rsid(item.lower()) for item in rsids]
        if rsids:
            self._download_rsids(normalized_rsids)

    def _download_rsids(self, rsids: Sequence[Rsid]):
        with requests.Session() as session:
            for count, rsid in enumerate(rsids):
                print(f"Loading {rsid}... ", end="", flush=True)
                html = self._snpedia.load_rsid(rsid, session)
                if html is None:
                    continue

                self.grabTable(rsid, html)
                print("")

                completed = count + 1
                if completed % 100 == 0:
                    print("%i out of %s completed" % (completed, len(rsids)))
                    self.export()
                    print("exporting current results")

        self.export()

    def grabTable(self, rsid: str, html: bytes) -> None:
        if rsid not in self.rsidDict.keys():
            self.rsidDict[rsid.lower()] = {
                "Description": "",
                "Variations": [],
                "StabilizedOrientation": ""
            }
            bs = BeautifulSoup(html, "html.parser")
            table = bs.find("table", {"class": "sortable smwtable"})
            description = bs.find('table', {'style': 'border: 1px; background-color: #FFFFC0; border-style: solid; margin:1em; width:90%;'})

            #Orientation Finder
            orientation = bs.find("td", string="Rs_StabilizedOrientation")
            if orientation is not None and orientation.parent is not None:
                plus = orientation.parent.find("td",string="plus")
                minus = orientation.parent.find("td",string="minus")
                if plus:
                    self.rsidDict[rsid]["StabilizedOrientation"] = "plus"
                if minus:
                    self.rsidDict[rsid]["StabilizedOrientation"] = "minus"
            else:
                  link = bs.find("a",{"title":"StabilizedOrientation"})
                  if link is not None and link.parent is not None and link.parent.parent is not None:
                    table_row = link.parent.parent
                    plus = table_row.find("td",string="plus")
                    minus = table_row.find("td",string="minus")
                    if plus:
                        self.rsidDict[rsid]["StabilizedOrientation"] = "plus"
                    if minus:
                        self.rsidDict[rsid]["StabilizedOrientation"] = "minus"

            if description:
                d1 = self.tableToList(description)
                self.rsidDict[rsid]["Description"] = d1[0][0]
                print(d1[0][0].encode("utf-8"))
            if table:
                d2 = self.tableToList(table)
                self.rsidDict[rsid]["Variations"] = d2[1:]
                print(d2[1:])

    def tableToList(self, table):
        rows = table.find_all('tr')
        data = []
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            data.append([ele for ele in cols if ele])
        return data

    def _complement(self, variant: str) -> Optional[str]:
        m = VARIANT_REGEXP.match(variant)
        if m is None:
            #print("XXX", variant)
            return None

        comp1 = COMPLEMENTS.get(m.group(1))
        comp2 = COMPLEMENTS.get(m.group(2))
        if comp1 is not None and comp2 is not None and comp1 > comp2:
            # It seems there is a convention to put them in alphabetic order
            comp1, comp2 = comp2, comp1
        return f"({comp1};{comp2})"

    def _chooseVariation(self, our_snp, variations, stbl_orient: str, debug_rsid: str) -> Optional[int]:
        for i, variation in enumerate(variations):
            if stbl_orient == "plus":
                our_oriented_snp = our_snp
            elif stbl_orient == "minus":
                # TODO: Stabilized orientation doesn't always works (e.g., rs10993994 for GRCh38). Probably we should
                #  look at reference genome used in SNPedia and in the analyzed genome.
                our_oriented_snp = self._complement(our_snp)
            else:
                return None

            if our_oriented_snp == variation[0]:
                return i

        if len(variations) == 3:  # Usually contains all variants.
            logging.warning(f"Couldn't find {our_snp} in {variations} ({debug_rsid}, {stbl_orient})")
        return None

    def createList(self, personal_data: PersonalData) -> Sequence[dict[str, Any]]:
        rsidList = []
        make = lambda rsname, description, variations, stbl_orientation, importance: \
            {"Name": rsname,
             "Description": description,
             "Importance": importance,
             "Genotype": personal_data.get_genotype(rsname.lower()),
             "Variations": str.join("<br>", variations),
             "StabilizedOrientation":stbl_orientation
            }

        messaged_once = False
        for rsid in self.rsidDict.keys():
            curdict = self.rsidDict[rsid]
            if "StabilizedOrientation" in curdict:
                stbl_orient = curdict["StabilizedOrientation"]
            else:
                stbl_orient = "Old Data Format"
                if not messaged_once:
                    print("Old Data Detected, Will not display variations bolding with old data.") 
                    print("See ReadMe for more details")
                    messaged_once = True

            variations_data = curdict["Variations"]
            if personal_data.has_genotype(rsid):
                variation_idx = self._chooseVariation(
                    our_snp=personal_data.get_genotype(rsid),
                    variations=variations_data,
                    stbl_orient=stbl_orient,
                    debug_rsid=rsid.lower(),
                )
            else:
                variation_idx = None

            variations = [" ".join(variation) for variation in variations_data]
            importance = None
            if variation_idx is not None:
                variations[variation_idx] = f'<b>{variations[variation_idx]}</b>'
                try:
                    if len(variations_data[variation_idx]) > 1:
                        importance = float(variations_data[variation_idx][1])
                except ValueError:
                    pass  # Ignore missing importance.

            maker = make(rsid, curdict["Description"], variations, stbl_orient, importance)
            
            rsidList.append(maker)

        return rsidList

    @staticmethod
    def import_dict(filepath: Path) -> Dict[str, Any]:
        with filepath.open("r") as jsonfile:
            return json.load(jsonfile)

    def export(self):
        #data = pd.DataFrame(self.rsidDict)
        #data = data.fillna("-")
        #data = data.transpose()
        #datapath = os.path.join(os.path.curdir, "data", 'rsidDict.csv')
        #data.to_csv(datapath)
        with self._rsid_list_path.open("w") as jsonfile:
            json.dump(self.rsidDict, jsonfile)


#Some interesting SNPs to get started with
SEED_RSIDS = [
    "rs1815739", "Rs53576", "rs4680", "rs1800497", "rs429358", "rs9939609", "rs4988235", "rs6806903", "rs4244285",
    "rs1801133",
]

#os.chdir(os.path.dirname(__file__))


def find_relevant_rsids(
        personal: PersonalData,
        crawl: SNPCrawl,
        count: int,
) -> Sequence[str]:
    snps_of_interest = [snp for snp in personal.snps if personal.has_genotype(snp)]
    snps_to_grab = [snp for snp in snps_of_interest if snp not in crawl.rsidDict]
    print(f"Yet to load: {len(snps_to_grab)}/{len(snps_of_interest)} genome SNPs available in SNPedia")
    snps_to_grab_set = set(snps_to_grab)

    result = []
    for rsid in SEED_RSIDS:
        if rsid in snps_to_grab_set:
            result.append(rsid)

    if len(result) < count:
        random.shuffle(snps_to_grab)
        result.extend(snps_to_grab[:count - len(result)])

    print(f"Chose {len(result)} SNPs to load")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--filepath', help='Filepath for 23andMe data to be used for import', required=False)
    parser.add_argument('-n', '--count', help='Number of SNPs to download', type=int, default=100)
    args = parser.parse_args()

    data_dir = get_default_data_dir()
    df_crawl = SNPCrawl(data_dir=data_dir)

    if args.filepath:
        rsids_on_snpedia = Approved(data_dir=data_dir)
        personal = PersonalData.from_input_file(Path(args.filepath), rsids_on_snpedia)
        personal.export(data_dir)  # Prepare cache for the webapp.
        rsids = find_relevant_rsids(personal, df_crawl, count=args.count)
    else:
        rsids = SEED_RSIDS

    df_crawl.crawl(rsids)


if __name__ == "__main__":
    main()

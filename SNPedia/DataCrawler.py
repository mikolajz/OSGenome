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
from data_types import Rsid, Orientation
from snpedia import SnpediaWithCache, SnpPage, GenotypeSummary, ParsedSnpsStorage
from utils import get_default_data_dir

COMPLEMENTS = {
    "A": "T",
    "T": "A",
    "C": "G",
    "G": "C",
}

VARIANT_REGEXP = re.compile(r'\(([ACTG-]);([ACTG-])\)')


class SNPCrawl:
    def __init__(self, snpedia: SnpediaWithCache, parsed_snps_storage: ParsedSnpsStorage) -> None:
        self._snpedia = snpedia
        self._parsed_snp_storage = parsed_snps_storage

    def crawl(self, rsids: Sequence[str]) -> None:
        normalized_rsids = [Rsid(item.lower()) for item in rsids]
        if rsids:
            self._download_rsids(normalized_rsids)

    def _download_rsids(self, rsids: Sequence[Rsid]):
        with requests.Session() as session:
            for count, rsid in enumerate(rsids):
                if rsid in self._parsed_snp_storage.snp_infos().keys():
                    print(f"SNP {rsid} already present")  # Shouldn't happen.
                    continue

                print(f"Loading {rsid}... ", end="", flush=True)
                html = self._snpedia.load_rsid(rsid, session)
                if html is None:
                    continue

                info = SnpPage(html).parse()
                self._parsed_snp_storage.set_snp(rsid, info)
                print("")

                completed = count + 1
                if completed % 100 == 0:
                    print("%i out of %s completed" % (completed, len(rsids)))
                    self._parsed_snp_storage.export()
                    print("exporting current results")

        self._parsed_snp_storage.export()

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

    def _chooseVariation(self, our_snp, variations: Sequence[GenotypeSummary], stbl_orient: Optional[Orientation], debug_rsid: str) -> Optional[int]:
        for i, variation in enumerate(variations):
            if stbl_orient is Orientation.PLUS:
                our_oriented_snp = our_snp
            elif stbl_orient is Orientation.MINUS:
                # TODO: Stabilized orientation doesn't always works (e.g., rs10993994 for GRCh38). Probably we should
                #  look at reference genome used in SNPedia and in the analyzed genome.
                our_oriented_snp = self._complement(our_snp)
            else:
                return None

            if our_oriented_snp == variation.genotype_str:
                return i

        if len(variations) == 3:  # Usually contains all variants.
            logging.warning(f"Couldn't find {our_snp} in {variations} ({debug_rsid}, {stbl_orient})")
        return None

    def createList(self, personal_data: PersonalData) -> Sequence[dict[str, Any]]:
        rsidList = []
        make = lambda rsname, description, variations, stbl_orientation, importance: \
            {"Name": rsname,
             "Description": description or "",
             "Importance": importance or "",
             "Genotype": personal_data.get_genotype(rsname.lower()),
             "Variations": str.join("<br>", variations),
             "StabilizedOrientation": stbl_orientation.value if stbl_orientation is not None else ""
            }

        snp_infos = self._parsed_snp_storage.snp_infos()
        for rsid, snp_info in snp_infos.items():
            variations_data = snp_info.genotype_summaries
            if personal_data.has_genotype(rsid):
                variation_idx = self._chooseVariation(
                    our_snp=personal_data.get_genotype(rsid),
                    variations=variations_data,
                    stbl_orient=snp_info.stabilized_orientation,
                    debug_rsid=rsid.lower(),
                )
            else:
                variation_idx = None

            variations = ["".join([
                    variation.genotype_str,
                    str(variation.magnitude) if variation.magnitude is not None else "",
                    variation.description or ''
                ])
                for variation in variations_data
            ]
            importance = None
            if variation_idx is not None:
                variations[variation_idx] = f'<b>{variations[variation_idx]}</b>'
                try:
                    if variations_data[variation_idx].magnitude is not None:
                        importance = str(variations_data[variation_idx].magnitude)
                except ValueError:
                    pass  # Ignore missing importance.

            maker = make(rsid, snp_info.description, variations, snp_info.stabilized_orientation, importance)
            
            rsidList.append(maker)

        return rsidList


#Some interesting SNPs to get started with
SEED_RSIDS = [
    "rs1815739", "Rs53576", "rs4680", "rs1800497", "rs429358", "rs9939609", "rs4988235", "rs6806903", "rs4244285",
    "rs1801133",
]


def find_relevant_rsids(
        personal: PersonalData,
        parsed_snps_storage: ParsedSnpsStorage,
        count: int,
) -> Sequence[str]:
    snps_of_interest = [snp for snp in personal.snps if personal.has_genotype(snp)]
    snps_to_grab = [snp for snp in snps_of_interest if snp not in parsed_snps_storage.snp_infos().keys()]
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
    snpedia = SnpediaWithCache(data_dir=data_dir)
    parsed_snps_storage = ParsedSnpsStorage.load(data_dir=data_dir, snpedia=snpedia)
    df_crawl = SNPCrawl(snpedia=snpedia, parsed_snps_storage=parsed_snps_storage)

    if args.filepath:
        rsids_on_snpedia = Approved(data_dir=data_dir)
        personal = PersonalData.from_input_file(Path(args.filepath), rsids_on_snpedia)
        personal.export(data_dir)  # Prepare cache for the webapp.
        rsids = find_relevant_rsids(personal, parsed_snps_storage, count=args.count)
    else:
        rsids = SEED_RSIDS

    df_crawl.crawl(rsids)


if __name__ == "__main__":
    main()

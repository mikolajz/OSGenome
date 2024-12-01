from pathlib import Path
from typing import Sequence

import requests

import argparse
import random

from GenomeImporter import PersonalData, Approved
from data_types import Rsid, Orientation
from inputs.formats import InputFormat
from snpedia import SnpediaWithCache, SnpPage, GenotypeSummary, ParsedSnpsStorage
from utils import get_default_data_dir


class SNPCrawl:
    def __init__(self, snpedia: SnpediaWithCache, parsed_snps_storage: ParsedSnpsStorage) -> None:
        self._snpedia = snpedia
        self._parsed_snps_storage = parsed_snps_storage

    def crawl(self, rsids: Sequence[Rsid]) -> None:
        with requests.Session() as session:
            for count, rsid in enumerate(rsids):
                if rsid in self._parsed_snps_storage.snp_infos().keys():
                    print(f"SNP {rsid} already present")  # Shouldn't happen.
                    continue

                print(f"Loading {rsid}... ", end="", flush=True)
                html = self._snpedia.load_rsid(rsid, session)
                if html is None:
                    continue

                info = SnpPage(html).parse()
                self._parsed_snps_storage.set_snp(rsid, info)
                print(f"{info.description or ''} {info.genotype_summaries if info.genotype_summaries else ''}")

                completed = count + 1
                if completed % 100 == 0:
                    print("%i out of %s completed" % (completed, len(rsids)))
                    self._parsed_snps_storage.export()
                    print("exporting current results")

        self._parsed_snps_storage.export()


#Some interesting SNPs to get started with
SEED_RSIDS = [
    Rsid(rsid_str) for rsid_str in [
        "rs1815739", "Rs53576", "rs4680", "rs1800497", "rs429358", "rs9939609", "rs4988235", "rs6806903", "rs4244285",
        "rs1801133",
    ]
]


def find_relevant_rsids(
        personal: PersonalData,
        parsed_snps_storage: ParsedSnpsStorage,
        count: int,
) -> Sequence[Rsid]:
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
    parser.add_argument(
        '-f', '--filepath', help='Path to 23andMe or VCF data file (VCF must be in build38 format)', required=True
    )
    parser.add_argument('--format', choices=[f.value for f in InputFormat],
                        help='Format of the input file; leave empty to autodetect')
    parser.add_argument('-n', '--count', help='Number of SNPs to download', type=int, default=100)
    args = parser.parse_args()

    print('Loading cache files...')
    data_dir = get_default_data_dir()
    snpedia = SnpediaWithCache(data_dir=data_dir)
    parsed_snps_storage = ParsedSnpsStorage.load(data_dir=data_dir, snpedia=snpedia)
    df_crawl = SNPCrawl(snpedia=snpedia, parsed_snps_storage=parsed_snps_storage)

    if args.filepath:
        print('Loading input file...')
        rsids_on_snpedia = Approved(data_dir=data_dir)
        personal = PersonalData.from_input_file(Path(args.filepath), args.format, rsids_on_snpedia)
        personal.export(data_dir)  # Prepare cache for the webapp.
        rsids = find_relevant_rsids(personal, parsed_snps_storage, count=args.count)
    else:
        rsids = SEED_RSIDS

    df_crawl.crawl(rsids)


if __name__ == "__main__":
    main()

import logging
from typing import Optional

from data_types import ReferenceBuild, Orientation
from genotype import Genotype
from snpedia import SnpediaSnpInfo


class VariantChooser:

    def __init__(
            self,
            personal_genome_build: ReferenceBuild,
    ):
        self._personal_genome_build = personal_genome_build

    def find_variant(
            self,
            our_genotype: Genotype,
            snp_info: SnpediaSnpInfo,
            debug_rsid: str
    ) -> Optional[int]:
        variations = snp_info.genotype_summaries
        snpedia_build = ReferenceBuild.BUILD38  # TODO: take it from SNPedia instead of assuming Build 38.
        orientation = snp_info.orientation
        if snpedia_build != self._personal_genome_build:
            raise NotImplementedError("Converting builds not implemented yet.")

        for i, variation in enumerate(variations):
            if orientation is Orientation.PLUS:
                our_oriented_snp = our_genotype
            elif orientation is Orientation.MINUS:
                # TODO: Stabilized orientation doesn't always works (e.g., rs10993994 for GRCh38). Probably we should
                #  look at reference genome used in SNPedia and in the analyzed genome.
                our_oriented_snp = our_genotype.complementary()
            else:
                return None

            if our_oriented_snp.unordered_equal(variation.genotype_str):
                return i

        if len(variations) == 3:  # Usually contains all variants.
            logging.warning(f"Couldn't find {our_genotype} in {variations} ({debug_rsid}, {orientation})")
        return None

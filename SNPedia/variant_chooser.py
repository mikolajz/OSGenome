import logging
from typing import Optional, Sequence

from pyliftover import LiftOver
from typing_extensions import assert_never

from chromosome import Location
from data_types import ReferenceBuild, Orientation
from genotype import Genotype
from snpedia import SnpediaSnpInfo, GenotypeSummary


class VariantChooser:

    def __init__(
            self,
            personal_genome_build: ReferenceBuild,
    ):
        self._personal_genome_build = personal_genome_build
        self._liftover_cache: dict[tuple[ReferenceBuild, ReferenceBuild], LiftOver] = {}

    def get_orientation_in_genome_reference_build(
            self,
            location: Location,
            snp_info: SnpediaSnpInfo,
    ) -> Optional[Orientation]:
        snpedia_build = ReferenceBuild.BUILD38  # TODO: take it from SNPedia instead of assuming Build 38.
        orientation = snp_info.orientation
        if orientation is None:
            return None

        if snpedia_build != self._personal_genome_build:
            lift_over = self._get_lift_over(from_build=self._personal_genome_build, to=snpedia_build)
            # Note: pyliftover says it uses 0-based convention, while VCFs and 23andme files use 1-based.
            places = lift_over.convert_coordinate(location.chromosome, location.position - 1)
            if not places:
                # Happens from time to time.
                logging.debug(f'Cannot convert {location} to SNPedia build {snpedia_build.value.snpedia_name}')
                return None

            _, _, snpedia_build_orientation, _ = places[0]
            if snpedia_build_orientation == '-':
                # The orientation changed between one build and the other. The "orientation" field on SNPedia, while
                # true for the build in SNPedia, is wrong for the build our genotype is in.
                orientation = orientation.other()

        return orientation

    def find_variant(
            self,
            our_genotype: Genotype,
            orientation: Optional[Orientation],
            variations: Sequence[GenotypeSummary],
            debug_rsid: str
    ) -> Optional[int]:
        if orientation is Orientation.PLUS:
            our_oriented_snp = our_genotype
        elif orientation is Orientation.MINUS:
            our_oriented_snp = our_genotype.complementary()
        elif orientation is None:
            return None
        else:
            assert_never(orientation)

        for i, variation in enumerate(variations):
            if our_oriented_snp.unordered_equal(variation.genotype_str):
                return i

        if len(variations) == 3:  # Usually contains all variants.
            logging.warning(
                f"Suspicious, but necessarily wrong: couldn't find {our_genotype} in {variations} ({debug_rsid}, {orientation})"
            )
        return None

    def _get_lift_over(self, from_build: ReferenceBuild, to: ReferenceBuild) -> LiftOver:
        lift_over = self._liftover_cache.get((from_build, to))
        if lift_over is not None:
            return lift_over

        print((from_build.value.pyliftover_name, to.value.pyliftover_name))  # DO_NOT_MERGE
        lift_over = LiftOver(from_build.value.pyliftover_name, to.value.pyliftover_name)
        self._liftover_cache[(from_build, to)] = lift_over
        return lift_over

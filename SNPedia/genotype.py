from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, NewType, cast

import dataclasses_json

DnaString = NewType("DnaString", str)  # Sequence of ACGT.

COMPLEMENTS = {
    "A": "T",
    "T": "A",
    "C": "G",
    "G": "C",
}

_COMPLEMENTS_TRANS = str.maketrans(COMPLEMENTS)


def complement_string(input: DnaString) -> DnaString:
    return DnaString(input.translate(_COMPLEMENTS_TRANS))


@dataclass
class Genotype:
    """
    "For DNA, the genotype is simply the specific information encoded at a given position in the genome."

    (see https://www.genome.gov/genetics-glossary/genotype)
    """
    alleles: Sequence[DnaString]  # Usually two elements, since most locations are diploid.

    @staticmethod
    def from_string(input: str) -> Genotype:
        assert input[0] == "(" and input[-1] == ")"
        return Genotype(
            alleles=cast(Sequence[DnaString], input[1:-1].split(";")),
        )

    def __str__(self) -> str:
        return "({})".format(";".join(self.alleles))

    def complementary(self) -> Genotype:
        return Genotype(
            alleles=[complement_string(a) for a in self.alleles],
        )

    def unordered_equal(self, g2: Genotype) -> bool:
        if len(self.alleles) != len(g2.alleles):
            return False

        if len(self.alleles) == 2:
            # Shortcut - should improve performance
            return (
                (self.alleles[0] == g2.alleles[0] and self.alleles[1] == g2.alleles[1]) or
                (self.alleles[0] == g2.alleles[1] and self.alleles[1] == g2.alleles[0])
            )

        if len(self.alleles) == 1:
            return self.alleles[0] == g2.alleles[0]

        return sorted(self.alleles) == sorted(g2.alleles)


dataclasses_json.cfg.global_config.encoders[Genotype] = Genotype.__str__
dataclasses_json.cfg.global_config.decoders[Genotype] = Genotype.from_string

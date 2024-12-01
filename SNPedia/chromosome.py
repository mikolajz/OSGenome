from dataclasses import dataclass
from typing import NewType

# There seems to be two conventions for chromosomes - "chr1", "chrM", ... or "1", "MT", .... This type contains
# the former.
Chromosome = NewType('Chromosome', str)

def chromosome_from_short_form(short_form: str) -> Chromosome:
    if short_form == "MT":
        return Chromosome("chrM")

    return Chromosome("chr" + short_form)


@dataclass(frozen=True)
class Location:
    chromosome: Chromosome
    position: int

    def __str__(self) -> str:
        return f"{self.chromosome}:{self.position}"

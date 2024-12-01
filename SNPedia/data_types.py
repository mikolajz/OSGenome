from dataclasses import dataclass
from enum import Enum
from typing import NewType

Rsid = NewType('Rsid', str)

class Orientation(Enum):
    PLUS = "plus"
    MINUS = "minus"


@dataclass(frozen=True)
class BuildInfo:
    snpedia_name: str
    pyliftover_name: str


class ReferenceBuild(Enum):
    BUILD37 = BuildInfo(snpedia_name='GRCh37', pyliftover_name='hg19')
    BUILD38 = BuildInfo(snpedia_name='GRCh38', pyliftover_name='hg38')

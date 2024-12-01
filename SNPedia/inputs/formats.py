import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, Tuple, Set, Optional

import vcfpy
from dataclasses_json import DataClassJsonMixin
from typing_extensions import assert_never

from chromosome import Chromosome, chromosome_from_short_form, Location
from data_types import Rsid, ReferenceBuild


class InputFormat(Enum):
    MICROARRAY = "microarray_txt"
    VCF = "vcf"


@dataclass(frozen=True)
class InputRecord:
    rsid: Rsid
    # We need the chromosome and position information to convert between reference builds.
    chromosome: Chromosome
    position: int
    genotype: str  # We don't use Genotype but convert on the fly to make files load faster.

    def get_location(self) -> Location:
        return Location(chromosome=self.chromosome, position=self.position)


class PersonalDataInput(ABC):

    @abstractmethod
    def read(self, interesting: Set[Rsid]) -> Iterator[InputRecord]:
        pass

    @abstractmethod
    def get_reference_build(self) -> ReferenceBuild:
        pass


class MicroarrayInput(PersonalDataInput):

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self, interesting: Set[Rsid]) -> Iterator[InputRecord]:
        lines_count = 0
        interesting_count = 0

        with self._path.open("r") as file:
            for line in file.readlines():
                lines_count += 1
                if line[0] == "#":
                    continue

                pd = line.split("\t")
                rsid = Rsid(pd[0].lower())
                if rsid not in interesting:
                    continue

                interesting_count += 1
                yield InputRecord(
                    rsid=rsid,
                    chromosome=chromosome_from_short_form(pd[1]),
                    position=int(pd[2]),
                    genotype="(" + pd[3].rstrip()[0] + ";" + pd[3].rstrip()[-1] + ")",
                )

        print(f"{interesting_count}/{lines_count} SNPs from personal data present also in SNPedia.")

    def get_reference_build(self) -> ReferenceBuild:
        return ReferenceBuild.BUILD37


class VcfInput(PersonalDataInput):

    def __init__(self, path: Path, sample_index: int = 0) -> None:
        self._path = path
        self._sample_index = sample_index

    def read(self, interesting: Set[Rsid]) -> Iterator[InputRecord]:
        lines_count = 0
        interesting_count = 0

        reader = vcfpy.Reader.from_path(self._path)

        pattern = re.compile(r"^[^\t]*\t[^\t]*\t([^\t]*)\t")

        for line in reader.stream:
            lines_count += 1

            # Using the vcfpy.Reader iterator and parsing each line is too slow. Do some filtering first.
            m = pattern.search(line)
            assert m is not None, line
            rsids = m[1]

            if rsids == ".":  # Used to denote missing ID.
                continue
            if "," in rsids:
                if all(rsid not in interesting for rsid in rsids.split(",")):
                    continue
            else:
                if rsids not in interesting:
                    continue

            # Now get back to using vcfpy.Reader.
            record = reader.parser.parse_line(line)
            for rsid in record.ID:
                if rsid not in interesting:
                    continue
                interesting_count += 1
                assert isinstance(record.POS, int)
                yield InputRecord(
                    rsid=Rsid(rsid),
                    chromosome=Chromosome(record.CHROM),
                    position=record.POS,
                    genotype="(" + ";".join(record.calls[self._sample_index].gt_bases) + ")",
                )

        print(f"{interesting_count}/{lines_count} SNPs from personal data present also in SNPedia.")

    def get_reference_build(self) -> ReferenceBuild:
        # TODO: it's a naive assumption that all VCF files are build 38 - support other builds.
        return ReferenceBuild.BUILD38


def autodetect_input(path: Path) -> Optional[InputFormat]:
    if path.suffix == ".txt":
        return InputFormat.MICROARRAY
    if path.suffix == ".vcf" or path.suffixes[-2:] == [".vcf", ".gz"]:
        return InputFormat.VCF
    return None


def create_reader(path: Path, format_hint: Optional[str]) -> PersonalDataInput:
    if format_hint is None:
        format = autodetect_input(path)
        if format is None:
            raise RuntimeError("Could detect file format based on file name. Please use --format flag")
    else:
        format = InputFormat(format_hint)

    if format is InputFormat.MICROARRAY:
        return MicroarrayInput(path)
    elif format is InputFormat.VCF:
        return VcfInput(path)
    else:
        assert_never(format)

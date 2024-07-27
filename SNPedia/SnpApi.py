import logging
import re
from typing import Optional, Sequence, Any

from flask import Flask, render_template, request, send_file, send_from_directory, jsonify
import base64
import io

from GenomeImporter import PersonalData
from data_types import Orientation
from snpedia import SnpediaWithCache, ParsedSnpsStorage, GenotypeSummary
from utils import get_default_data_dir

app = Flask(__name__, template_folder='templates')

COMPLEMENTS = {
    "A": "T",
    "T": "A",
    "C": "G",
    "G": "C",
}

VARIANT_REGEXP = re.compile(r'\(([ACTG-]);([ACTG-])\)')


class UiListGenerator:

    def __init__(self, parsed_snps_storage: ParsedSnpsStorage) -> None:
        self._parsed_snps_storage = parsed_snps_storage

    def _complement(self, variant: str) -> Optional[str]:
        m = VARIANT_REGEXP.match(variant)
        if m is None:
            # print("XXX", variant)
            return None

        comp1 = COMPLEMENTS.get(m.group(1))
        comp2 = COMPLEMENTS.get(m.group(2))
        if comp1 is not None and comp2 is not None and comp1 > comp2:
            # It seems there is a convention to put them in alphabetic order
            comp1, comp2 = comp2, comp1
        return f"({comp1};{comp2})"

    def _chooseVariation(self, our_snp, variations: Sequence[GenotypeSummary], stbl_orient: Optional[Orientation],
                         debug_rsid: str) -> Optional[int]:
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

        snp_infos = self._parsed_snps_storage.snp_infos()
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

            variations = [" ".join([
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


@app.route("/", methods=['GET', 'POST'])
def main_page():
    print(vars(request.form))
    return render_template('snp_resource.html')


@app.route("/excel", methods=['GET', 'POST'])
def create_file():
    content = request.form

    filename = content['fileName']
    file_contents = content['base64']
    binary_contents = base64.b64decode(file_contents)

    bytesIO = io.BytesIO()
    bytesIO.write(binary_contents)
    bytesIO.seek(0)

    return send_file(bytesIO,
                     attachment_filename=filename,  # type: ignore[call-arg]
                     as_attachment=True)


@app.route('/images/<path:path>')
def send_image(path):
    return send_from_directory('images', path)


@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)


@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)


@app.route("/api/rsids", methods=['GET'])
def get_types():
    return jsonify({"results": app.data_list})  # type: ignore[attr-defined]


def main() -> None:
    data_dir = get_default_data_dir()
    personal_data = PersonalData.from_cache(data_dir)
    snpedia = SnpediaWithCache(data_dir=data_dir)
    parsed_snps_storage = ParsedSnpsStorage.load(data_dir=data_dir, snpedia=snpedia)
    app.data_list = UiListGenerator(parsed_snps_storage=parsed_snps_storage).createList(personal_data=personal_data)  # type: ignore[attr-defined]
    app.run(debug=True)


if __name__ == "__main__":
    main()

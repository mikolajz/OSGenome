import argparse
import logging
import os
import re
import socket
import threading
import time
import webbrowser
from typing import Optional, Sequence, Any

from flask import Flask, render_template, request, send_file, send_from_directory, jsonify
import base64
import io

from storage.personal_data import PersonalData
from storage.settings import get_settings
from base.data_types import Orientation
from base.genotype import Genotype
from snpedia import SnpediaWithCache, ParsedSnpsStorage, GenotypeSummary, SnpediaSnpInfo
from base.utils import get_default_data_dir
from base.variant_chooser import VariantChooser

app = Flask(__name__, template_folder='templates')


def _wait_for_port(host: str, port: int) -> None:
    """Wait for a port to become available indefinitely."""
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.1)
                result = sock.connect_ex((host, port))
                if result == 0:
                    return
        except:
            pass
        time.sleep(0.1)


WARNING_EMOJI = "\u26A0\uFE0F"
ORIENTATION_WARNING = (
    f"{WARNING_EMOJI} <i><b>Orientation changed between versions of reference genome.</b> "
    "Despite efforts to do it right, we may have a A&lt;-&gt;T, C&lt;-&gt;G mismatch.</i>"
)

class UiListGenerator:

    def __init__(self, parsed_snps_storage: ParsedSnpsStorage, variant_chooser: VariantChooser) -> None:
        self._parsed_snps_storage = parsed_snps_storage
        self._variant_chooser = variant_chooser

    def _compute_secondary_importance(self, snp_info: SnpediaSnpInfo, variation_idx: Optional[int]) -> int:
        # A tie-breaker, especially useful for entries with missing magnitude.
        result = 0
        if snp_info.description:
            result += 1
        if snp_info.genotype_summaries:
            result += 1
        if variation_idx is not None:
            if snp_info.genotype_summaries[variation_idx].magnitude != 0:  # We value an explicit 0 less than None.
                result += 2
            else:
                result += 1

        return result

    def createList(self, personal_data: PersonalData) -> Sequence[dict[str, Any]]:
        rsidList = []
        snp_infos = self._parsed_snps_storage.snp_infos()
        for rsid, snp_info in snp_infos.items():
            variations_data = snp_info.genotype_summaries
            if not personal_data.has_genotype(rsid):
                continue

            genotype, location = personal_data.get_genotype_and_location(rsid)
            orientation = self._variant_chooser.get_orientation_in_genome_reference_build(location, snp_info)

            variation_idx = self._variant_chooser.find_variant(
                our_genotype=genotype,
                location=location,
                orientation=orientation,
                variations=snp_info.genotype_summaries,
                debug_rsid=rsid.lower(),
            )

            variations = [" ".join([
                    str(variation.genotype_str),
                    variation.description or '',
                    f'(imp: {variation.magnitude})' if variation.magnitude is not None else "",
                ])
                for variation in variations_data
            ]
            importance = None
            if variation_idx is not None:
                variations[variation_idx] = f'<b>{variations[variation_idx]}</b>'
                try:
                    if variations_data[variation_idx].magnitude is not None:
                        importance = variations_data[variation_idx].magnitude
                except ValueError:
                    pass  # Ignore missing importance.

            # Add a tie-breaker for entries with the same importance value, especially to sort missing importance
            actual_importance = round(
                (importance or 0.0) * 100 + self._compute_secondary_importance(snp_info, variation_idx)
            )

            if snp_info.orientation is not None and snp_info.orientation != snp_info.stabilized_orientation:
                variations = [
                    ORIENTATION_WARNING,
                    *variations,
                ]

            maker = {
                "Name": rsid,
                "Description": snp_info.description or "",
                "Importance": importance,
                "ActualImportance": actual_importance,
                "Genotype": str(personal_data.get_genotype(rsid)),
                "Variations": str.join("<br>", variations),
                "StabilizedOrientation": orientation.value if orientation is not None else ""
            }
            rsidList.append(maker)

        return rsidList


@app.route("/", methods=['GET', 'POST'])
def main_page():
    print(vars(request.form))
    return render_template('snp_resource.html')

@app.route("/settings/show_disclaimer", methods=['GET', 'PUT'])
def disclaimer_setting():
    """REST endpoint for disclaimer preference - GET to read, PUT to update."""
    settings = get_settings()
    
    if request.method == 'GET':
        """Check if the user has chosen not to show the disclaimer."""
        show_disclaimer = settings.get_show_disclaimer()
        return jsonify({"show_disclaimer": show_disclaimer})
    
    elif request.method == 'PUT':
        """Set the user's preference for showing the disclaimer."""
        data = request.get_json()
        if data and 'show_disclaimer' in data:
            settings.set_show_disclaimer(bool(data['show_disclaimer']))
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Invalid data"}), 400


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

@app.route('/warning_content.html')
def send_warning_content():
    return send_from_directory('templates', 'warning_content.html')


@app.route("/api/rsids", methods=['GET'])
def get_types():
    return jsonify({"results": app.data_list})  # type: ignore[attr-defined]


def main() -> None:
    parser = argparse.ArgumentParser(description='Launch the SNP results viewer web application')
    parser.add_argument('--no-browser', action='store_true', help='Do not automatically open a web browser')
    args = parser.parse_args()
    
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Do the expensive initialization only when in the process being reloaded.
        data_dir = get_default_data_dir()
        personal_data = PersonalData.from_cache(data_dir)
        snpedia = SnpediaWithCache(data_dir=data_dir)
        parsed_snps_storage = ParsedSnpsStorage.load(data_dir=data_dir, snpedia=snpedia)
        app.data_list = UiListGenerator(  # type: ignore[attr-defined]
            parsed_snps_storage=parsed_snps_storage,
            variant_chooser=VariantChooser(personal_genome_build=personal_data.get_reference_build()),
        ).createList(personal_data=personal_data)
    else:
        # Launch browser if requested - only in main process, not in the reloader worker.
        if not args.no_browser:
            def __launch_browser_when_ready():
                _wait_for_port('127.0.0.1', 5000)
                webbrowser.open('http://127.0.0.1:5000')
            
            threading.Thread(target=__launch_browser_when_ready, daemon=True).start()
    
    app.run(debug=True)


if __name__ == "__main__":
    main()

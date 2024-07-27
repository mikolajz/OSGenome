from flask import Flask, render_template, request, send_file, send_from_directory, jsonify
import base64
from DataCrawler import SNPCrawl
import io

from GenomeImporter import PersonalData
from snpedia import SnpediaWithCache, ParsedSnpsStorage
from utils import get_default_data_dir

app = Flask(__name__, template_folder='templates')


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
    app.data_list = SNPCrawl(snpedia=snpedia, parsed_snps_storage=parsed_snps_storage).createList(personal_data=personal_data)  # type: ignore[attr-defined]
    app.run(debug=True)


if __name__ == "__main__":
    main()

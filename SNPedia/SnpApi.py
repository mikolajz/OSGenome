from flask import Flask, render_template, request, send_file, send_from_directory, jsonify
import base64
from DataCrawler import SNPCrawl
import io

from GenomeImporter import PersonalData
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
    filecontents = content['base64']
    filecontents = base64.b64decode(filecontents)

    bytesIO = io.BytesIO()
    bytesIO.write(filecontents)
    bytesIO.seek(0)

    return send_file(bytesIO,
                     attachment_filename=filename,
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
    return jsonify({"results": app.data_list})


def main() -> None:
    data_dir = get_default_data_dir()
    personal_data = PersonalData.from_cache(data_dir)
    app.data_list = SNPCrawl(data_dir=data_dir).createList(personal_data=personal_data)
    app.run(debug=True)


if __name__ == "__main__":
    main()

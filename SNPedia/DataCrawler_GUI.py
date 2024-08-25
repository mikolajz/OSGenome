from pathlib import Path

from tkinter import filedialog
from tkinter import *

from DataCrawler import SNPCrawl, find_relevant_rsids
from GenomeImporter import PersonalData, Approved
from snpedia import SnpediaWithCache, ParsedSnpsStorage
from utils import get_default_data_dir


READ_COUNT = 200


def get_filepath_using_gui(data_dir: Path) -> Path:
    last_save_path = data_dir / "lastsave.txt"

    try:
        last_path = last_save_path.read_text()
    except FileNotFoundError:  # Configuration file not crated yet.
        last_path = "/"

    root = Tk()
    filename = Path(filedialog.askopenfilename(  # type: ignore[attr-defined]
        initialdir=last_path,
        title="Select file",
        filetypes=(("text files", "*.txt"), ("all files", "*.*")),
    ))
    root.destroy()

    last_save_path.write_text(str(filename.parent))

    return filename


def main():
    data_dir = get_default_data_dir()
    snpedia = SnpediaWithCache(data_dir=data_dir)
    parsed_snps_storage = ParsedSnpsStorage.load(data_dir=data_dir, snpedia=snpedia)
    df_crawl = SNPCrawl(snpedia=snpedia, parsed_snps_storage=parsed_snps_storage)

    file_path = get_filepath_using_gui(data_dir)

    rsids_on_snpedia = Approved(data_dir=data_dir)
    personal = PersonalData.from_input_file(file_path, None, rsids_on_snpedia)
    personal.export(data_dir)  # Prepare cache for the webapp.
    rsids = find_relevant_rsids(personal, parsed_snps_storage, count=READ_COUNT)

    df_crawl.crawl(rsids)


if __name__ == "__main__":
    main()

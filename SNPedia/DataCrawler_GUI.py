from pathlib import Path

from tkinter import filedialog
from tkinter import *

from DataCrawler import SNPCrawl, find_relevant_rsids
from GenomeImporter import PersonalData, Approved
from utils import get_default_data_dir


READ_COUNT = 200


def get_filepath_using_gui() -> Path:
    last_save_path = Path("lastsave.txt")  # TODO: save in data_dir?

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
    df_crawl = SNPCrawl(data_dir=data_dir)

    file_path = get_filepath_using_gui()

    rsids_on_snpedia = Approved(data_dir=data_dir)
    personal = PersonalData.from_input_file(file_path, rsids_on_snpedia)
    personal.export(data_dir)  # Prepare cache for the webapp.
    rsids = find_relevant_rsids(personal, df_crawl, count=READ_COUNT)

    df_crawl.crawl(rsids)


if __name__ == "__main__":
    main()

# OSGenome
An Open Source Web Application for analyzing genetic information (23AndMe files, VCF files from WGS) using SNPedia information.

A fork of the application by @mentatpsi [https://github.com/mentatpsi/OSGenome]

## Description
The application looks up each variant from a 23andMe or a VCF file on SNPedia and shows the results in a tabular form. Compared to a service on the Internet, the downside is that it requires more
manual work (also, different services have different methodologies, this app implements only one approach), but the upside is that the data doesn't leave your computer.

Worth mentioning is [Promethease](https://promethease.com/) that is a commercial service AFAIU run by the maintainers of SNPedia who probably understand it the best.

## Will it tell me all about my future?
No, genes are by far not the only thing shaping our future and looking at variants in isolation has its limitations (some limitations are described [here](SNPedia/templates/start_popup.html) - may be useful in case are wondering whether to download it).

## Usage:

Currently tested only under Linux and some knowledge of the command line is required.

Make sure you have [python pip](https://packaging.python.org/installing/).

### One-time setup
Step 0 (optional, but recommended):
Create a virtual environment.
```
python -m venv /path/to/new/virtual/environment
source /path/to/new/virtual/environment/bin/activate  # activate the virtual envornment
```
This will create a separate space where the libraries from the next step will be installed, this avoiding version conflict with other Python software you might have.

Step 1:
Install the necessary libraries:
```
pip install -r requirements.txt
```


### Running the tool - viewing one more set of information
Step 0 (if you did step 0 of the one-time setup):
```
source /path/to/new/virtual/environment/bin/activate  # activate the virtual envornment
```

Step 1:
Download the next pack of 100 entries about your genome.
```
python3 SNPedia/import_from_snpedia.py -f [Absolute path of your downloaded raw 23andMe data or VCF (latter can be gzipped)]
```
We download a small piece at once to be nice to SNPedia servers. The data accumulates as you keep running this command. You can use the `-n` flag to control how much you download at once.


Step 2:
Run the viewer of the entires downloaded so far:
```
python3 SNPedia/results_viewer.py
```
This should launch a Web browser on its own. If it doesn't open, navigate manually to [http://127.0.0.1:5000/] (where `127.0.0.1` means that it's hosted on your machine; it's configured to be accessible only from your computer).


## VCF files limitations
Tested only with a Nebula Genomics file. Assumes Build38 reference genome (but it's easy to change - see `VcfInput.get_reference_build` in `SNPedia/inputs/formats.py`).

## Disclaimer
Raw Data coming from Genetic tests done by Direct To Consumer companies such as 23andMe and Ancestry.com were found to have a false positive rate of 40% for genes with clinical significance in a March 2018 study [*False-positive results released by direct-to-consumer genetic tests highlight the importance of clinical confirmation testing for appropriate patient care*](https://www.nature.com/articles/gim201838). For this reason, it's important to confirm any at risk clinical SNPs with your doctor who can provide genetic tests and send them to a clinical laboratory.


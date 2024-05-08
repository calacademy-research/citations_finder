#!/usr/bin/env python3
from doi_entry import DoiFactory
from doi_database import DoiDatabase
from database_report import DatabaseReport
from scan_database import ScanDatabase
from db_connection import DBConnector
from known_good_papers import KnownGoodPapers
from scan import Scan
from validator import Validator
from config import Config
from downloaders import Downloaders
from copyout import CopyOut
from crossref_journal_entry import CrossrefJournalEntry
import journal_finder
import logging

import os


def download_single_doi(doi):
    """This function handles the retrieval of DOI information, 
    checks if the DOI exists in the database, dois table, 
    and initiates the download of the associated document using 
    class Downloaders in downloaders.py

    :param doi: The DOI  of the document to be downloaded.
    :type doi: str
    :param config: The configuration settings for the download.
    :type config: dict
    :return: None

    Limitations here: if doi specified is shown 
    """
    logging.info("Single DOI download mode")
    select_doi = f"""select * from dois where doi='{doi}'"""
    doif = DoiFactory(select_doi)
    doi_list = doif.dois
    if len(doi_list) == 0:
        logging.critical(f"Single download failed - DOI not in system: {select_doi} ")
        raise ValueError("DOI not found in the system")
        # above line used to be "sys.exit(1)", but it prevents sphinx autodoc from working

    downloaders = Downloaders()

    for doi_entry in doi_list:
        downloaders.download(doi_entry)


def retry_failed_unpaywall_links(config):
    """Retry failed unpaywall downloads for DOIs. 
    
    This function retrieves the list of DOIs that failed to download from the unpaywall service. 
    Failed DOIs are characterized as a) downloaded column = False in dois table, and 
    b) open_url column in unpaywall_downloader table has a url address. Then funtion 
    attempts to retry the download for each DOI. If a download is successful, the DOI is marked
    as a successful download.

    :param config: user configuration settings in config.ini, [general]
    :type config: dict

    :return: None

    """
    logging.info("Retrying failed unpaywall downloads")
    select_dois = f"""select * from dois, unpaywall_downloader where downloaded=False 
     and dois.doi = unpaywall_downloader.doi and unpaywall_downloader.open_url is not null"""

    doif = DoiFactory(select_dois)
    doi_list = doif.dois
    downloaders = Downloaders()

    for doi_entry in doi_list:
        if downloaders.download(doi_entry):
            doi_entry.mark_successful_download()


#  More may need to be added here; this is for efficency;
# most elements create on class instatntiation, but we potentially
# hit create here so many times that it belongs in a run-once place.
def setup_tables():
    CrossrefJournalEntry.create_tables()
    downloaders = Downloaders()
    downloaders.create_tables()


# TODO: some missing pdfs are marked as downloaded, we need a cross check step to mark
# missing as missing.
def setup():
    """This is the main function
    
    Reads the configuration settings and executes 
    different blocks of code based on the configuration option.

    :return: None
    
    """
    config = Config()
    setup_tables()

    if config.get_boolean('journal population', 'populate_journals'):
        gbif_url_list = config.get_list('journal population', 'gbif_api_collection_links')
        for url in gbif_url_list:
            logging.info(f"Processing journals for population from link: {url}")
            journal_finder.addJournals('journals.tsv', url)

    if config.get_boolean('general', 'download_single_doi_mode'):
        download_single_doi(config.get_string('general', 'download_single_doi'))
        return None
        # above line used to be "sys.exit(0)", but it prevents sphinx autodoc from working

    if config.get_boolean('general', 'retry_failed_unpaywall_links'):
        retry_failed_unpaywall_links(config)
        return None
        # above line used to be "sys.exit(0)", but it prevents sphinx autodoc from working

    # below line prints/logs lines such as
    # "Downloading Arthropod-Plant Interactions issn: 1872-8855 starting year: 2016 
    # ending year 2016 Type: print" regardless of config.ini settings
    db = DoiDatabase(config,
                     config.get_int('crossref', 'scan_for_dois_after_year'),
                     config.get_int('crossref', 'scan_for_dois_before_year'))
    if config.get_boolean('general', 'write_used_journals'):
        print("Writing to journals table")
        db.write_journals_to_tsv(config.get_string('general', 'used_journals_only_file'))
    if config.get_boolean('crossref', 'force_update'):
        print("CROSSREF FORCE INGEST")

        db.force_crossref_update(config.get_int('crossref', 'force_update_year'))

    if config.get_boolean('general', 'report_on_start'):
        print("GENERATE DATABASE REPORT BEFORE START")

        report_start_year = config.get_int('general', 'report_start_year')
        report_end_year = config.get_int('general', 'report_end_year')
        report = DatabaseReport(db, report_start_year, report_end_year, issn=None)
        logging.info(report.report())
        if config.get_boolean('general', 'exit_after_report'):
            raise SystemExit(0)
            # above line used to be "sys.exit(0)", but it prevents sphinx autodoc from working

    download_start_year = config.get_int('download', 'download_start_year')
    download_end_year = config.get_int('download', 'download_end_year')

    # Checks if an DOI's associated PDF file exists, then updates the database
    if config.get_boolean('download', 'update_pdf_file_link'):
        print("Verifying PDF files against doi database and updating all records - this is slow!")
        db.update_doi_pdf_downloaded_status_per_year(download_start_year, download_end_year)

    if config.get_boolean('download', 'download_single_journal'):
        print("DOWNLOAD SINGLE JOURNAL TEST MODE")
        db.download_dois(download_start_year, download_end_year,
                         journal=None,
                         issn=config.get_string('download', 'download_single_journal_issn'))

    if config.get_boolean('download', 'enable_paper_download'):
        print("DOWNLOADING PAPERS")
        db.download_dois_by_journal_size(download_start_year, download_end_year)
    else:
        print("Skipping downloading papers...")

    reset_scan_database = config.get_boolean('scan', 'reset_scan_database')

    if config.get_boolean('scan', 'enabled'):
        print("STARTING SCAN")
        scan_db = ScanDatabase(db, reset_scan_database=reset_scan_database)

        scan_start_year = config.get_int('scan', 'scan_start_year')
        scan_end_year = config.get_int('scan', 'scan_end_year')
        rescore = config.get_boolean('scan', 'rescore')
        # parallelize = config.get_boolean('scan', 'parallelize')

        scan_db.scan_pdfs(scan_start_year, scan_end_year, rescore=rescore)








    if config.get_boolean('scan_for_specimen_ids', 'enabled'):
        print("Scan for specimen ids...")
        scan_db = ScanDatabase(db, reset_scan_database=reset_scan_database)

        reset_scan_id_database = config.get_boolean('scan_for_specimen_ids', 'reset_scan_database')
        if reset_scan_database:
            print("Resetting specimen id scan tables...")
        scan_db.scan_for_specimen_ids(reset_tables=reset_scan_id_database)

    validate_enabled = config.get_boolean('validate', 'enabled')

    if validate_enabled:

        validate_start_year = config.get_int('validate', 'validate_start_year')
        validate_end_year = config.get_int('validate', 'validate_end_year')
        validator = Validator()
        regular_prompts = config.get_boolean('validate', 'regular_prompts')
        if regular_prompts:
            validator.audit(validate_start_year, validate_end_year)
        digital_prompts = config.get_boolean('validate', 'digital_prompts')
        # doesn't work until the regular validation sequence is completed.
        if digital_prompts:
            validator.audit_digital_only(validate_start_year, validate_end_year)

    copyout_enabled = config.get_boolean('copyout', 'enabled')
    if copyout_enabled:
        copyout_start_year = config.get_int('copyout', 'copyout_start_year')
        copyout_end_year = config.get_int('copyout', 'copyout_end_year')
        target_dir = config.get_string('copyout', 'target_dir')

        for cur_year in range(copyout_start_year, copyout_end_year + 1):
            logging.info(f"Exporting year {cur_year}")
            copyout = CopyOut(cur_year, config)
            if config.get_boolean('copyout', 'copyout_pdfs'):
                copyout.copy_out_files(target_dir)
            if config.get_boolean('copyout', 'export_tsv'):
                copyout.dump_file_tsv(target_dir)
                copyout.dump_custom("antcat", target_dir)
                copyout.dump_custom("antweb", target_dir)
                copyout.dump_custom("inaturalist", target_dir)
                copyout.dump_custom("catalog of fishes", target_dir)

        # validator.copy_matches("2016_found")

        # dynamic = scan_db.scan_single_doi('10.11646/zootaxa.4205.2.2')
        # logging.info(f"Score: {dynamic}")
        # sys.exit(1)
        #
        # test_known_good(db)

        return
    # above line used to be "sys.exit(1)", but it prevents sphinx autodoc from working


#  testing code - we generate a set of known good papers and test our algorithms against it.
# Hasn't been validated since the re-org, not currently run.
def test_known_good(db):
    scan_db = ScanDatabase(db, reset_scan_database=False)
    scan_associations = KnownGoodPapers()
    # scan_associations.associate_title_file("herp-2016.csv",year,year)
    test_dois = scan_associations.get_associated_dois()
    validator = Validator(run_audit=False)

    test_dois = test_dois + validator.get_matched_paper_dois()
    known_good_scans = []
    for doi in test_dois:
        logging.info(f"Scnning doi: {doi}")
        try:
            Scan.clear_db_entry(doi)
            scan = scan_db.scan_single_doi(doi)
            logging.info(f"Score: {scan.score} doi: {doi} title: {scan.title}")
            known_good_scans.append(scan)
        except FileNotFoundError:
            logging.warning("cannot download; skipping.")

    file = open("known_good.tsv", "w")
    for scan in known_good_scans:
        results = f"{scan.score}\t{scan.textfile_path}\t{scan.doi_string}\t{scan.title}"
        results = results.replace('\"', '\'')
        file.write(results + "\n")


if __name__ == '__main__':
    config = Config()
    logging_level = config.get_string('general', 'logging_level')
    logging.basicConfig(level=eval(f"logging.{logging_level}"), format='%(message)s')
    setup()

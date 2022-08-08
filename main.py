from doi_entry import DoiFactory
import sys
from doi_database import DoiDatabase
from database_report import DatabaseReport
from scan_database import ScanDatabase
from known_good_papers import KnownGoodPapers
from scan import Scan
from validator import Validator
from config import Config
from downloaders import Downloaders
from copyout import CopyOut
from crossref_journal_entry import CrossrefJournalEntry


def download_single_doi(doi, config):
    print("Single DOI download mode")
    select_doi = f"""select * from dois where doi='{doi}'"""
    doif = DoiFactory(select_doi)
    doi_list = doif.dois
    if len(doi_list) == 0:
        print(f"Single download failed - DOI not in system: {select_doi} ")
        sys.exit(1)
    downloaders = Downloaders()

    for doi_entry in doi_list:
        downloaders.download(doi_entry)


def retry_failed_unpaywall_links(config):
    print("Retrying failed unpaywall downloads")
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
    config = Config()
    setup_tables()

    if config.get_boolean('general', 'download_single_doi_mode'):
        download_single_doi(config.get_string('general', 'download_single_doi'), config)
        sys.exit(0)

    if config.get_boolean('general', 'retry_failed_unpaywall_links'):
        retry_failed_unpaywall_links(config)
        sys.exit(0)
    
    if config.get_boolean('general', 'do_pdf_ingest'):
        pdf_dir = config.get_string('general', 'pdf_ingest_directory')
        d = DoiDatabase()
        d.import_pdfs(pdf_dir, False)

    db = DoiDatabase(config.get_int('crossref', 'scan_for_dois_after_year'),
                     config.get_int('crossref', 'scan_for_dois_before_year'))
    if config.get_boolean('crossref', 'force_update'):
        db.force_crossref_update(config.get_int('crossref', 'force_update_year'))
    if config.get_boolean('general', 'report_on_start'):
        report_start_year = config.get_int('general', 'report_start_year')
        report_end_year = config.get_int('general', 'report_end_year')
        report = DatabaseReport(report_start_year, report_end_year, journal=None)
        print(report.report())
        if config.get_boolean('general', 'exit_after_report'):
            sys.exit(0)

    # joe tie to config
    db.ensure_downloaded_has_pdf(2020, 2022)

    verify_start_year = config.get_int('verify', 'verify_start_year')
    verify_end_year = config.get_int('verify', 'verify_end_year')

    if config.get_boolean('verify', 'verify_single_journal'):
        db.verify_dois(verify_start_year, verify_end_year,
                       journal=config.get_string('verify', 'verify_single_journal_issn'))

    if config.get_boolean('verify', 'verify_all_journals'):
        db.verify_dois_by_journal_size(verify_start_year, verify_end_year)

    if config.get_boolean('scan', 'enabled'):
        scan_start_year = config.get_int('scan', 'scan_start_year')
        scan_end_year = config.get_int('scan', 'scan_end_year')
        rescore = config.get_boolean('scan', 'rescore')
        reset_scan_database = config.get_boolean('scan', 'reset_scan_database')
        scan_db = ScanDatabase(db, reset_scan_database=reset_scan_database)
        scan_db.scan_pdfs(scan_start_year, scan_end_year, rescore=rescore)

        if config.get_boolean('scan_for_colleciton_ids', 'enabled'):
            reset_scan_database = config.get_boolean('scan', 'reset_scan_database')

            scan_db.scan_for_collection_ids(reset_tables=reset_scan_database)

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
            print(f"Exporting year {cur_year}")
            copyout = CopyOut(cur_year)
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
    # print(f"Score: {dynamic}")
    # sys.exit(1)
    #
    # test_known_good(db)

    sys.exit(1)


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
        print(f"Scnning doi: {doi}")
        try:
            Scan.clear_db_entry(doi)
            scan = scan_db.scan_single_doi(doi)
            print(f"Score: {scan.score} doi: {doi} title: {scan.title}")
            known_good_scans.append(scan)
        except FileNotFoundError:
            print("cannot download; skipping.")

    file = open("known_good.tsv", "w")
    for scan in known_good_scans:
        results = f"{scan.score}\t{scan.textfile_path}\t{scan.doi_string}\t{scan.title}"
        results = results.replace('\"', '\'')
        file.write(results + "\n")


if __name__ == '__main__':
    setup()

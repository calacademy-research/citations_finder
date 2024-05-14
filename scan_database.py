from db_connection import DBConnection
from scan import Scan
from utils_mixin import Utils
from doi_database import DoiFactory
import logging
import random
from scan import RecordNotFoundException
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
import os

class ScanDatabase(Utils):

    # "reset" causes a the whole scan database to be rebuilt.
    # required most of the time; it won't pick up new PDFs without it
    # TODO: Command to scan all elements to ensure they have a scan object (7/7/22: this meant
    # something to me when I wrote it, but no clue now. Expand or remove this comment.)
    def __init__(self, doi_db, reset_scan_database=False):
        super().__init__()
        if reset_scan_database:
            logging.info ("Resetting scan database...")
            self.create_tables(reset_scan_database)
        self.doi_db = doi_db

    def __str__(self):
        if self.cannot_convert is not False:
            return (f"doi: {self.doi} Score: {self.score} title: {self.title}")
        else:
            return (f"doi: {self.doi} Score: CONVERSION FAILURE title: {self.title}")

    @classmethod
    def create_tables(self, reset_tables=False):
        """Creates two database tables: "scans" and "found_scan_lines". 
        It also includes an optional parameter reset_tables to determine 
        whether existing tables should be dropped before creating new ones

        :param reset_tables: determine whether existing tables should be 
        dropped before creating new ones, defaults to False
        :type reset_tables: bool, optional
        """        
        if reset_tables:
            try:
                sql = "drop table scans"
                DBConnection.execute_query(sql)
            except Exception:
                pass
            try:

                sql = "drop table found_scan_lines"
                DBConnection.execute_query(sql)
            except Exception:
                pass

        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS scans (
                                            doi varchar(255) primary key not null,
                                            textfile_path varchar(2048),
                                            score integer,
                                            cannot_convert boolean,
                                            title varchar(8192) NOT NULL
                                        ); """
        DBConnection.execute_query(sql_create_database_table)

        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS found_scan_lines (
                                            doi varchar(255),
                                            line varchar(8192),
                                            score integer,
                                            matched_string varchar(1024)
                                        ); """
        DBConnection.execute_query(sql_create_database_table)

    def scan_single_doi(self, doi):
        scan = Scan(doi_string=doi)
        scan.scan(clear_existing_records=True)
        return scan

    def do_scan(self, doi):
        """Performs a scan on the provided DOI using the Scan class in scan.py

        :param doi: DOI
        :type doi: str
        """        
        scan = Scan(doi)
        if scan.score is None:
            if scan.broken_converter is not True:
                scan.scan()

    def process_doi(self, doi_entry):
        logging.debug(f"Scanning doi: {doi_entry.doi}")
        try:
            scan = Scan(doi_string=doi_entry.doi)
            scan.scan(clear_existing_records=True)
        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")
        except Exception as e:
            logging.error(f"Error processing DOI {doi_entry.doi}: {e}")

    def scan_pdfs(self, start_year, end_year, rescore=False, directory="./"):
        """Scans PDFs for DOIs within the specified year range. It retrieves DOIs that 
        have been downloaded but not yet scanned.

        :param start_year: The starting year of the range for which PDFs should be scanned.
        :type start_year: int

        :param end_year: The ending year of the range for which PDFs should be scanned.
        :type end_year: int

        :param rescore: Flag indicating whether to rescore previously scanned DOIs, defaults to False.
        :type rescore: bool, optional

        :param directory: The directory where the scanned PDFs should be saved, defaults to "./".
        :type directory: str, optional
        """

        batch_size = 500
        offset = 0
        total_dois_processed = 0
        num_workers = os.cpu_count()  # Number of CPUs for parallel processing
        max_workers = self.config.get_int('scan','max_pdf_conversion_threads')
        logging.info("Loading entries from database...")
        num_workers = max(num_workers,max_workers)
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            while True:
                if not rescore:
                    sql = self.doi_db.generate_select_sql(start_year, end_year, None, True, batch_size, offset)
                    dois = DoiFactory(sql).dois
                else:
                    dois = self.doi_db.get_dois(start_year=start_year, end_year=end_year, journal_issn=None,
                                                downloaded=True, limit=batch_size, offset=offset)

                if not dois:
                    break  # No more DOIs to process
                random.shuffle(dois)

                # Submit DOIs to the executor for processing
                future_to_doi = {executor.submit(self.process_doi, doi_entry): doi_entry for doi_entry in dois}

                # Process future results as they complete
                for future in as_completed(future_to_doi):
                    try:
                        future.result()  # Wait for the result to make sure no exceptions are thrown
                    except Exception as exc:
                        doi_entry = future_to_doi[future]
                        logging.error(f"DOI {doi_entry.doi} generated an exception: {exc}")

                total_dois_processed += len(dois)
                offset += batch_size
                logging.info(f"Processed {total_dois_processed} DOIs so far")


        logging.info("All DOIs processed")


    def scan_for_specimen_ids(self, reset_tables=False):
        """Scans for specimen IDs in the matched documents and stores them in 
        the database table 'matched_specimen_ids'.

        :param reset_tables: If True, drops the 'matched_specimen_ids' table 
        and recreates it, defaults to False.
        :type reset_tables: bool, optional
        """        
        if reset_tables:
            sql = "drop table matched_specimen_ids"
            DBConnection.execute_query(sql)

        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS matched_specimen_ids (
                                            doi varchar(255),
                                            identifier varchar(1024)
                                        ); """
        DBConnection.execute_query(sql_create_database_table)
        select_dois = f"""select doi from matches where skip = 0"""
        matched_dois = DBConnection.execute_query(select_dois)
        for doi in matched_dois:
            doi = doi[0]
            try:
                scan = Scan(doi_string=doi)
            except RecordNotFoundException:
                print(f" Can't locate DOI in scan database: {doi}, skipping...")
                continue
            if scan.textfile_path is None:
                print(f" Never converted txt file for doi {doi}, pdf: {scan.doi_object.full_path}")
                continue
            print(f"Scanning: {scan._get_textfile_path()}")
            results = scan.scan_specimen_ids()
            if results:
                logging.info(f"Title: {scan.title}")
                for result in results:
                    sql_insert = f"""insert into matched_specimen_ids (doi, identifier) VALUES (%s,%s)"""
                    result = result.strip()
                    if result.startswith("("):
                        result = result[1:]
                    args = [doi,
                            result]
                    DBConnection.execute_query(sql_insert, args)
                    # if '-' in result:
                    #     logging.debug(f"doi: {doi} title: {scan.title}")
                    #     logging.debug(f" Got bad: {result}")





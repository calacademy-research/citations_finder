import os

import requests.exceptions

from doi_entry import DoiEntry
from doi_entry import DoiFactory
from utils_mixin import Utils
import glob
import urllib
import time
import csv
from crossref_journal_entry import CrossrefJournalEntry
from doi_entry import EntryExistsException
from db_connection import DBConnection
from database_report import DatabaseReport
from downloaders import Downloaders
from scan_database import ScanDatabase
from validator import Validator

from datetime import date
import logging

class RetriesExceededException(Exception):
    pass


class DoiDatabase(Utils):
    headers = {
        'User-Agent': 'development; mailto:jrussack@calacademy.org',
    }

    # "do_setup" creates the db tables (if they don't exist) and polls crossref.org for
    # the journals listed in journals.tsv. If the PDF already exists
    # then the full path is updated.
    #
    # "do_download" scans through all DOI records. If the PDF is already
    # downloaded, it populates the record accordingly.
    def __init__(self,
                 start_year=None,
                 end_year=None):
        super().__init__()

        self._setup()
        if start_year is not None:
            assert end_year is not None, "If scanning must provide both a start and an end year"
            self._query_journals(start_year, end_year)

    def _setup(self):
        """Creates seven SQL database tables 
        """        
        CrossrefJournalEntry.create_tables()
        DoiEntry.create_tables()
        ScanDatabase.create_tables()
        Validator.create_tables()


    def _query_journals(self, start_year, end_year):
        """Queries crossref for the history of the journal in question.
        Crossref returns all records starting at the start_year until the 
        most recent year. Both are defined in config.ini -> [crossref] ->
        'scan_for_dois_after_year' AND 'scan_for_dois_before_year'

        Updates the table "journals" with the "start year" and "end_year" 
        passed in here. Journals table doesn't get an 
        entry until an attempt to query DOIs from crossref has happened.

        :param start_year: Start year of journal
        :type start_year: int
        :param end_year: End year of journal
        :type end_year: int
        """        
        with open('journals.tsv', 'r') as tsvin:
            for line in csv.reader(tsvin, delimiter='\t'):
                try:
                    if len(line) == 0 or line[0].startswith('#'):
                        continue
                    issn = line[0]
                    if issn.startswith("not in crossref"):
                        logging.warning("Not in crossref, continuing.")
                        continue
                    journal = line[1]
                    type = None
                    if len(line) > 2:
                        type = line[2]
                except Exception as e:
                    logging.warning(f"Parsing error: {line}, skipping.")
                    continue

                logging.info(f"Downloading {journal} issn: {issn} starting year: {start_year} ending year {end_year}")
                if type is None:
                    logging.info("")
                else:
                    logging.info(f" Type: {type}")

                if self._check_journal_record(issn, start_year):
                    self.download_issn(issn, start_year, end_year)
                    self._update_journal_record(issn, start_year, journal, type)

    def force_crossref_update(self, start_year):
        """ Retrieves journals from the database and performs a forced update
        for the specified `start_year` defined in config.ini 'force_update_year = xxxx' 
        by downloading data from Crossref  
        

        :param start_year: The start year for the update, defined in config.ini as 'force_update_year = xxxx'
        :type start_year: int
        """        
        end_year = start_year
        query = f"select issn,name,type from journals"
        results = DBConnection.execute_query(query)
        for journal in results:
            issn = journal[0]
            name = journal[1]
            type = journal[2]
            self.download_issn(issn, start_year, end_year)
            self._update_journal_record(issn, start_year, name, type)

    def _get_issn_oldest_year(self, issn):
        """In 'journals' table in database, each issn # / journal name 
        has a start_year and end_year assigned. This method 
        retrieves the start_year value by SQL query

        :param issn: issn number
        :type issn: str
        :return: The start_year of issn # / journal name 
        :rtype: int
        """        
        query = f"select start_year from journals where issn=\"{issn}\""
        results = DBConnection.execute_query(query)

        if len(results) >= 1:
            return int(results[0][0])
        else:
            return None

    def _check_journal_record(self, issn, start_year):
        """Returns True if the journal needs to be downloaded

        :param issn: ISSN number
        :type issn: str
        :param start_year: The start year of the journal
        :type start_year: int
        :return: True if journal needs to be downloaded (when old_year_downloaded
        on record is more recent than passed start_year)
        :rtype: bool
        """
        oldest_year_downloaded = self._get_issn_oldest_year(issn)
        if oldest_year_downloaded is None or (oldest_year_downloaded > start_year):
            return True
        return False

    def _update_journal_record(self, issn, start_year, name, type):
        """Update or insert a line in the database -> 'journals' table, 
        with new start_year, if previous_start_year is None or is more recent(greater) 
        than new start_year

        :param issn: ISSN number
        :type issn: str
        :param start_year: The start year of the journal
        :type start_year: int
        :param name: The name of the journal
        :type name: str
        :param type: the type of the journal, either 'online' or 'print'
        :type type: str
        """        
        previous_start_year = self._get_issn_oldest_year(issn)
        if previous_start_year is None or previous_start_year > start_year:
            # Below line "escapes the quotes". In SQL, single quotes are used to 
            # enclose string values in SQL queries. "Escaping quotes" allowing 
            # the string to be included in the SQL query without causing issues.
            name = name.replace("'", "''")
            logging.info(f"{issn}\t{name}\t{type}")
            sql = f"INSERT OR REPLACE INTO journals (issn,name, type,start_year,end_year) VALUES ('{issn}','{name}','{type}',{start_year},{date.today().year})"

            results = DBConnection.execute_query(sql)

    # not referenced anywhere at present; invoke from main per README

    # Scans through existing PDFs in the directory
    # If they're present, create or update the DoiEntry
    # in the database.

    # Inefficent; single request to crossref.org to get metadata for one pub.
    # it's better to run download_issn for the journal of interest and the run
    # import_pdfs. If the pdfs are of unknown or mixed provenance, then this
    # is the way to go.

    def import_pdfs(self, directory="./", raise_exception_if_exist=True):
        """ Import PDFs and build database entries based on their metadata.

        :param directory: The directory path where the PDF files are located, defaults to "./"
        :type directory: str, optional

        :param raise_exception_if_exist: Flag indicating whether to raise an exception if the DOI already exists in the database, defaults to True
        :type raise_exception_if_exist: bool, optional
        """        
        pdf_files = glob.glob(os.path.join(directory, "*.pdf"))
        total_count = 0
        for pdf_file in pdf_files:
            doi_string = self.get_doi_from_path(pdf_file)
            base_url = f"https://api.crossref.org/works/{doi_string}"

            logging.info(f"Querying crossref.org for metadata to build db: {base_url}")
            results = self._get_url_(base_url)
            item = results['message']
            if raise_exception_if_exist:
                DoiEntry('import_pdfs', item)
            else:
                try:
                    DoiEntry('import_pdfs', item)
                except EntryExistsException as e:
                    logging.info(f"DOI already in database, skipping: {e}")
            total_count += 1
            if total_count % 10 == 0:
                logging.info(f"Done {total_count} out of {len(pdf_files)}")

    def download_dois_by_journal_size(self,
                                    start_year,
                                    end_year):
        """ Selects journals with a specified time range and retrieves a list of journals
        along with their ISSN and the number of DOIs associated with each journal. It then proceeds 
        to attempt downloads for each journal based on their size, i.e., the number of DOIs they have,
        from journal with least DOIs to most DOIs

        :param start_year: The start year for the time range to consider.
        :type start_year: int
        :param end_year: The end year for the time range to consider.
        :type end_year: int
        """        
        sql = f'''SELECT journal_title,issn,count(doi)
                FROM dois
                where {self.sql_year_restriction(start_year, end_year)}
                and downloaded = False 
                GROUP BY journal_title
                ORDER BY COUNT(doi) ASC'''

        journals = DBConnection.execute_query(sql)
        for journal, issn, doi_count in journals:
            # journal = journal[0]
            # issn = journal[1]
            logging.info(f"Attempting downloads for journal: {journal}:{issn}")
            report = DatabaseReport(start_year, end_year, journal)
            logging.info("\n")
            logging.info(report.report(journal=journal, issn=issn, summary=False))
            self.download_dois(start_year, end_year, journal=journal, issn=issn)

    def _generate_select_sql(self, start_year, end_year, journal_issn, downloaded="FALSE"):
        """Generate an SQL query to select DOI entries from the database -> dois table

        :param start_year: The starting year of the date range for DOI entries selection.
        :type start_year: int
        :param end_year: The ending year of the date range for DOI entries selection.
        :type end_year: int
        :param journal_issn: The ISSN (International Standard Serial Number) of the journal
        for DOI entries filtering.
        :type journal_issn: str
        :param downloaded: The downloaded status to be used in the selection criteria,
        defaults to "FALSE".
        :type downloaded: str, optional
        :return: The SQL query for selecting DOI entries based on the provided criteria.
        :rtype: str
        """        
        select_dois = f"""select * from dois where downloaded={downloaded} """

        if start_year is not None and end_year is not None:
            select_dois += f""" and  {self.sql_year_restriction(start_year, end_year)}"""
        if journal_issn is not None:
            select_dois += f' and issn="{journal_issn}"'
        return select_dois

    def get_dois(self, start_year, end_year, journal_issn=None):
        """Get DOI entries from the database where downloaded column is marked as True
          within the specified date range


        :param start_year: The starting year of the date range.
        :type start_year: int
        :param end_year: The ending year of the date range.
        :type end_year: int
        :param journal_issn: The ISSN (International Standard Serial Number) of the journal to filter the results, defaults to None.
        :type journal_issn: str, optional
        :return: A list of DOI entries that match the specified criteria.
        :rtype: List[DoiEntry]
        """        
        sql = self._generate_select_sql(start_year, end_year, journal_issn, "TRUE")
        dois = DoiFactory(sql).dois
        return dois

    def get_doi(self, doi):
        sql = f"select * from dois where doi = '{doi}'"
        doi = DoiFactory(sql).dois
        if len(doi) != 1:
            raise FileNotFoundError(f"No such doi: {doi} or multiple results")
        return doi[0]

    def ensure_downloaded_has_pdf(self, start_year, end_year):
        """Checks if an DOI's associated PDF file exists, then updates the database

        :param start_year: The starting year of the date range.
        :type start_year: int
        :param end_year: The ending year of the date range.
        :type end_year: int
        """        
        dois = self.get_dois(start_year, end_year)
        for doi_entry in dois:
            doi_entry_instance = DoiEntry(doi_entry)
            doi_entry_instance.check_file()
            doi_entry_instance.update_database()

    # Ensures that all DOIs in the database have associated files
    # Download, if not.

    def download_dois(self,
                    start_year,
                    end_year,
                    journal,
                    issn):
        """Download DOI entries based on specified criteria.

        
        It first generates an SQL query to select the DOI entries from the database based on
        the given start year, end year, and ISSN (International Standard Serial Number).
        It then creates an instance of the Downloaders class to handle the downloading process.

        :param start_year: The starting year of the date range for selecting DOI entries.
        :type start_year: int
        :param end_year: The ending year of the date range for selecting DOI entries.
        :type end_year: int
        :param journal: The journal name used as a filter for DOI entries, or None for all journals.
        :type journal: str or None
        :param issn: The ISSN (International Standard Serial Number) used as a filter for DOI entries. If True, the ISSN will be used to filter DOI entries; if False, it will not be used for filtering.
        :type issn: bool
        """        
        select_dois = self._generate_select_sql(start_year, end_year, issn)
        downloaders = Downloaders()

        doif = DoiFactory(select_dois)
        dois = doif.dois
        logging.info(f"SQL: {select_dois}")
        logging.info(f"  Pending download count: {len(dois)}")
        download_list = []
        for doi_entry in dois:
            if journal is None or doi_entry.issn == issn:
                download_list.append(doi_entry)

        downloaders.download_list(download_list)

    def is_downloaded(self, doi_entry):
        return doi_entry.downloaded

    def download_issn(self, issn, start_year, end_year):
        """    Download data for a specific ISSN from a given start year to an end year
        using crossref API. The downloaded data is not explicitly stored or saved to a 
        specific location.


        :param issn: The ISSN of the journal
        :type issn: str
        :param start_year: The start year for filtering the data
        :type start_year: str
        :param end_year: The end year for filtering the data
        :type end_year: str
        """        
        base_url = f"https://api.crossref.org/journals/{issn}/works?filter=from-pub-date:{start_year},until-pub-date:{end_year}&rows=1000&cursor="
        cursor = "*"
        done = False
        total_items_processed = 0
        total_results = 0
        logging.info(f"Processing issn:{issn}")
        while not done:
            try:
                cursor, total_results, items_processed = self._download_chunk(base_url, cursor, start_year)
                total_items_processed += items_processed
                logging.info("Continuing...")
            except ConnectionError:
                if total_items_processed >= total_results:
                    done = True
                    logging.info("Done.")
                else:
                    logging.info("retrying....")
            except RetriesExceededException as rex:
                logging.info(f"Retries exceeded: {rex}, aborting.")
                return

    def _handle_connection_error(self, retries, max_retries, url, cursor, start_year, e):
        """    Handles connection errors during downloading.

        :param retries: The number of retries attempted.
        :type retries: int
        :param max_retries: The maximum number of retries allowed.
        :type max_retries: int
        :param url: The URL of the resource being downloaded.
        :type url: str
        :param cursor: The cursor or pointer indicating the current position in the resource.
        :type cursor: int
        :param start_year: The start year of the resource.
        :type start_year: int
        :param e: The connection error that occurred.
        :type e: Exception
        :raises RetriesExceededException: If the maximum number of retries is exceeded.
        :return: The result of the _download_chunk function call.
        :rtype: Result of _download_chunk function call.
        """        
        logging.info(f"Connection error: {e}, retries: {retries}. Sleeping 60 and retrying.")
        time.sleep(60)
        if retries >= max_retries:
            raise RetriesExceededException(f"Retried {retries} times, aborting.")
        return self._download_chunk(url, cursor, start_year, retries)

    def _download_chunk(self, url, cursor, start_year, retries=0):
        """First, download data using url and store in 'results'. From results, get 'message', 
        'items', and 'total-results'.
        Second, loop through all items. If item type is 'journal', run CrossrefJournalEntry. 
        Else if item type is 'journal-article", run DoiEntry. If item type is anything else, pass for now.
        Third, check number of items. If no items, raise ConnectionError exception. If there are items, 
        logs a message indicating the number of items processed.
        Lastly, return the tuple consisted of 'message['next-cursor'], total_results, items_processed'

        :param url: The URL (crossref api) to download the data from
        :type url: str
        :param cursor: The cursor for pagination
        :type cursor: str
        :param start_year: The start year for filtering the data
        :type start_year: str
        :param retries:  The number of retries attempted, defaults to 0
        :type retries: int, optional
        :raises ConnectionError: Raises a ConnectionError if a connection error occurs
        :return: The 'next cursor' value, message['total-results'], and number of items processed.
        :rtype: Tuple[str, dict(not sure about this), int]
        
        """        
        max_retries = 3
        safe_cursor = urllib.parse.quote(cursor, safe="")
        try:
            results = self._get_url_(url + safe_cursor, self.headers)
        except ConnectionError as e:
            retries += 1
            return self._handle_connection_error(retries, max_retries, url, cursor, start_year, e)
        except requests.exceptions.ConnectionError as e:
            retries += 1
            return self._handle_connection_error(retries, max_retries, url, cursor, start_year, e)

        logging.info(f"Querying: {url + safe_cursor}")
        message = results['message']
        items = message['items']
        total_results = message['total-results']
        items_processed = 0
        for item in items:
            items_processed += 1
            # logging.info(f"Processing DOI: {item['DOI']}")
            type = item['type']
            if type == 'journal':
                CrossrefJournalEntry(item)
            elif type == "journal-article":
                try:
                    DoiEntry('download_chunk', item)
                except EntryExistsException as e:
                    # logging.warning(f"DOI already in database, skipping: {e}")
                    logging.info(".")
            else:
                # "journal-issue"
                # logging.info(f"got type: {type}")
                pass

        if len(items) == 0:
            logging.error("No items left.")
            raise ConnectionError()
        else:
            logging.info(f"Processed {len(items)} items")
        return message['next-cursor'], total_results, items_processed

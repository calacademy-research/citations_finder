import os

import requests.exceptions

from doi_entry import DoiEntry
from doi_entry import DoiFactory
from utils_mixin import Utils
import random
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
import json
from datetime import datetime

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
                 config,
                 start_year=None,
                 end_year=None):
        super().__init__()
        self.config = config

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

    def _print_journal_actions(self, issn, check_year, journal, type):
        """Prints the intended actions for a journal record."""

        if self._is_year_downloaded(issn, check_year):
            logging.info(f"Will require download: {issn}, year: {check_year}, journal: {journal}, type: {type}")
        else:
            logging.info(f"  Already downloaded: {issn}, year: {check_year}, journal: {journal}, type: {type}")


    def _execute_journal_actions(self, issn, check_year, journal, type):
        """Executes the actions for a journal record."""

        if not self._is_year_downloaded(issn, check_year):
            logging.info(f"Downloading {journal} issn: {issn} year: {check_year}")
            if type is None:
                logging.info("")
            else:
                logging.info(f" Type: {type}")
            self.download_issn(issn, check_year, check_year)
            self._update_journal_record(issn, journal, type)

    def _query_journals_tsv(self, start_year, end_year, operation):
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

                for year in range(start_year, end_year + 1):
                    check_year = str(year)
                    operation(issn, check_year, journal, type)


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
        skip_crossref = self.config.get_boolean('crossref', 'skip_crossref')
        if skip_crossref:
            logging.info("Skipping crossref check and doi download step...")
            return
        skip_crossref_precheck = self.config.get_boolean('crossref', 'skip_crossref_precheck')

        if not skip_crossref_precheck:
            self._query_journals_tsv(start_year,end_year, self._print_journal_actions)
        self._query_journals_tsv(start_year,end_year, self._execute_journal_actions)

                # if self._check_journal_record(issn, start_year):
                #     self.download_issn(issn, start_year, end_year)
                #     self._update_journal_record(issn, start_year, journal, type)

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
            self._update_journal_record(issn, name, type)

    def _is_year_downloaded(self, issn, year):
        """Check if there are any DOI entries for the given ISSN in the specified year.
        If so, we assume the entire year is downloded.

        :param issn: ISSN number.
        :type issn: str
        :param year: Year to check for DOI entries.
        :type year: int
        :return: True if there are DOI entries in the specified year, False otherwise.
        :rtype: bool
        """
        query = f"""
        SELECT COUNT(*) FROM collections_papers.dois
        WHERE issn = \"{issn}\" AND YEAR(published_date) = {year}
        """
        results = DBConnection.execute_query(query)

        if len(results) >= 1 and results[0][0] > 0:
            return True
        else:
            return False

    def _update_journal_record(self, issn, name, type):
        """
        ensure journal record is present in the database

        :param issn: ISSN number
        :type issn: str
        :param name: The name of the journal
        :type name: str
        :param type: the type of the journal, either 'online' or 'print'
        :type type: str
        """
        name = name.replace("'", "''")
        logging.info(f"{issn}\t{name}\t{type}")
        sql = f"REPLACE INTO journals (issn,name, type) VALUES ('{issn}','{name}','{type}')"

        results = DBConnection.execute_query(sql)


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

        sql = f'''SELECT journal_title, issn, count(doi)
                  FROM dois
                  WHERE {self.sql_year_restriction(start_year, end_year)}
                  AND downloaded = False
                  GROUP BY journal_title, issn
                  ORDER BY COUNT(doi) ASC'''
        journals = DBConnection.execute_query(sql)
        suppress_journal_report_header = self.config.get_boolean("downloaders","suppress_journal_report_header")

        randomize = self.config.get_boolean("downloaders","randomize_download_order")
        if randomize:
            random.shuffle(journals)

        for journal, issn, doi_count in journals:
            # journal = journal[0]
            # issn = journal[1]
            logging.info(f"Attempting downloads for journal: {journal}:{issn}")
            if not suppress_journal_report_header:
                report = DatabaseReport(self, start_year, end_year, journal)
                logging.info("\n")
                logging.info(report.report(journal=issn, summary=False))
            self.download_dois(start_year, end_year, journal=journal, issn=issn)

    def _generate_select_sql(self, start_year, end_year, journal_issn, downloaded):
        """Generate an SQL query to select DOI entries from the database -> dois table.

        :param start_year: The starting year of the date range for DOI entries selection.
        :type start_year: int
        :param end_year: The ending year of the date range for DOI entries selection.
        :type end_year: int
        :param journal_issn: The ISSN (International Standard Serial Number) of the journal
                             for DOI entries filtering.
        :type journal_issn: str
        :param downloaded: The downloaded status to be used in the selection criteria.
                           Can be True, False, or None. If None, the downloaded status
                           is not included in the criteria.
        :type downloaded: bool or None
        :return: The SQL query for selecting DOI entries based on the provided criteria.
        :rtype: str
        """

        conditions = []

        if downloaded is not None:
            downloaded_value = "TRUE" if downloaded else "FALSE"
            conditions.append(f"downloaded = {downloaded_value}")

        if start_year is not None and end_year is not None:
            conditions.append(self.sql_year_restriction(start_year, end_year))

        if journal_issn is not None:
            conditions.append(f'issn = "{journal_issn}"')

        where_clause = " where " + " and ".join(conditions) if conditions else ""

        select_dois = f"select * from dois{where_clause}"

        return select_dois

    def get_dois(self, start_year, end_year, journal_issn=None, downloaded=True):
        """Get DOI entries from the database within the specified date range
         downloaded can be true, false, or none. Clause will be removed in the "none" case.

        :param start_year: The starting year of the date range.
        :type start_year: int
        :param end_year: The ending year of the date range.
        :type end_year: int
        :param journal_issn: The ISSN (International Standard Serial Number) of the journal to filter the results, defaults to None.
        :type journal_issn: str, optional
        :return: A list of DOI entries that match the specified criteria.
        :rtype: List[DoiEntry]
        """

        sql = self._generate_select_sql(start_year, end_year, journal_issn, downloaded)
        dois = DoiFactory(sql).dois
        return dois

    def get_doi(self, doi):
        sql = f"select * from dois where doi = '{doi}'"
        doi = DoiFactory(sql).dois
        if len(doi) != 1:
            raise FileNotFoundError(f"No such doi: {doi} or multiple results")
        return doi[0]

    def update_doi_pdf_downloded_status(self, start_year, end_year):
        """Checks if an DOI's associated PDF file exists, then updates the database

        :param start_year: The starting year of the date range.
        :type start_year: int
        :param end_year: The ending year of the date range.
        :type end_year: int
        """        
        dois = self.get_dois(start_year, end_year, downloaded=None)
        total_dois = len(dois)
        logging.info(f"Checking paths for {total_dois} DOIs... ")

        for index, doi_entry in enumerate(dois, start=1):
            if index % 1000 == 0 or index == total_dois:
                logging.info(f"Processed {index}/{total_dois} DOIs.")
            if doi_entry.check_file():
                doi_entry.update_database()

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
        select_dois = self._generate_select_sql(start_year, end_year, issn, downloaded=False)
        downloaders = Downloaders()
        logging.info(f"SQL: {select_dois}")

        doif = DoiFactory(select_dois)
        dois = doif.dois
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
        using crossref API. This is "dumb"; it will re-download all years regardless
        of whether they have been downloaded before.
        The downloaded data is not explicitly stored or saved to a
        specific location.


        :param issn: The ISSN of the journal
        :type issn: str
        :param start_year: The start year for filtering the data
        :type start_year: str
        :param end_year: The end year for filtering the data
        :type end_year: str
        """
        journal_url = f'https://api.crossref.org/journals/{issn}'
        base_url = f"{journal_url}/works?filter=from-pub-date:{start_year},until-pub-date:{end_year}&rows=1000&cursor="
        cursor = "*"
        done = False
        total_items_processed = 0
        total_results = 0
        logging.info(f"Processing issn:{issn}")

        response = requests.get(journal_url)

        if response.status_code == 404 and response.text == "Resource not found.":
            print(f"There is no crossref data for journal {issn}")
            return

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
        """
        Downloads a chuck of DOIS from crossref. Creates a crossref journal entry for
        journals or a DOI for papers and stores it in the database if there isn't
        already a database entry there.

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

    # Not used, not yet tested, but potentially handy nonetheless. Delete
    # if not used after major revisions.
    def _get_single_doi(self, doi):
        """
        Get details for a single DOI from Crossref and return data formatted for database insertion.

        :param doi: The DOI for which to retrieve details.
        :type doi: str
        :return: A dictionary with keys matching the database columns.
        :rtype: dict
        """
        try:
            response = requests.get(f"{self.base_url}{doi}")
            response.raise_for_status()
            data = response.json()

            # Extracting relevant fields from the response
            item = data['message']
            doi = item.get('DOI', '')
            issn = item.get('ISSN', [''])[0] if item.get('ISSN') else ''
            published_date = item.get('created', {}).get('date-time', '')
            journal_title = item.get('container-title', [''])[0] if item.get('container-title') else ''
            downloaded = 0  # or 1 depending on your download logic
            details = json.dumps(item)
            full_path = ''  # Depends on your file storage logic

            # Formatting the published date
            if published_date:
                published_date = datetime.fromisoformat(published_date).date()

            return {
                'doi': doi,
                'issn': issn,
                'published_date': published_date,
                'journal_title': journal_title,
                'downloaded': downloaded,
                'details': details,
                'full_path': full_path
            }

        except requests.RequestException as e:
            print(f"Error fetching details for DOI {doi}: {e}")
            return {}


    def write_journals_to_tsv(self, output_file):
        # SQL query to select journals that have at least one corresponding DOI in the dois table
        query = """
        SELECT j.issn, j.name, j.type 
        FROM collections_papers.journals j
        WHERE EXISTS (
            SELECT 1 FROM collections_papers.dois d
            WHERE d.issn = j.issn
        )
        """
        journal_data = DBConnection.execute_query(query)

        # Check if there is any journal data to write
        if journal_data:
            # Open a file to write
            with open(output_file, 'w', newline='') as file:
                writer = csv.writer(file, delimiter='\t')

                # Write each row from the database to the TSV file
                for row in journal_data:
                    writer.writerow(row)
        else:
            print("No journals with corresponding DOIs found.")

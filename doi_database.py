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
import sys

from datetime import date


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
    # "do_verify" scans through all DOI records. If the PDF is already
    # downloaded, it populates the record accordingly.
    def __init__(self,
                 start_year=None):
        super().__init__()

        self._setup()
        self._query_journals(start_year)

    @staticmethod
    def _create_tables():
        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS journals (
                                            issn text primary key NOT NULL,
                                            name text,
                                            type text,
                                            start_year INT,
                                            end_year INT
                                        ); """
        DBConnection.execute_query(sql_create_database_table)

    def _setup(self):
        self._create_tables()
        CrossrefJournalEntry.create_tables()
        DoiEntry.create_tables()

    # Queries crossref for the history of the journal in question.
    # Crossref returns all records starting at the start_year until the
    # most recent year.

    # Updates the table "journals" with the "start year" passed in here
    # and "end year" being the current year. Journals table doesn't get an
    # entry until an attempt to query DOIs from crossref has happened.
    def _query_journals(self, start_year):
        with open('journals.tsv', 'r') as tsvin:
            for line in csv.reader(tsvin, delimiter='\t'):
                try:
                    if len(line) == 0 or line[0].startswith('#'):
                        continue
                    issn = line[0]
                    if issn.startswith("not in crossref"):
                        print("Not in crossref, continuing.")
                        continue
                    journal = line[1]
                    type = None
                    if len(line) > 2:
                        type = line[2]
                except Exception as e:
                    print(f"Parsing error: {line}, skipping.")
                    continue

                # print(f"Downloading {journal} issn: {issn} starting year: {start_year}", end='')
                # if type is None:
                #     print("")
                # else:
                #     print(f" Type: {type}")

                if self._check_journal_record(issn, start_year):
                    self.download_issn(issn, start_year)
                    self._update_journal_record(issn, start_year, journal, type)

    def force_crossref_update(self, start_year):
        query = f"select issn,name,type from journals"
        results = DBConnection.execute_query(query)
        for jounral in results:
            issn = jounral[0]
            name = jounral[1]
            type = jounral[2]
            self.download_issn(issn, start_year)
            self._update_journal_record(issn, start_year, name, type)

    def _get_issn_oldest_year(self, issn):
        query = f"select start_year from journals where issn=\"{issn}\""
        results = DBConnection.execute_query(query)

        if len(results) >= 1:
            return int(results[0][0])
        else:
            return None

    # returns true if the journal needs to be downloaded
    def _check_journal_record(self, issn, start_year):

        oldest_year_downloaded = self._get_issn_oldest_year(issn)
        if oldest_year_downloaded is None or (oldest_year_downloaded > start_year):
            return True
        return False

    def _update_journal_record(self, issn, start_year, name, type):
        previous_start_year = self._get_issn_oldest_year(issn)
        if previous_start_year is None or previous_start_year > start_year:
            name = name.replace("'", "''")
            print(f"{issn}\t{name}\t{type}")
            sql = f"INSERT OR REPLACE INTO journals (issn,name, type,start_year,end_year) VALUES ('{issn}','{name}','{type}',{start_year},{date.today().year})"
            results = DBConnection.execute_query(sql)

    # Scans through existing PDFs in the directory
    # If they're present, create or update the DoiEntry
    # in the database.

    # Inefficent; single request to crossref.org to get metadata for one pub.
    # it's better to run download_issn for the journal of interest and the run
    # import_pdfs. If the pdfs are of unknown or mixed provenance, then this
    # is the way to go.

    def import_pdfs(self, directory="./"):
        pdf_files = glob.glob(os.path.join(directory, "*.pdf"))
        query_count = 0
        total_count = 0
        for pdf_file in pdf_files:
            doi_string = self.get_doi_from_path(pdf_file)
            if doi_string in self.dois:
                doi_entry = self.dois[doi_string]
            else:
                doi_entry = DoiEntry(doi_string)
            if doi_entry.details is None:
                query_count += 1
                self._populate_metadata(doi_string, doi_entry)
                if query_count % 50 == 0:
                    self.save_database()
            total_count += 1
            if total_count % 10 == 0:
                print(f"Done {total_count} out of {len(pdf_files)}")
        self.save_database()

    # def _populate_metadata(self,doi_string):
    #     base_url = f"https://api.crossref.org/works/{doi_string}"
    #
    #     print(f"Querying crossref.org for metadata to build db: {base_url}")
    #     results = self._get_url_(base_url)
    #     item = results['message']
    #     DoiEntry(item,do_not_download=True)

    def verify_dois_by_journal_size(self,
                                    start_year,
                                    end_year):
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
            print(f"Attempting downloads for journal: {journal}:{issn}")
            report = DatabaseReport(start_year, end_year, journal)
            print("\n")
            print(report.report(journal=journal, issn=issn, summary=False))
            self.verify_dois(start_year, end_year, journal=journal, issn=issn)

    def _generate_select_sql(self, start_year, end_year, journal_issn, downloaded="FALSE"):
        select_dois = f"""select * from dois where downloaded={downloaded} """

        if start_year is not None and end_year is not None:
            select_dois += f""" and  {self.sql_year_restriction(start_year, end_year)}"""
        if journal_issn is not None:
            select_dois += f' and issn="{journal_issn}"'
        return select_dois

    def get_dois(self, start_year, end_year, journal_issn=None):
        sql = self._generate_select_sql(start_year, end_year, journal_issn, "TRUE")
        dois = DoiFactory(sql).dois
        return dois

    def get_doi(self, doi):
        sql = f"select * from dois where doi = '{doi}'"
        doi = DoiFactory(sql).dois
        if len(doi) != 1:
            raise FileNotFoundError(f"No such doi: {doi} or multiple results")
        return doi[0]

    def ensure_downloaded_has_pdf(self,start_year,end_year):
        dois = self.get_dois(start_year,end_year)
        for doi_entry in dois:
            doi_entry.check_file()
            doi_entry.update_database()




    # Ensures that all DOIs in the database have associated files
    # Download, if not.

    def verify_dois(self,
                    start_year,
                    end_year,
                    journal=None,
                    issn=None):

        select_dois = self._generate_select_sql(start_year, end_year, issn)
        downloaders = Downloaders()

        doif = DoiFactory(select_dois)
        dois = doif.dois
        print(f"SQL: {select_dois}")
        print(f"  Pending download count: {len(dois)}")
        download_list = []
        for doi_entry in dois:
            if journal is None or doi_entry.issn == issn:
                download_list.append(doi_entry)

        downloaders.download_list(download_list)

    def is_downloaded(self, doi_entry):
        return doi_entry.downloaded

    def download_issn(self, issn, start_year):
        base_url = f"https://api.crossref.org/journals/{issn}/works?filter=from-created-date:{start_year}&rows=1000&cursor="
        cursor = "*"
        done = False
        total_items_processed = 0
        total_results = 0
        print(f"Processing issn:{issn}")
        while not done:
            try:
                cursor, total_results, items_processed = self._download_chunk(base_url, cursor, start_year)
                total_items_processed += items_processed
                print("Continuing...")
            except ConnectionError:
                if total_items_processed >= total_results:
                    done = True
                    print("Done.")
                else:
                    print("retrying....")
            except RetriesExceededException as rex:
                print(f"Retries exceeded: {rex}, aborting.")
                return

    def _handle_connection_error(self, retries, max_retries, url, cursor, start_year, e):
        print(f"Connection error: {e}, retries: {retries}. Sleeping 60 and retrying.")
        time.sleep(60)
        if retries >= max_retries:
            raise RetriesExceededException(f"Retried {retries} times, aborting.")
        return self._download_chunk(url, cursor, start_year, retries)

    def _download_chunk(self, url, cursor, start_year, retries=0):
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

        print(f"Querying: {url + safe_cursor}")
        message = results['message']
        items = message['items']
        total_results = message['total-results']
        items_processed = 0
        for item in items:
            items_processed += 1
            # print(f"Processing DOI: {item['DOI']}")
            type = item['type']
            if type == 'journal':
                CrossrefJournalEntry(item)
            elif type == "journal-article":
                try:
                    DoiEntry(item)
                except EntryExistsException as e:
                    print(f"DOI already in database, skipping: {e}")
            else:
                # "journal-issue"
                # print(f"got type: {type}")
                pass

        if len(items) == 0:
            print("No items left.")
            raise ConnectionError()
        else:
            print(f"Processed {len(items)} items")
        return message['next-cursor'], total_results, items_processed

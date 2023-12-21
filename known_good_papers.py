#  testing code - we generate a set of known good papers and test our algorithms against it.
# Hasn't been validated since the re-org, not currently run.

from doi_database import DoiDatabase
from db_connection import DBConnection
from doi_database import DoiFactory
import re
import logging
# These are for our control group; papers that we know contain CAS references.

class KnownGoodPapers():
    def __init__(self):
        self.titles = []

    def _build_title_doi_map(self, start_year, end_year):
        self.doi_title_map = {}
        sql = f"select * from dois where published_date BETWEEN \'{start_year}-01-01\' AND \'{end_year}-12-31\'"
        dois = DoiFactory(sql).dois
        for doi_entry in dois:
            doi_title = self.clean_html(doi_entry.get_title())
            self.doi_title_map[doi_entry.doi] = doi_title

    def associate_title_file(self, filename, start_year, end_year):
        with open(filename, "r") as a_file:
            for cur_line in a_file:
                title = cur_line.strip()
                title = title.strip('\"')
                self.titles.append(title)
                # logging.debug(title)
        self._associate_titles(start_year,end_year)

    def _associate_titles(self, start_year, end_year):
        self._build_title_doi_map(start_year, end_year)
        self._create_association_table()
        matched_dois = []

        for title in self.titles:
            doi = self._get_title_association(title)
            if doi is not None:
                logging.info(f"Doi {doi[0][0]} already in database associated to Title \"{title}\"")
                continue
            title = self.clean_html(title)
            doi = self.match_literal(title)
            if doi is not None:
                logging.info("Literal match: ", end="")
            else:
                doi = self.match_fuzzy(title)
                if doi is not None:
                    logging.info("Fuzzy match: ", end="")
            if doi is not None:
                logging.info(f" {doi}: {title}")
                matched_dois.append(doi)
                self._insert_association(doi, title)
            else:
                logging.info(f"**** No match for: {title}")
                self._insert_association(None, title)

        return matched_dois

    def _get_title_association(self,title):
        query = f"select title from associations where title=\"{title}\""
        results = DBConnection.execute_query(query)
        # logging.info(f"Check exists query: {query}")
        if len(results) >= 1:
            return results
        return None

    def _check_association_doi_exists(self,doi):
        query = f"select doi from associations where doi=\"{doi}\""
        results = DBConnection.execute_query(query)
        # logging.info(f"Check exists query: {query}")
        if len(results) >= 1:
            return True
        return False

    def _insert_association(self,doi,title):
        try:
            if doi is not None:
                if self._check_association_doi_exists(doi):
                    logging.info(f"DOI {doi} already inserted, continuing...")
                    return
                sql_insert = f"INSERT INTO associations (doi, title) VALUES (%s, %s)"
                args = [doi, title]
            else:
                sql_insert = f"INSERT INTO associations (title) VALUES (?)"
                args = [title]
            DBConnection.execute_query(sql_insert, args)
        except Exception as e:
            logging.error(f"Failed to insert: {e}")


    def _create_association_table(self):
        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS associations (
                                            doi varchar(255) NOT NULL,
                                            title varchar(8192) NOT NULL
                                        ); """
        DBConnection.execute_query(sql_create_database_table)


    def clean_html(self, raw_html):
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext

    def match_literal(self, match_string):
        matched_doi = None
        for doi, doi_title in self.doi_title_map.items():
            if len(doi_title) > 5:
                if match_string.lower() in doi_title.lower():
                    # logging.info(f"Matched! {doi}: {doi_title}")
                    matched_doi = doi
                    break
        return matched_doi

    def match_fuzzy(self, match_string):
        matched_doi = None
        for doi, doi_title in self.doi_title_map.items():
            if len(doi_title) > 5:
                ratio = fuzz.ratio(match_string.lower(), doi_title.lower())
                if ratio > 90:
                    # logging.info(f"Matched! {doi}: {doi_title}")
                    matched_doi = doi
                    break
        return matched_doi

    def get_associated_dois(self):
        sql = "select doi from associations where doi is not NULL"
        return [x[0] for x in DBConnection.execute_query(sql) ]

from utils_mixin import Utils

import json
import os
import datetime

from db_connection import DBConnection

PDF_DIRECTORY = "./pdf/"

# from libgen_api import LibgenSearch

sh = None
headers = {
    'User-Agent': 'development; mailto:jrussack@calacademy.org',
}


class DoiFactory:

    def __init__(self, sql):
        doi_sql_results = DBConnection.execute_query(sql)

        results = []
        for cur_doi_json in doi_sql_results:
            doi = cur_doi_json[0]
            issn = cur_doi_json[1]
            journal_title = cur_doi_json[3]
            downloaded = cur_doi_json[4]
            details = cur_doi_json[5]
            full_path = cur_doi_json[6]

            new_doi = DoiEntry(skip_setup=True)
            new_doi.details = json.loads(details)
            new_doi.doi = doi
            new_doi.issn = issn
            new_doi.date = new_doi.get_date()
            new_doi.journal_title = journal_title
            new_doi.downloaded = downloaded
            new_doi.full_path = full_path
            results.append(new_doi)
        self.dois = results


class DoiEntry(Utils):
    # if json is populated
    def __init__(self, doi_details=None, skip_setup=False):
        super().__init__()
        if skip_setup:
            return
        self.issn = doi_details['ISSN'][0]
        self.doi = doi_details['DOI']
        if self._check_exists():
            raise EntryExistsException(self.doi)
        self.downloaded = False
        self.details = doi_details
        self.date = self.get_date()
        if doi_details['type'] == 'journal':
            raise TypeError("Journal not paper")
        if doi_details['type'] != "journal-article":
            raise TypeError(f"Not a journal article: {doi_details['type']}")
        # should be duplicate of ISSN reference, but we'll leave it for now
        self.journal_title = doi_details['container-title'][0]
        self.full_path = None

        self.insert_database()

    def mark_successful_download(self):
        self.downloaded = True
        self.full_path = self.generate_file_path()
        self.update_database()

    def _check_exists(self):
        query = f"select doi from dois where doi=\"{self.doi}\""
        results = DBConnection.execute_query(query)
        # print(f"Check exists query: {query}")
        if len(results) >= 1:
            return True
        return False

    @staticmethod
    def create_tables():
        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS dois (
                                            doi text primary key NOT NULL,
                                            issn text not null,
                                            published_date date not null,
                                            journal_title text not null,
                                            downloaded boolean NOT NULL,
                                            details data json,
                                            full_path text
                                        ); """
        DBConnection.execute_query(sql_create_database_table)

    def update_database(self):

        # json_string = json.dumps(self.details)
        sql_update = f"""update dois set issn=?,
                                                   published_date=?,
                                                   journal_title=?,
                                                   downloaded=?,
                                                   full_path=?,
                                                   details=?
                        where doi = "{self.doi}"             
               """
        args = [self.issn,
                self.date,
                self.journal_title,
                self.downloaded,
                self.full_path,

                json.dumps(self.details)]
        # print(f"SQL: {sql_update}")
        DBConnection.execute_query(sql_update, args)

    def insert_database(self):
        # sql = "INSERT INTO customers (name, address) VALUES (%s, %s)"
        # json_string = json.dumps(self.details)
        sql_insert = f"""insert into dois (doi,
                                            issn,
                                            published_date,
                                            journal_title,
                                            downloaded,
                                            full_path,
                                            details)
                        VALUES (?,?,?,?,?,?,?)                
        """

        args = [self.doi,
                self.issn,
                self.date,
                self.journal_title,
                self.downloaded,
                self.full_path,
                json.dumps(self.details)]
        # print(f"SQL insert {sql_insert}")
        DBConnection.execute_query(sql_insert, args)

    def get_journal(self):
        return self.journal_title

    def _get_date_parent(self, id_string, details):
        if id_string in details:
            date_parts = details[id_string]['date-parts'][0]
        else:
            raise IndexError("Missing publication date")
        try:
            if len(date_parts) == 3:
                results = datetime.datetime(year=date_parts[0], month=date_parts[1], day=date_parts[2])
            elif len(date_parts) == 2:
                results = datetime.datetime(year=date_parts[0], month=date_parts[1], day=1)
            else:
                results = datetime.datetime(year=date_parts[0], month=1, day=1)
        except IndexError as e:
            print(f"Bad date: {id_string}")
            raise e
        return results

    def get_date(self):
        if 'journal-issue' in self.details and 'published-online' in self.details['journal-issue']:
            return self._get_date_parent('published-online', self.details['journal-issue'])
        if 'journal-issue' in self.details and 'published-print' in self.details['journal-issue']:
            return self._get_date_parent('published-print', self.details['journal-issue'])
        elif 'published-online' in self.details:
            return self._get_date_parent('published-online', self.details)
        elif 'issued' in self.details:
            return self._get_date_parent('issued', self.details)
        elif 'deposited' in self.details:
            return self._get_date_parent('deposited', self.details)
        else:
            raise ValueError(f"Bad date format: {self.doi}")

    def get_issn_list(self):
        if self.details is None:
            return None
        if 'issn-type' not in self.details:
            return None
        retval = []
        for issn in self.details['issn-type']:
            retval.append(issn['value'])
        return retval

    def generate_file_path(self, path=None):
        if path is None:
            path = PDF_DIRECTORY
        filename = path + self.get_filename_from_doi_entry()
        return filename

    def check_file(self, path=None):
        filename = self.generate_file_path(path=path)
        if os.path.exists(filename):
            self.full_path = filename
            self.downloaded = True
            return True
        return False

    def get_doi_date_string(self, item):
        if 'created' in item:
            return item['created']['date-time']
        else:
            return ''

    def get_title(self):
        return self.details['title'][0]

    def __str__(self):
        str = ""
        str += f"  DOI: {self.doi}\n"

        if self.details is not None:
            if 'title' in self.details:
                str += f"  Title: {self.details['title'][0]}\n"
            else:
                str += "\n"
            if 'link' in self.details:
                str += f"  Link: {self.details['link'][0]['URL']}\n"
            if 'URL' in self.details:
                str += f"  URL: {self.details['URL']}\n"
            if 'created' in self.details:
                str += f"  Date: {self.get_doi_date_string(self.details)}\n"

        if self.full_path is not None:
            str += f"  File path: {self.full_path}\n"

        return str

    def print(self):
        print(self)


class EntryExistsException(Exception):
    pass

from utils_mixin import Utils

import json
import os
import datetime

from db_connection import DBConnection
import logging
from config import Config



# from libgen_api import LibgenSearch

sh = None
headers = {
    'User-Agent': 'development; mailto:jrussack@calacademy.org',
}


class DoiFactory:
    # TODO: Odd and bad that there are two ways to set up DoiEntry objects. We should use
    # one or the other and enforce it, or at the very least clarify the two cases in comments.
    def __init__(self, sql):
        """Initialize an object of the class by executing query, extract the fields from 
        query results, create a new DoiEntry object, populate the DoiEntry object with
        the extracted data, add the new DoiEntry object to the results list, and set the 
        dois attribute of the current object to the results list.

        :param sql: The SQL query to fetch DOI-related data.
        :type sql: str
        """
        #  TODO: All this junk probably belongs in doi_database.
        doi_sql_results = DBConnection.execute_query(sql)

        results = []
        for cur_doi_json in doi_sql_results:
            doi = cur_doi_json[0]
            issn = cur_doi_json[1]
            published_date = cur_doi_json[2]
            journal_title = cur_doi_json[3]
            downloaded = cur_doi_json[4]
            full_path = cur_doi_json[5]
            article_title = cur_doi_json[6]
            new_doi = DoiEntry()

            new_doi.doi = doi
            new_doi.issn = issn
            new_doi.published_date = published_date
            new_doi.journal_title = journal_title
            new_doi.downloaded = downloaded
            new_doi.full_path = full_path
            new_doi.article_title = article_title
            results.append(new_doi)
        self.dois = results


class DoiEntry(Utils):
    # if json is populated
    # Valid setup_type: None, 'download_chunk', 'import_pdfs'
    def __init__(self, setup_type=None, doi_details=None):
        """Initialize a DoiEntry object based on the provided setup type and DOI details.
        Will not create a new entry if one already exists, will raise EntityExistsException

        :param setup_type: The type of setup to be performed ('download_chunk' or 'import_pdfs'), defaults to None.
        :type setup_type: str, optional
        :param doi_details: Details related to the DOI, defaults to None.
        :type doi_details: dict, optional
        :raises ValueError: Raised when an invalid setup_type is provided.
        :raises EntityExistsException: Raised when an attempt is made to create a duplicate entry

        """        
        super().__init__()
        self.PDF_DIRECTORY = self.config.get_string("downloaders", "pdf_directory")
        if setup_type == None:
            return
        elif setup_type == 'download_chunk':
            self._setup(doi_details)
            self.downloaded = False
            self.full_path = None
        elif setup_type == 'import_pdfs':
            self._setup(doi_details)
            self.downloaded = True
            self.full_path = self.generate_file_path()
        else:
            raise ValueError(f"DoiEntry __init__: Invalid setup_type '{setup_type}'")
        self.insert_database()


    def _setup(self, doi_details):

        """Sets up the object and
        checks if DOI is of type "journal-article". If it's not, raise errors.

        :param doi_details: decoded json results of DOI from crossref.org
        :type doi_details: dict

        :raises EntryExistsException: If the length of the DOI string
            in the database is greater than or equal to 1.
        :raises TypeError: if DOI is of type 'journal'.
        :raises TypeError: if DOI is not of type 'journal-article'.
        """
        self.issn = doi_details['ISSN'][0]
        self.doi = doi_details['DOI']
        # should be duplicate of ISSN reference, but we'll leave it for now
        self.journal_title = doi_details['container-title'][0]
        # logging.info(f"attempting DOI with New date: {self.get_date()}")
        self.article_title = doi_details['title'][0]
        if self._check_exists():
            raise EntryExistsException(self.doi)
        self.published_date = self._get_date(doi_details)
        if doi_details['type'] == 'journal':
            raise TypeError("DOI type is 'journal', not 'journal-article'.")
        if doi_details['type'] != "journal-article":
            raise TypeError(f"DOI type is '{doi_details['type']}', not 'journal-article'.")

    def mark_successful_download(self):
        """Sets the 'downloaded' attribute to True, 
        generates the full file path, and updates the database.

        """        
        self.downloaded = True
        self.full_path = self.generate_file_path()
        self.update_database()

    def _check_exists(self):
        """Checks if the length of DOI string in database >= 1.

        :return: True if length of DOI string in database >= 1
            False if otherwise
        :rtype: bool
        """        
        query = f"select doi from dois where doi=\"{self.doi}\""
        results = DBConnection.execute_query(query)
        # logging.info(f"Check exists query: {query}")
        if len(results) >= 1:
            return True
        return False

    @staticmethod
    def create_tables():
        """Creates a database table named "dois" if it doesn't already exist. 
        The table includes columns: 
        doi(primary key), issn, published_date, ournal_title,downloaded, details, full_path
        """        
        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS dois (
                                          doi            varchar(255)           not null  primary key,
                                          issn           varchar(100)           not null,
                                          published_date date           not null,
                                          journal_title  varchar(1024)           not null,
                                          downloaded     tinyint(1)     not null,
                                          full_path      varchar(2048)           null,
                                          article_title  varchar(4096) null
                                    );"""




        DBConnection.execute_query(sql_create_database_table)

    def update_database(self):
        """Update the dois table in database with the current object's 
        details  using sql query
        """        

        sql_update = f"""
            UPDATE dois SET 
                issn = %s,
                published_date = %s,
                journal_title = %s,
                downloaded = %s,
                full_path = %s,
                article_title = %s
            WHERE doi = "{self.doi}"
        """

        args = [self.issn,
                self.published_date,
                self.journal_title,
                self.downloaded,  # Convert boolean to 1 or 0
                self.full_path,
                self.article_title]
        # logging.info(f"SQL: {sql_update}")
        DBConnection.execute_query(sql_update, args)

    def insert_database(self):
        sql_insert = f"""insert into dois (doi,
                                            issn,
                                            published_date,
                                            journal_title,
                                            downloaded,
                                            full_path,
                                            article_title
                                            )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)                
        """
        self.article_title = self.article_title[:8100]

        args = [self.doi,
                self.issn,
                self.published_date,
                self.journal_title,
                self.downloaded,  # Convert boolean to 1 or 0
                self.full_path,
                self.article_title
                ]


        # logging.info(f"SQL insert {sql_insert}")
        # logging.debug(f"Args: {args}")
        DBConnection.execute_query(sql_insert, args)

    def get_journal(self):
        """Retrieve the title of the journal associated with this object.


        :return: The title of the journal.
        :rtype: str
        """        
        return self.journal_title

    def get_downloaded_status(self):
        return self.downloaded != 0

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
            logging.warning(f"Bad date: {id_string}")
            raise e
        return results

    def get_date(self):
        return self.published_date

    def _get_date(self,doi_details):
        if 'journal-issue' in doi_details and 'published-online' in doi_details['journal-issue']:
            return self._get_date_parent('published-online', doi_details['journal-issue'])
        if 'journal-issue' in doi_details and 'published-print' in doi_details['journal-issue']:
            return self._get_date_parent('published-print', doi_details['journal-issue'])
        elif 'published-online' in doi_details:
            return self._get_date_parent('published-online', doi_details)
        elif 'issued' in doi_details:
            return self._get_date_parent('issued', doi_details)
        elif 'deposited' in doi_details:
            return self._get_date_parent('deposited', doi_details)
        else:
            raise ValueError(f"Bad date format: {self.doi}")


    def generate_file_path(self, path=None):
        """Generates the full file path for saving the generated papers.

        :param path: The base directory path that is ./pdf/issn#/year, defaults to None
        :type path: str, optional

        :return: The generated full file path to the papers in pdf format.
        :rtype: str
        """        
        if path is None:
            path = os.path.join(self.PDF_DIRECTORY, self.issn, str(self.published_date.year))
        filename = os.path.join(path, self.get_filename_from_doi_entry())
        return filename

    def check_and_update_file_path_variables(self, path=None):
        """Check whether designated file already exists in path. If so, 
        return True and update self. If otherwise, return False and
        update self.

        :param path: path to check for file existence, defaults to None
        :type path: str, optional
        :return: True if file exists in path, False otherwise
        :rtype: bool
        """        
        filename = self.generate_file_path(path=path)
        if os.path.exists(filename):
            self.full_path = filename
            self.downloaded = True
            # logging.debug(f"Found paper for doi {self.doi} at {self.full_path}")
            return True
        else:
            # if self.downloaded is True:
            #     logging.debug(f"Missing paper marked as present! updating {self.doi} at {self.full_path}")

            self.full_path = None
            self.downloaded = False
            return False

    def get_doi_date_string(self, item):
        if 'created' in item:
            return item['created']['date-time']
        else:
            return ''

    def get_title(self):
        return self.article_title
        # This was wrong, but it's old code? Not sure how that error happened.
        # return self.journal_title

    # Scream test - delete if unused
    # def __str__(self):
    #     """Return a string representation of the DoiEntry object.
    #
    #     :return: A formatted string representation of the object.
    #     :rtype: str
    #     """
    #     str = ""
    #     str += f"  DOI: {self.doi}\n"
    #
    #     if self.details is not None:
    #         if 'title' in self.details:
    #             str += f"  Title: {self.details['title'][0]}\n"
    #         else:
    #             str += "\n"
    #         if 'link' in self.details:
    #             str += f"  Link: {self.details['link'][0]['URL']}\n"
    #         if 'URL' in self.details:
    #             str += f"  URL: {self.details['URL']}\n"
    #         if 'created' in self.details:
    #             str += f"  Date: {self.get_doi_date_string(self.details)}\n"

        if self.full_path is not None:
            str += f"  File path: {self.full_path}\n"

        return str

    def print(self):
        print(self)


class EntryExistsException(Exception):
    pass

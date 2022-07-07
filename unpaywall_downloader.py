from downloader import Downloader
import traceback
from unpywall.utils import UnpywallCredentials
from unpywall import Unpywall
from requests import exceptions
import requests
from datetime import datetime
from db_connection import DBConnection
from utils_mixin import Utils


class UnpaywallDownloader(Downloader, Utils):

    def __init__(self):
        super().__init__()
        self.most_recent_url = None
        self.most_recent_firefox_failure = None
        self.firefox_failure = None
        self._create_tables()

    def _create_tables(self):
        sql_create_database_table = """ create table IF NOT EXISTS unpaywall_downloader
                                        (
                                            doi TEXT primary key,
                                            open_url TEXT, 
                                            most_recent_attempt DATE,
                                            most_recent_firefox_failure DATE

                                        ); """
        DBConnection.execute_query(sql_create_database_table)

    def _update_unpaywall_database(self, doi):

        sql = "INSERT OR REPLACE INTO unpaywall_downloader(doi, open_url, most_recent_attempt, most_recent_firefox_failure) VALUES(?,?,?,?)"
        args = [doi, self.most_recent_url, datetime.now(), self.most_recent_firefox_failure]
        # print(f"SQL: {sql_update}")
        DBConnection.execute_query(sql, args)

    def download(self, doi_entry):
        self.most_recent_firefox_failure = None
        self.most_recent_url = None
        print(f"Download unpaywall:{doi_entry}")
        sql = f"select most_recent_attempt from unpaywall_downloader where doi='{doi_entry.doi}'"
        results = DBConnection.execute_query(sql)
        if len(results) == 0:
            self.most_recent_attempt = None
        else:
            self.most_recent_attempt = results[0][0]
            # '2022-07-02 22:00:39.132010'
            self.most_recent_attempt = datetime.strptime(self.most_recent_attempt, self.DATETIME_FORMAT)

        if not self.meets_datetime_requrements('unpaywall_downloader', self.most_recent_attempt):
            print(
                f"Attempted too recently; last attempt was {self.most_recent_attempt} cutoff is {self.config.get_string('unpaywall_downloader', 'retry_after_datetime')}")
            return False
        if self.config.get_boolean("unpaywall_downloader", "attempt_direct_link"):
            print("Attempting direct link...")
            if self._download_link(doi_entry):
                doi_entry.downloaded = True

                return True
        results = self._download_unpaywall(doi_entry)
        self._update_unpaywall_database(doi_entry.doi)
        return results

    #  TODO: Currently only handles direct-to-PDF links. Most aren't; smart pdf button finder?
    def _download_link(self, doi_entry):
        if 'link' in doi_entry.details:
            URL = doi_entry.details['link'][0]['URL']
            self._update_unpaywall_database(doi_entry.doi, URL, self.most_recent_firefox_failure)

        else:
            self._update_unpaywall_database(doi_entry.doi, None, self.most_recent_firefox_failure)
            return False
        print(f"Direct link cited; attempting link: {URL}")
        try:
            self._download_url_to_pdf_bin(doi_entry, URL, self.PDF_DIRECTORY)
        except Exception as ex:
            print(f"Direct link failed: {ex}")
            return False
        return True

    def _download_unpaywall(self, doi_entry):
        print(f"Attempting unpaywall... @{datetime.now()}")
        use_firefox_downloader = self.config.get_boolean('unpaywall_downloader', 'firefox_downloader')
        retry_firefox_failure = self.config.get_boolean('unpaywall_downloader', 'retry_firefox_failure')

        try:

            filename = Utils.get_filename_from_doi_string(doi_entry.doi)
            # print(f"Downloading to: {self.PDF_DIRECTORY}/{filename}")
            email = self.config.get_string("downloaders","header_email")
            UnpywallCredentials(email)

            self.most_recent_url = Unpywall.get_pdf_link(doi_entry.doi)

            if self.most_recent_url is None:
                print(f"Not available through unpaywall.")
                return False
            print(f"Attempting unpaywall download: {self.most_recent_url} will download to {self.PDF_DIRECTORY}/{filename}")
            try:
                self._download_url_to_pdf_bin(doi_entry, self.most_recent_url, self.PDF_DIRECTORY)
            except TypeError as te:
                if use_firefox_downloader:
                    if self.most_recent_firefox_failure is not None and retry_firefox_failure is False:
                        print("We have a firefox browser download failure; not retrying per config")
                        raise te
                    firefox_result = self._firefox_downloader(self.most_recent_url, doi_entry)
                    if firefox_result is False:
                        self.most_recent_firefox_failure = datetime.now()
                    return firefox_result



                else:
                    raise te
            return True
        except exceptions.HTTPError as e:
            print(f"Not available through unpaywall... {e}")
            return False
        except TypeError as e:
            print(f"Unpaywall redirected to an html link, likely a redirect that requires a browser: {e} {url}")
            return False
        except TimeoutError as e:
            print(f"Unpaywall timeout error attempting download: {e} {url}")
            return False
        except requests.exceptions.ChunkedEncodingError as e:
            print(f"Unpaywall encoding error attempting download: {e} {url}")
            return False
        except Exception as e:
            traceback.print_exc()
            print(f"Unpaywall unexpected exception: {e}")
            return False

from downloader import Downloader
import traceback
from unpywall.utils import UnpywallCredentials
from unpywall import Unpywall
from requests import exceptions
import requests
from datetime import datetime
from db_connection import DBConnection
from utils_mixin import Utils
import time


class UnpaywallDownloader(Downloader, Utils):

    def __init__(self):
        super().__init__()
        self.open_url = None
        self.most_recent_firefox_failure = None
        self.most_recent_attempt = None
        self.error_code = None
        self.error_code = None
        self.firefox_failure = None
        self._create_tables()



    def _create_tables(self):
        sql_create_database_table = """ create table IF NOT EXISTS unpaywall_downloader
                                        (
                                            doi TEXT primary key,
                                            open_url TEXT, 
                                            most_recent_attempt DATE,
                                            most_recent_firefox_failure DATE,
                                            error_code boolean,
                                            not_available boolean

                                        ); """
        DBConnection.execute_query(sql_create_database_table)

    def _update_unpaywall_database(self, doi):

        sql = "INSERT OR REPLACE INTO unpaywall_downloader(doi, open_url, most_recent_attempt, most_recent_firefox_failure,error_code,not_available) VALUES(?,?,?,?,?,?)"
        args = [doi, self.open_url, datetime.now(), self.most_recent_firefox_failure, self.error_code,self.not_available]
        DBConnection.execute_query(sql, args)

    def download(self, doi_entry):
        self.most_recent_firefox_failure = None
        self.open_url = None
        self.error_code = None
        self.most_recent_attempt = None
        self.not_available = None

        # print(f"Download unpaywall:{doi_entry}")
        sql = f"select most_recent_attempt, open_url, most_recent_firefox_failure,error_code,not_available from unpaywall_downloader where doi='{doi_entry.doi}'"
        results = DBConnection.execute_query(sql)
        if len(results) == 0:
            self.most_recent_attempt = None
        else:
            self.most_recent_attempt = datetime.strptime(results[0][0], self.DATETIME_FORMAT)
            self.open_url = results[0][1]
            self.most_recent_firefox_failure = results[0][2]
            self.error_code = results[0][3]
            self.not_available = results[0][4]

        # if self.error_code != 200:
        #     print("Will not retry - last attempt was not found")
        retry_only_failures_with_link = self.config.get_boolean('unpaywall_downloader', 'retry_only_failures_with_link')

        if not (retry_only_failures_with_link and (self.open_url is not None)):
            if not self.meets_datetime_requrements('unpaywall_downloader', self.most_recent_attempt):
                print(
                    f"Attempted too recently; last attempt was {self.most_recent_attempt} cutoff is {self.config.get_string('unpaywall_downloader', 'retry_after_datetime')}")
                return False
        if self.config.get_boolean("unpaywall_downloader", "attempt_direct_link"):
            print("Attempting direct link...")
            if self._download_link(doi_entry):
                doi_entry.downloaded = True
                # update most recent attempt
                self._update_unpaywall_database(doi_entry.doi)
                return True

        results = self._download_unpaywall(doi_entry)
        self._update_unpaywall_database(doi_entry.doi)
        return results

    # Crossref downloader has some good code to extract PDF link
    # from HTML
    def _download_link(self, doi_entry):
        if 'link' in doi_entry.details:
            direct_link = doi_entry.details['link'][0]['URL']
        else:
            return False
        print(f"Direct link cited; attempting link: {direct_link}")

        is_good, self.error_code = self._download_url_to_pdf_bin(doi_entry, direct_link, self.PDF_DIRECTORY)
        return is_good

    def _download_unpaywall(self, doi_entry):
        print(f"Attempting unpaywall... @{datetime.now()}")
        use_firefox_downloader = self.config.get_boolean('unpaywall_downloader', 'firefox_downloader')
        retry_firefox_failure = self.config.get_boolean('unpaywall_downloader', 'retry_firefox_failure')
        force_open_url_update = self.config.get_boolean('unpaywall_downloader', 'force_open_url_update')
        force_update_link_only = self.config.get_boolean('unpaywall_downloader', 'force_update_link_only')

        try:

            filename = Utils.get_filename_from_doi_string(doi_entry.doi)
            # print(f"Downloading to: {self.PDF_DIRECTORY}/{filename}")
            email = self.config.get_string("downloaders", "header_email")
            UnpywallCredentials(email)
            if self.open_url is None or force_open_url_update:
                self.open_url = Unpywall.get_pdf_link(doi_entry.doi)
            else:
                print(f"re-using url from last unpaywall pull: {self.open_url}..")
                sleep_time = self.config.get_int('unpaywall_downloader', 're_used_direct_url_sleep_time')
                if sleep_time > 0:
                    time.sleep(sleep_time)

            if self.open_url is None:
                print(f"Not available through unpaywall.")
                self.not_available = True
                return False
            else:
                self.not_available = False
            print(
                f"Attempting unpaywall download: {self.open_url} will download to {self.PDF_DIRECTORY}/{filename}")

            if force_update_link_only:
                time.sleep(5)
                return False
            response, self.error_code = self._download_url_to_pdf_bin(doi_entry, self.open_url, self.PDF_DIRECTORY)
            if response:
                return True

            if self.error_code == 503:

                print("Likely cloudflare interception. ")
                # time.sleep(60)

                if use_firefox_downloader:
                    if self.most_recent_firefox_failure is not None and retry_firefox_failure is False:
                        print("We have a firefox browser download failure; not retrying per config")
                        raise Exception
                    firefox_result = self._firefox_downloader(self.open_url, doi_entry)
                    if firefox_result is False:
                        self.most_recent_firefox_failure = datetime.now()
                    return firefox_result

        except exceptions.HTTPError as e:
            print(f"Not available through unpaywall... {e}")
        except TypeError as e:
            print(
                f"Unpaywall redirected to an html link, likely a redirect that requires a browser: {e} {self.open_url}")
        except TimeoutError as e:
            print(f"Unpaywall timeout error attempting download: {e} {self.open_url}")
        except requests.exceptions.ChunkedEncodingError as e:
            print(f"Unpaywall encoding error attempting download: {e} {self.open_url}")
        except Exception as e:
            traceback.print_exc()
            print(f"Unpaywall unexpected exception: {e}")
        finally:
            return False

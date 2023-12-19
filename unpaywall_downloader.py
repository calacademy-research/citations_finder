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
import logging


# from headless_download import HeadlessDownload

class UnpaywallDownloader(Downloader, Utils):

    def __init__(self):
        """initializes the UnpaywallDownloader object by calling the 
        constructor of the superclass(Downloader) using 'super().__init__()'. 
        It sets several instance attributes to None, including 'open_url',
        'most_recent_firefox_failure', 'most_recent_attempt', 'error_code', 
        and 'firefox_failure'. It then calls the 'create_tables' method to 
        create the 'unpaywall_downloader' table in the database.

        Note: The 'self' parameter refers to the instance of the 
        UnpaywallDownloader class being created.
        """
        super().__init__()
        self.open_url = None
        self.most_recent_firefox_failure = None
        self.most_recent_attempt = None
        self.error_code = None
        self.firefox_failure = None
        self.create_tables()

    @classmethod
    def create_tables(self):
        """Creates the 'unpaywall_downloader' table in the database 
        if it does not already exist.
        The table schema includes columns for DOI (doi), open URL (open_url), 
        most recent attempt timestamp (most_recent_attempt),
        most recent Firefox failure timestamp (most_recent_firefox_failure), 
        error code (error_code), and not available flag (not_available).

        The DOI column is set as the primary key to ensure uniqueness of DOI entries in the table.
        """
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
        """Updates the Unpaywall database with the download information for the 
        provided DOI. It inserts or replaces a record in the 'unpaywall_downloader'
        table with the DOI, open URL, most recent attempt timestamp, most recent 
        Firefox failure timestamp, error code, and not available flag. The method
        uses the class attributes `self.open_url`, `self.most_recent_firefox_failure`
        , `self.error_code`, and `self.not_available`to populate the database record.

        :param doi: The DOI for which the download information is to be updated in the database.
        :type doi: str
        """

        sql = "INSERT OR REPLACE INTO unpaywall_downloader(doi, open_url, most_recent_attempt, most_recent_firefox_failure,error_code,not_available) VALUES(%s,%s,%s,%s,%s,%s)"
        args = [doi, self.open_url, datetime.now(), self.most_recent_firefox_failure, self.error_code,
                self.not_available]
        DBConnection.execute_query(sql, args)

    def download(self, doi_entry):
        """Attempts to download a DOI entry from Unpaywall. The method first retrieves the
        most recent downloaddetails from the Unpaywall database for the provided
        DOI. If the DOI has been downloaded, it checks the
        configuration settings to determine whether to retry the 
        download based on different conditions.

        :param doi_entry: The DOI entry to download.
        :type doi_entry: DoiEntry
        :return: True if the download is successful, False otherwise.
        :rtype: bool
        """
        self.most_recent_firefox_failure = None
        self.open_url = None
        self.error_code = None
        self.most_recent_attempt = None
        self.not_available = None
        force_update_link_only = self.config.get_boolean('unpaywall_downloader', 'force_update_link_only')
        populate_not_available_only = self.config.get_boolean('unpaywall_downloader', 'populate_not_available_only')

        # logging.debug(f"Download unpaywall:{doi_entry}")
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

        # if both force_update_link_only and populate_not_available_only are set to True and self.not_available has a value
        # in the database, then the download process should be aborted.
        if force_update_link_only and populate_not_available_only:
            if self.not_available is not None:
                return False
        # if self.error_code != 200:
        #     logging.warning("Will not retry - last attempt was not found")

        # See config.ini.template for details -
        # If there's no unpaywall info for this paper, won't requery unpaywall unless
        # retry_only_failures_with_link is true. Also checks most recent download
        # attempt so we don't bother if we have recent failures.

        retry_only_failures_with_link = self.config.get_boolean('unpaywall_downloader', 'retry_only_failures_with_link')
        if not (retry_only_failures_with_link and (self.open_url is not None)):
            if not self.meets_datetime_requrements('unpaywall_downloader', self.most_recent_attempt):
                logging.info(
                    f"Attempted too recently; last attempt was {self.most_recent_attempt} cutoff is {self.config.get_string('unpaywall_downloader', 'retry_after_datetime')}")
                return False

        # Checks another configuration setting attempt_direct_link. If this setting is True, 
        # it attempts to download the resource using a direct link (self._download_link(doi_entry)).
        # If the direct download is successful (_download_link returns True), it updates doi_entry.downloaded to True, 
        # indicating that the download was successful.
        # It also updates the most recent attempt in the database and returns True, indicating that the download was successful.
        if self.config.get_boolean("unpaywall_downloader", "attempt_direct_link"):
            logging.info("Attempting direct link...")
            if self._download_link(doi_entry):
                doi_entry.downloaded = True
                # update most recent attempt
                self._update_unpaywall_database(doi_entry.doi)
                return True

        # below results is True if the download is successful, False otherwise. Also performs
        # download action
        results = self._download_unpaywall(doi_entry)
        self._update_unpaywall_database(doi_entry.doi)
        return results

    # Crossref downloader has some good code to extract PDF link
    # from HTML
    def _download_link(self, doi_entry):
        """Attempts to download the DOI entry using a direct link if available
          in the DOI entry details (dois table, details column). The method 
          first checks if the DOI entry has a 'link' field in its details. If 
          the field exists, it retrieves the direct link to the PDF file and 
          attempts to download the PDF. If the download is successful, it 
          returns True; otherwise, it returns False.

            :param doi_entry: The DOI entry object to download.
            :type doi_entry: DoiEntry
            :return: True if the download is successful, False otherwise.
            :rtype: bool
        """
        if 'link' in doi_entry.details:
            direct_link = doi_entry.details['link'][0]['URL']
        else:
            return False
        logging.info(f"Direct link cited; attempting link: {direct_link}")

        is_good, self.error_code = self._download_url_to_pdf_bin(doi_entry, direct_link, self.PDF_DIRECTORY)
        return is_good

    def _download_unpaywall(self, doi_entry):
        """Attempts to download the DOI entry from Unpaywall based on the given
        DOI entry object. The method retrieves configuration settings and performs
        various checks to determine the appropriate download strategy. If the DOI 
        entry is available through Unpaywall,it attempts to download the PDF 
        file using the direct link. If the download is successful,it returns True, 
        otherwise False.

        :param doi_entry: The DOI entry object to download.
        :type doi_entry: DoiEntry
        :raises Exception: Raises an exception if the download process encounters critical issues.
        :return: True if the download is successful, False otherwise.
        :rtype: bool
        """
        use_firefox_downloader = self.config.get_boolean('unpaywall_downloader', 'firefox_downloader')
        retry_firefox_failure = self.config.get_boolean('unpaywall_downloader', 'retry_firefox_failure')
        force_open_url_update = self.config.get_boolean('unpaywall_downloader', 'force_open_url_update')
        force_update_link_only = self.config.get_boolean('unpaywall_downloader', 'force_update_link_only')
        do_not_refetch_links = self.config.get_boolean('unpaywall_downloader', 'do_not_refetch_links')

        # if not headless_download:
        logging.info(f"Attempting unpaywall... @{datetime.now()}")

        try:
            # logging.debug(f"Downloading to: {doi_entry.generate_file_path()}")
            email = self.config.get_string("downloaders", "header_email")
            UnpywallCredentials(email)

            # marking download as failed (False) if do_not_refetch_links
            if self.not_available == 1 and do_not_refetch_links:
                logging.warning("Do not re-pull missing unpaywall links")
                download_result = False
            # ===========================
            # if url available, fetch url or reusing url from last pull
            if self.open_url is None or force_open_url_update:
                self.open_url = Unpywall.get_pdf_link(doi_entry.doi)

            else:
                logging.info(f"re-using url from last unpaywall pull: {self.open_url}..")
                sleep_time = self.config.get_int('unpaywall_downloader', 're_used_direct_url_sleep_time')
                if sleep_time > 0:
                    time.sleep(sleep_time)
            # ===========================

            # ===========================
            # if url not availble, mark download as failed and not_available as True.
            # if url available, mark not_available as False
            if self.open_url is None:
                logging.info(f"Not available through unpaywall.")
                self.not_available = True
                download_result = False
            else:
                self.not_available = False
            # ===========================

            if force_update_link_only:
                download_result = False

            # ===========================
            # Sophia added if block here to prevent download from starting, if URL doesn't exist
            if self.not_available is True:
                logging.info(f"Skipping download")
                response = False
            else:
                logging.info(
                    f"Attempting unpaywall download, URL: ({self.open_url}) will download to {doi_entry.generate_file_path()}")
                # below line performs download function
                response, self.error_code = self._download_url_to_pdf_bin(doi_entry, self.open_url, self.PDF_DIRECTORY)
            # ===========================

            if response:
                download_result = True

            # added 403 below
            if self.error_code == 503 or self.error_code == 403 or self.error_code == 429:

                logging.info("Http error 403, 429 or 503, trying firefox selenium downloader, if enabled")

                if use_firefox_downloader:
                    if self.most_recent_firefox_failure is not None and retry_firefox_failure is False:
                        logging.error("We have a firefox browser download failure; not retrying per config")
                        raise Exception
                    firefox_result = self._firefox_downloader(self.open_url, doi_entry, self.PDF_DIRECTORY)
                    if firefox_result is False:
                        self.most_recent_firefox_failure = datetime.now()
                    download_result = firefox_result

        except exceptions.HTTPError as e:
            logging.info(f"Not available through unpaywall... {e}")
        except TypeError as e:
            logging.info(
                f"Unpaywall redirected to an html link, likely a redirect that requires a browser: {e} {self.open_url}")
        except TimeoutError as e:
            logging.warning(f"Unpaywall timeout error attempting download: {e} {self.open_url}")
        except requests.exceptions.ChunkedEncodingError as e:
            logging.warning(f"Unpaywall encoding error attempting download: {e} {self.open_url}")
        except Exception as e:
            traceback.print_exc()
            logging.error(f"Unpaywall unexpected exception: {e}")
        finally:
            if download_result is None:
                download_result = False
            return download_result

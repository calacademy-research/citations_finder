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
        email = self.config.get_string("downloaders", "header_email")
        UnpywallCredentials(email)
        self._fetch_config_settings()


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
                                            doi varchar(255) primary key,
                                            open_url varchar(2048), 
                                            most_recent_attempt DATETIME,
                                            most_recent_firefox_failure DATETIME,
                                            error_code smallint,
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

        # sql = "INSERT OR REPLACE INTO unpaywall_downloader(doi, open_url, most_recent_attempt, most_recent_firefox_failure,error_code,not_available) VALUES(%s,%s,%s,%s,%s,%s)"
        sql = "REPLACE INTO unpaywall_downloader(doi, open_url, most_recent_attempt, most_recent_firefox_failure, error_code, not_available) VALUES(%s, %s, %s, %s, %s, %s)"
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
            if self.do_not_retry:
                logging.warning: ("Do not retry is set - previous failure won't be attempted")
                return False
            # self.most_recent_attempt = datetime.strptime(results[0][0], self.DATETIME_FORMAT)
            self.most_recent_attempt = results[0][0]
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
        result = self._download_unpaywall(doi_entry)
        if result is True:
            logging.info("SUCCESSFUL download")
        else:
            logging.info("FAILED download")
        self._update_unpaywall_database(doi_entry.doi)
        return result

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
        """
        Attempts to download the DOI entry from Unpaywall based on the given
        DOI entry object. The method retrieves configuration settings and performs
        various checks to determine the appropriate download strategy. If the DOI
        entry is available through Unpaywall, it attempts to download the PDF
        file using the direct link. If the download is successful, it returns True,
        otherwise False.

        :param doi_entry: The DOI entry object to download.
        :type doi_entry: DoiEntry
        :raises Exception: Raises an exception if the download process encounters critical issues.
        :return: True if the download is successful, False otherwise.
        :rtype: bool
        """
        logging.info(f"Attempting Unpaywall download @{datetime.now()}")

        try:
            if self._is_download_skippable(doi_entry):
                return False
            if not self._fetch_or_reuse_url(doi_entry):
                return False


            if self.force_update_link_only:
                return False

            return self._attempt_download(doi_entry)
        except exceptions.HTTPError as e:
            logging.info(f"Not available through Unpaywall: {e}")
            return False
        except TypeError as e:
            logging.info(f"Redirect to HTML link, requires browser: {e} URL: {self.open_url}")
            return False
        except TimeoutError as e:
            logging.warning(f"Timeout error during download: {e} URL: {self.open_url}")
            return False
        except requests.exceptions.ChunkedEncodingError as e:
            logging.warning(f"Encoding error during download: {e} URL: {self.open_url}")
            return False
        except Exception as e:
            traceback.print_exc()
            logging.error(f"Unexpected exception during download: {e}")
            return False


    def _fetch_config_settings(self):
        config_keys = ['firefox_downloader',
                       'retry_firefox_failure',
                       'force_open_url_update',
                       'force_update_link_only',
                       'do_not_refetch_links',
                       'do_not_retry']

        for key in config_keys:
            setattr(self, key, self.config.get_boolean('unpaywall_downloader', key))

    #
    def _is_download_skippable(self, doi_entry):
        if self.not_available and self.do_not_refetch_links:
            logging.warning("Skipping missing Unpaywall links")
            return True

        return False

    def _fetch_or_reuse_url(self, doi_entry):
        if self.open_url is None or self.force_open_url_update:
            for attempt in range(4):
                try:
                    self.open_url = Unpywall.get_pdf_link(doi_entry.doi)
                    break
                except Exception as e:
                    logging.error(
                        f"Attempt {attempt + 1}: Failed to get url from unpaywall for doi:{doi_entry.doi}. exception: {e}")
                    time.sleep(15 * 2 ** attempt)

            if self.open_url is None:
                logging.info("DOI not available through Unpaywall.")
                self.not_available = True
                return False
            self.not_available = False
        else:
            logging.info(f"Re-using URL from last Unpaywall pull: {self.open_url}")
            sleep_time = self.config.get_int('unpaywall_downloader', 're_used_direct_url_sleep_time')
            if sleep_time > 0:
                time.sleep(sleep_time)
        return True

    def _attempt_download(self, doi_entry):
        if self.not_available:
            logging.info("Skipping download due to unavailability")
            return False

        logging.info(f"Downloading from Unpaywall URL: {self.open_url}")
        response, self.error_code = self._download_url_to_pdf_bin(doi_entry, self.open_url, self.PDF_DIRECTORY)

        if response:
            return True
        if self.error_code in [403, 429, 503]:
            return self._attempt_firefox_download(doi_entry)
        return False

    def _attempt_firefox_download(self, doi_entry):
        if not self.firefox_downloader:
            return False

        if self.most_recent_firefox_failure and not self.retry_firefox_failure:
            logging.error("Skipping Firefox download due to previous failure")
            return False

        try:
            if not self._firefox_downloader(self.open_url, doi_entry, self.PDF_DIRECTORY):
                self.most_recent_firefox_failure = datetime.now()
                return False
            logging.info("Successful Firefox download")
            self.error_code = None
            return True
        except Exception as e:
            logging.error(f"Firefox download failed: {e}")
            self.most_recent_firefox_failure = datetime.now()
            return False

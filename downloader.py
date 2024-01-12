from abc import ABC, ABCMeta, abstractmethod
from config import Config
import requests
from utils_mixin import Utils
from datetime import datetime
import os
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
import errno
import signal
import functools
import shutil
import logging
from selenium.webdriver.firefox.options import Options
import subprocess


class Downloader(ABC, Utils):
    __metaclass__ = ABCMeta

    def __init__(self):
        """_summary_
        """
        self.DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

        self.config = Config()

        self.PDF_DIRECTORY = self.config.get_string("downloaders", "pdf_directory")
        if not os.path.exists(self.PDF_DIRECTORY):
            logging.warning(f"PDF directory missing; creating now: {self.PDF_DIRECTORY}")
            os.mkdir(self.PDF_DIRECTORY)
        header_email = self.config.get_string("downloaders", "header_email")
        self.headers = {
            'User-Agent': f'development; mailto:{header_email}',
        }

    def meets_datetime_requrements(self, section, most_recent_attempt_datetime):
        """Check if the provided conditions meet the datetime requirements.
        If 'retry_after_datetime' in config.ini is newer/more recent than the 
        last attempt date, return False


        :param section: The configuration section to retrieve values from.
        :type section: str
        :param most_recent_attempt_datetime: The datetime of the most recent attempt.
        :type most_recent_attempt_datetime: datetime.datetime or None
        :return: True if the conditions meet the datetime requirements, False otherwise.
        :rtype: bool
        """
        if not self.config.get_boolean(section, 'use_datetime_restriction'):
            return True
        if most_recent_attempt_datetime is None:
            return True
        datetime_object = datetime.strptime(self.config.get_string(section, 'retry_after_datetime'),
                                            '%m/%d/%Y %H:%M:%S')
        return datetime_object < most_recent_attempt_datetime

    def _download_url_to_pdf_bin(self, doi_entry, url, path):
        """Retrieves content from a specified URL, checks if it's in PDF format,
        and saves it as a binary PDF file. It also handles the creation of directories for
        organizing downloaded PDFs.

        :param doi_entry: The DOI entry object associated with the download.
        :type doi_entry: DoiEntry

        :param url: The URL from which to download the content.
        :type url: str

        :param path: The base directory path where the PDF should be saved.
        :type path: str

        :return: A tuple indicating the download status and HTTP status code. - If download is successful, the first element is True, and the second element is the HTTP status code. - If download fails or the content is not in PDF format, the first element is False, and the second element is the HTTP status code.
        :rtype: tuple[bool, int]
        """
        headers = {
            'User-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'}
        r = requests.get(url, headers=headers, allow_redirects=True, timeout=120, verify=False)

        # download by sending a http request, if url isnt a html
        if 'html' not in r.headers['Content-Type']:
            logging.warning(f"not html, downloading: {r.headers['Content-Type']} {url}")
            new_directory = os.path.join(path, doi_entry.issn, str(doi_entry.published_date.year))
            if not os.path.exists(new_directory):
                print(f"Creating new PDF directory: {new_directory}")
                os.makedirs(new_directory)
            filename = os.path.join(new_directory, Utils.get_filename_from_doi_string(doi_entry.doi))
            with open(filename, "wb") as f:
                logging.info(f"Downloaded {doi_entry.doi} to {filename}.")
                f.write(r.content)
            # testing: line below simulate a 503 status code for testing purposes
            # return (False, 503)
            return True, r.status_code

        # raise error if url is a html
        else:
            logging.error(f"Not a PDF, can't download. Code: {r.status_code}: {r.headers['Content-Type']} {url}")
            # testing: line below simulate a 503 status code for testing purposes
            # return (False, 503)

            return False, r.status_code

    @abstractmethod
    def download(self, doi_entry):
        """_summary_

        :param doi_entry: _description_
        :type doi_entry: _type_
        :raises NotImplementedError: _description_
        """
        raise NotImplementedError()

    @abstractmethod
    def create_tables(self):
        """_summary_

        :raises NotImplementedError: _description_
        """
        raise NotImplementedError()

    class TimeoutError(Exception):
        pass

    def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
        """_summary_

        :param seconds: _description_, defaults to 10
        :type seconds: int, optional
        :param error_message: _description_, defaults to os.strerror(errno.ETIME)
        :type error_message: _type_, optional
        """

        def decorator(func):
            def _handle_timeout(signum, frame):
                raise TimeoutError(error_message)

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                signal.signal(signal.SIGALRM, _handle_timeout)
                signal.alarm(seconds)
                try:
                    result = func(*args, **kwargs)
                finally:
                    signal.alarm(0)
                return result

            return wrapper

        return decorator

    @timeout(3)
    def _close_firefox(self, driver):
        """_summary_

        :param driver: _description_
        :type driver: _type_
        """
        driver.close()

    def cleandir(self, path):
        """_summary_

        :param path: _description_
        :type path: _type_
        """
        dir = path
        for files in os.listdir(dir):
            path = os.path.join(dir, files)
            try:
                shutil.rmtree(path)
            except OSError:
                os.remove(path)

    def get_latest_downloaded_file(self, tmp_pdf_directory):
        """
        Takes a directory path as input and returns the full path
        and name of the latest file downloaded in that directory.

        :param directory_issn_year: The path to the directory containing downloaded files.
        :type directory_issn_year: str
        :return: A tuple containing the full path and name of the latest downloaded file.
        :rtype: tuple
        """
        # Get a list of all files in the specified download path
        list_of_files = os.listdir(tmp_pdf_directory)
        if list_of_files is None or len(list_of_files) < 1:
            return None
        # Use the max function to find the file with the latest creation time
        latest_file = max(list_of_files, key=lambda x: os.path.getctime(os.path.join(tmp_pdf_directory, x)))
        print(latest_file)

        # Construct the full path to the latest file
        directory_issn_year_textname = os.path.join(tmp_pdf_directory, latest_file)
        return directory_issn_year_textname

    def check_and_rename_file(self, tmp_pdf_directory, doi_entry, pdf_directory):
        """checks if the latest downloaded file exists in the specified
        directory. If the file exists, it is renamed to it's DOI#

        :param tmp_pdf_directory: The path to the directory containing downloaded files.
        :type tmp_pdf_directory: str
        :param doi: The DOI (Digital Object Identifier) used for renaming the file.
        :type doi: str
        :return: True if the file is successfully downlaoded and renamed, False otherwise.
        :rtype: bool
        """
        temp_pdf_directory_filename = self.get_latest_downloaded_file(tmp_pdf_directory)

        # Check if the file exists at the specified file path
        if temp_pdf_directory_filename is not None and os.path.exists(temp_pdf_directory_filename):

            # Construct the full path to the new file
            destination_path = os.path.join(pdf_directory,
                                            doi_entry.issn,
                                            str(doi_entry.published_date.year),
                                            Utils.get_filename_from_doi_string(doi_entry.doi))

            # copy the existing file to the new file name
            # rsync required to bypass ACL permisisons
            # preservation when moving betwen filesystems.
            rsync_command = [
                "rsync", "-av", "--no-perms", "--no-owner", "--no-group",
                temp_pdf_directory_filename, destination_path
            ]

            # Execute the rsync command
            subprocess.run(rsync_command)


            # Log a success message
            logging.info(f"File successfully downloaded to {temp_pdf_directory_filename} and renamed to {destination_path}")
            return True
        else:
            # Log a message if the file does not exist
            logging.error("Download unsuccessful. File not found. Returning failure. ")
            return False

    def _firefox_downloader(self, url, doi_entry, pdf_directory):
        """Download PDF using Firefox/Selenium with headless download."""
        logging.info(f"Attempting download using firefox/selenium: {url}")

        # Retrieve configurations only once
        tmp_firefox_pdf_directory = f'{self.config.get_string("downloaders", "tmp_firefox_pdf_directory")}.{os.getpid()}'
        page_load_timeout = self.config.get_int('downloaders', 'firefox_page_load_timeout')
        try:
            shutil.rmtree(tmp_firefox_pdf_directory)
        except FileNotFoundError:
            # this is fine, we want it gone either way
            pass
        self._create_directory_if_not_exists(tmp_firefox_pdf_directory)

        # Set Firefox options
        options = self._configure_firefox_options(tmp_firefox_pdf_directory)

        with webdriver.Firefox(options=options) as browser:
            browser.set_page_load_timeout(page_load_timeout)
            try:
                browser.get(url)
            except TimeoutException as e:
                logging.error("Firefox/Selenium timed out. Checking for download....")

            return self.check_and_rename_file(tmp_firefox_pdf_directory, doi_entry, self.PDF_DIRECTORY)

    def _create_directory_if_not_exists(self, directory):
        """Create directory if it doesn't exist."""

        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                logging.error(f"Error creating directory: {e}")
                raise e


    from selenium.webdriver.firefox.options import Options

    def _configure_firefox_options(self, download_directory):
        """Configure Firefox options for headless download."""
        options = Options()

        # Set preferences for file download
        options.set_preference("browser.download.folderList", 2)  # custom location
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.dir", download_directory)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf,application/x-pdf")

        # Disable the built-in PDF viewer to avoid viewing PDFs in the browser
        options.set_preference("pdfjs.disabled", True)

        # Enable headless mode for Firefox
        options.add_argument("--headless")

        # Set environment variable for headless mode (if needed)
        os.environ['MOZ_HEADLESS'] = '1'

        return options


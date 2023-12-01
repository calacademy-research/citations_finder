from abc import ABC, ABCMeta, abstractmethod
from config import Config
import requests
from utils_mixin import Utils
from datetime import datetime
import os
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
import glob
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import errno
import signal
import functools
import shutil
from selenium.common.exceptions import WebDriverException
import pyautogui
import logging

from selenium.webdriver.firefox.options import Options
from db_connection import DBConnection


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
        
        #download by sending a http request, if url isnt a html
        if 'html' not in r.headers['Content-Type']:
            logging.warning(f"not html, downloading: {r.headers['Content-Type']} {url}")
            new_directory = os.path.join(path, doi_entry.issn, str(doi_entry.date.year))
            if not os.path.exists(new_directory):
                print(f"Creating new PDF directory: {new_directory}")
                os.makedirs(new_directory)
            filename = os.path.join(new_directory, Utils.get_filename_from_doi_string(doi_entry.doi))
            with open(filename, "wb") as f:
                logging.info(f"Downloaded {doi_entry.doi} to {filename}.")
                f.write(r.content)
            #testing: line below simulate a 503 status code for testing purposes
            #return (False, 503)
            return (True, r.status_code)
        
        #raise error if url is a html
        else:
            logging.error(f"Not a PDF, can't download. Code: {r.status_code}: {r.headers['Content-Type']} {url}")
            #testing: line below simulate a 503 status code for testing purposes
            #return (False, 503)

            return (False, r.status_code)

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

    def get_latest_downloaded_file(self, directory_issn_year):
        """
        Takes a directory path as input and returns the full path
        and name of the latest file downloaded in that directory.

        :param directory_issn_year: The path to the directory containing downloaded files.
        :type directory_issn_year: str
        :return: A tuple containing the full path and name of the latest downloaded file.
        :rtype: tuple
        """        
        # Get a list of all files in the specified download path
        list_of_files = os.listdir(directory_issn_year)

        # Use the max function to find the file with the latest creation time
        latest_file = max(list_of_files, key=lambda x: os.path.getctime(os.path.join(directory_issn_year, x)))
        print(latest_file)

        # Construct the full path to the latest file
        directory_issn_year_textname= os.path.join(directory_issn_year, latest_file)
        return directory_issn_year_textname,latest_file

    def check_and_rename_file(self,directory_issn_year, doi):
        """checks if the latest downloaded file exists in the specified
        directory. If the file exists, it is renamed to it's DOI#

        :param directory_issn_year: The path to the directory containing downloaded files.
        :type directory_issn_year: str
        :param doi: The DOI (Digital Object Identifier) used for renaming the file.
        :type doi: str
        :return: True if the file is successfully downlaoded and renamed, False otherwise.
        :rtype: bool
        """        
        directory_issn_year_textname, latest_file = self.get_latest_downloaded_file(directory_issn_year)
        
        # Check if the file exists at the specified file path
        if os.path.exists(directory_issn_year_textname):

            # Construct the full path to the new file
            directory_issn_year_doiname = os.path.join(os.path.dirname(directory_issn_year_textname), 
                                                    Utils.get_filename_from_doi_string(doi))
            
            # Rename the existing file to the new file name
            os.rename(directory_issn_year_textname, directory_issn_year_doiname)
            
            # Log a success message
            logging.info(f"File successfully downloaded to {directory_issn_year} and renamed to {doi}")
            return True
        else:
            # Log a message if the file does not exist
            logging.error("Download unsuccessful. File not found. Returning failure. ")
            return False

    def _firefox_downloader(self, url, doi_entry):
        """Attempts to download a PDF file from the specified URL
        using the Firefox browser controlled by Selenium. It sets preferences for
        headless download and saves the file in a directory based on the ISSN and
        publication year.

        :param url: The URL of the PDF file to be downloaded.
        :type url: str
        :param doi_entry: An object containing information about the DOI entry.
        :type doi_entry: DOIEntry
        :return: True if the download and renaming process is successful, False otherwise.
        :rtype: bool
        """        
        logging.info(f"Attempting download using firefox/selenium: {url}")

        options = Options()


         #creating directory in which pdfs will be stored
        path = self.config.get_string('downloaders', 'firefox_save_directory')
        directory_issn_year = os.path.join(path, doi_entry.issn, str(doi_entry.date.year))
        if not os.path.exists(directory_issn_year):
            print(f"Creating new PDF directory: {directory_issn_year}")
            os.makedirs(directory_issn_year)
        

        #setting preferences
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.dir", directory_issn_year)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf,application/x-pdf")
        #below line triggers brower.get to hang and timeout. Without it, headless function wouldnt work
        options.set_preference("pdfjs.disabled", True)
        options.add_argument("--headless")
        os.environ['MOZ_HEADLESS'] = '1'


        #Initializing browser
        browser = webdriver.Firefox(options=options)

        browser.set_page_load_timeout(self.config.get_int('unpaywall_downloader', 'firefox_page_load_timeout'))

        try:
            try:
                #performs headless download
                browser.get(url)


            except TimeoutException as e:
                logging.error(f"Firefox/selenium timed out. Now checking whether pdf has been downloaded prior to timing out")

            finally:
                #check whether file has been downloaded prior to time out, if so, rename it, other wise, make uncessful downlaod
                return self.check_and_rename_file(directory_issn_year,doi_entry.doi)
        
        finally:
            browser.quit()



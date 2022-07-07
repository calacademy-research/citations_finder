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
import os
import signal
import functools
import shutil


import pyautogui

class Downloader(ABC, Utils):
    __metaclass__ = ABCMeta

    def __init__(self):
        self.DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

        self.config = Config()

        self.PDF_DIRECTORY = self.config.get_string("downloaders", "pdf_directory")
        if not os.path.exists(self.PDF_DIRECTORY):
            print(f"PDF directory missing; creating now: {self.PDF_DIRECTORY}")
            os.mkdir(self.PDF_DIRECTORY)
        header_email = self.config.get_string("downloaders", "header_email")
        self.headers = {
            'User-Agent': f'development; mailto:{header_email}',
        }

    def meets_datetime_requrements(self, section, most_recent_attempt_datetime):
        if not self.config.get_boolean(section, 'use_datetime_restriction'):
            return True
        if most_recent_attempt_datetime is None:
            return True
        datetime_object = datetime.strptime(self.config.get_string(section, 'retry_after_datetime'),
                                            '%m/%d/%Y %H:%M:%S')
        return datetime_object < most_recent_attempt_datetime

    def _download_url_to_pdf_bin(self, doi_entry, url, path):
        headers = {
            'User-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'}
        r = requests.get(url, headers=headers, allow_redirects=True, timeout=120)
        if 'html' not in r.headers['Content-Type']:
            print(f"not html, downloading: {r.headers['Content-Type']} {url}")

            filename = os.path.join(path, Utils.get_filename_from_doi_string(doi_entry.doi))
            with open(filename, "wb") as f:
                print(f"Downloaded {doi_entry.doi} to {filename}.")
                f.write(r.content)
            return True
        else:
            # print(f"Not a PDF, can't download: {r.headers['Content-Type']} {url}")
            raise TypeError(f"Not a PDF, can't download: {r.headers['Content-Type']} {url}")

    @abstractmethod
    def download(self, doi_entry):
        raise NotImplementedError()

    class TimeoutError(Exception):
        pass

    def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
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
    def _close_firefox(self,driver):
        driver.close()

    def cleandir(self,path):
        dir = path
        for files in os.listdir(dir):
            path = os.path.join(dir, files)
            try:
                shutil.rmtree(path)
            except OSError:
                os.remove(path)

    def _firefox_downloader(self, url, doi_entry):
        print(f"Attempting download using firefox/selenium: {url}")

        # Doesn't work. Too bad.
        # directory = './webdriver'
        # options = Options()
        # options.set_preference('browser.download.folderList', 2)  # custom location
        # options.set_preference('browser.download.manager.showWhenStarting', False)
        # options.set_preference('browser.download.dir', directory)
        # options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf")
        # driver = webdriver.Firefox(options=options)
        driver = webdriver.Firefox()

        driver.get(url)

        time.sleep(3)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "pdfViewer"))
            )
        except TimeoutException:
            print("Timeout, never found a pdfviewer")
            pass

        pyautogui.keyDown('command')
        pyautogui.press('s')
        pyautogui.keyUp('command')
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(3)
        pyautogui.keyDown('command')
        pyautogui.press('q')
        pyautogui.keyUp('command')
        time.sleep(1)

        try:
            self._close_firefox(driver)
        except Exception:
            print("timeout hit, continuing...")

        # driver.close()

        firefox_download_folder = self.config.get_string("unpaywall_downloader", "firefox_save_directory")

        list_of_files = glob.glob(f'{firefox_download_folder}/*')
        try:
            latest_file = max(list_of_files, key=os.path.getctime)
        except ValueError:
            print("No files saved, marking as failed.")
            return False
        if not latest_file.lower().endswith(".pdf"):
            print("No PDF file found, returning failure. ")
            self.cleandir(firefox_download_folder)
            return False

        destination = f"{self.PDF_DIRECTORY}/{Utils.get_filename_from_doi_string(doi_entry.doi)}"
        os.rename(f"{latest_file}", destination)

        print(f"Downloaded {destination}")
        return True
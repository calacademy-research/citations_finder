from json import JSONDecodeError

import requests
import ntpath
import time
import re
import logging

class Utils:
    def __init__(self):
        self.response_time = 0

    def _get_url_(self, url, headers=None, decode_json=True):
        if self.response_time > 20:
            logging.info(f"Long wait time ({self.response_time} seconds), backing off 60 seconds on request {url}")
            time.sleep(60)
        elif self.response_time > 10:
            logging.info(f"Long wait time ({self.response_time} seconds), backing off 30 seconds on request {url}")
            time.sleep(30)
        elif self.response_time > 4:
            logging.info(f"Long wait time ({self.response_time} seconds), backing off 5 seconds on request {url}")
            time.sleep(5)

        start = time.time()

        if headers is None:
            response = requests.get(url, allow_redirects=True)
        else:
            response = requests.get(url, allow_redirects=True, headers=headers)
        self.response_time = time.time() - start
        logging.info(f"Request took {self.response_time}")
        if response.status_code != 200:
            # logging.error(f"Fail to get url: {url} ")
            raise ConnectionError(url)
        if decode_json:
            try:
                return response.json()
            except JSONDecodeError as e:
                logging.error(f"Invalid JSON:\n{response}")
                raise ConnectionError(f"{e}")
        else:
            return response

    @staticmethod
    def get_filename_from_doi_string(doi_string):
        sanitized_identifier = doi_string.replace('/', '_')
        dest_path = sanitized_identifier + ".pdf"
        return dest_path

    def get_filename_from_doi_entry(self):
        return Utils.get_filename_from_doi_string(self.doi)

    def get_doi_from_path(self, path):
        filename = ntpath.basename(path)
        filename = filename.rsplit(".", 1)[0]
        filename = filename.replace('_', '/')
        return filename

    def clean_string(self, raw):
        cleanr = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
        cleantext = re.sub(cleanr, '', raw)
        cleanr = re.compile('[^A-Z a-z0-9]+')
        cleantext = re.sub(cleanr, '', cleantext)
        return cleantext

    def sql_year_restriction(self, start_year, end_year):
        if start_year is not None and end_year is not None:
            return f"""published_date BETWEEN 
                '{start_year}-01-01' AND '{end_year}-12-31'"""

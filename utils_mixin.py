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
        """Perform an HTTP GET request to "https://api.crossref.org/works/{doi_string}"
            and return JSON response, decoded

        :param url: The URL to send the GET request to.
        :type url: str

        :param headers: Optional headers to include in the request, defaults to None.
        :type headers: dict, optional

        :param decode_json: Flag indicating whether to decode the 
            response as JSON, defaults to True.
        :type decode_json: bool, optional

        :raises ConnectionError: If request to url fails. Provides the url.
        :raises ConnectionError: If there is an error decoding the JSON response.
            Provides the string representation of the caught exceptions.
        
        :return: The response from the URL, either as a decoded JSON object (if `decode_json` is True) or as a raw response.
        :rtype: dict or requests.Response
        """        
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
        """Extracts the DOI from a given file path by removing ".pdf" and 
        replace "_" with "/" to conform with the DOI format. 

        Example: Convert "10.11646_phytotaxa.388.2.3.pdf" to
        "10.11646/phytotaxa.388.2.3" 

            :param path: The path of the file containing the DOI
            :type path: str

            :return: The extracted DOI from the file path
            :rtype: str
        """        
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
        """Generates an SQL date range condition based on the start 
        and end years provided. It creates a SQL WHERE clause to 
        filter records within the specified year range.

        :param start_year: The start year of the date range.
        :type start_year: int
        :param end_year: The end year of the date range.
        :type end_year: int
        :return: An SQL date range condition in the form of a string.
        :rtype: str
        """        
        if start_year is not None and end_year is not None:
            return f"""published_date BETWEEN 
                '{start_year}-01-01' AND '{end_year}-12-31'"""

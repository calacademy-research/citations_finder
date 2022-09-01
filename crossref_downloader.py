from downloader import Downloader
import traceback
from requests import exceptions
import requests
import re
import http
import logging

class CrossrefDownloader(Downloader):

    def __init__(self):
        super().__init__()

    def download(self, doi_entry):
        logging.info(f"Download unpaywall:{doi_entry}")
        return self._download_crossref(doi_entry, self.PDF_DIRECTORY)

    def _download_crossref(self, doi, path="./"):
        try:
            url = self._crossref_get_direct_link(doi)
            logging.info(f"Attempting crossref link: {url}")
            results = self._get_url_(url, decode_json=False)
            ref_url = results.url
            logging.info(f"Got crossref referred URL:{ref_url}")
            r = requests.get(ref_url, timeout=120)

            response, self.error_code = self._download_url_to_pdf_bin(ref_url, doi, path)
            if not response and self.error_code == 200:
                logging.warning("Didn't return pdf link, parsing...")
                pattern = "(https?:\/\/[a-zA-Z0-9\-]+\.[a-zA-Z0-9]+[a-zA-Z\/\-0-9\.]+(?i)[.]pdf)"
                regexp = re.compile(pattern)
                re_match = regexp.findall(r.text)
                # logging.debug(f"{re_match}")
                unique_match = list(set(re_match))
                if len(unique_match) > 1:
                    logging.warning("Multiple links! Will not proceed.")
                    for link in unique_match:
                        logging.info(f"   {link}")
                    return False
                if len(unique_match) == 0:
                    logging.warning(f"No PDF link found.")
                    return False
                link = unique_match[0]
                logging.info(f"Candidate pdf link found: {link}. Attempting download....")
                try:
                    results, self.error_code = self._download_url_to_pdf_bin(link, doi, path)
                    if results is True:
                        logging.info(f"Successful download from PDF extraction: {link}")
                    self.full_path = path
                    self.downloaded = True
                    return results
                except TypeError as e:
                    logging.warning(f"Can't download {ref_url}: {e}")
                    return False

        except exceptions.HTTPError as e:
            logging.warning(f"Crossref download failure: {e}")
            return False
        except ConnectionError as e:
            logging.warning(f"Crossref lookup failure: {e}")
            return False
        except http.client.RemoteDisconnected as e:
            print(f"Remote disconnected from crossref:{e}")
            return False
        except Exception as e:
            traceback.print_exc()
            print(f"Unexpected exception: {e}")
            return False

import os
import importlib
from config import Config
import sys
from datetime import datetime
import logging
import random
from doi_entry import DoiEntry


class Downloaders:

    def __init__(self):
        """First, remove any "unpaywall_cache". 
        Second, initialize an empty list "self.downloaders". 
        Then, Loops over [dowbloaders] -> modules, and 
        split the text with "_", turn into camel case.  
        Lastly, creates instances of classes from those modules 
        to populate the self.downloaders list
        """        
        if os.path.exists("unpaywall_cache"):
            os.remove("unpaywall_cache")

        self.config = Config()
        modules = self.config.get_list('downloaders', 'modules')

        self.downloaders = []
        for module in modules:
            python_module = self.module_import(module)

            temp = module.split('_')
            camel_module = temp[0].capitalize() + ''.join(ele.title() for ele in temp[1:])
            klass = getattr(python_module, camel_module)
            self.downloaders.append(klass())

    def module_import(self, module_name):
        """Imports and returns a module dynamically based on the provided module name.

        :param module_name: The name of the module to import.
        :type module_name: str
        :return: The imported module.
        :rtype: module
        """        
        spec = importlib.util.find_spec(module_name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module] = module
        return module


    def download_list(self, doi_list):
        """Download DOI entries in serial order.

        This method downloads DOI entries from the given list in a serial (sequential) order.
        It iterates through each DOI entry in the list and calls the `download` method on it.
        If the download is successful, the DOI entry is marked as a successful download using
        the `mark_successful_download` method.

        :param doi_list: A list of DOIEntry objects representing the DOI entries to be downloaded.
        :type doi_list: List[DOIEntry]
        """        
        randomize = self.config.get_boolean("downloaders","randomize_download_order")
        if randomize:
            random.shuffle(doi_list)

        for doi_entry in doi_list:
        # logging.warning(f"journal:{doi_entry.journal_title} not found: {doi_entry.not_found_count} doi: {doi_entry.doi}")
            if self.download(doi_entry):
                doi_entry.mark_successful_download()



    def download(self, doi_entry:DoiEntry):
        """Download a DOI entry using downloader(s) specified in config.ini -> 
        downloaders] -> modules = ["unpaywall_downloader"]

        :param doi_entry: The DOI entry to download.
        :type doi_entry: DoiEntry
        :type doi_entry: str
        :return: True if the download is successful, False otherwise.
        :rtype: bool

        Switched the order of 'if doi_entry.check_file()' and 'if doi_entry.downloaded',
        encountered a case 'download_single_doi = 10.1073/pnas.1719260115' where it's marked 
        as downloaded in db but not downloaded to path. Should check_file first before check downloaded
        """     
        if doi_entry.check_and_update_file_path_variables():
            logging.info(f"PDF already downloaded; marking {doi_entry.doi} as downloaded ")
            return True


        logging.info("==================================================================")
        logging.info(f"Attempting download: {datetime.now()}:{doi_entry.doi} journal: {doi_entry.get_journal()}")
        
        #below line is performing download action
        #the code iterates over each element (downloader) in this list and calls the download 
        # method on each of them, passing doi_entry as an argument. If any of these downloaders 
        # return True, indicating a successful download, the method returns True. Otherwise, 
        # if none of the downloaders succeed, it returns False.
        for downloader in self.downloaders:
            if downloader.download(doi_entry):
                return True
        return False

    def create_tables(self):
        """Creates tables for each downloader in the list of downloaders.

        This method iterates over the downloaders and calls their respective 'create_tables' methods.
        Each downloader is responsible for creating its own required tables.
        """         
         

        for downloader in self.downloaders:
            downloader.create_tables()
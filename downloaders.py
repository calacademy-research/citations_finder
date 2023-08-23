import os
import importlib
from config import Config
import sys
from datetime import datetime
import concurrent.futures
from more_itertools import grouper
import logging
from doi_entry import DoiEntry

class Downloaders:

    def __init__(self):
        """First, remove any "unpaywall_cache". 
        Second, initialize an empty list "self.downloaders". 
        Then, Loops over "modules = ["unpaywall_downloader"]", and 
        split the text with "_", turn into camel case.  
        Lastly, retrieve the attribute of "python_module", but use the camel case name
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

    def download_list_parallel(self, doi_list):
        """Uses ProcessPoolExecutor to download DOI entries from 
        the given list in parallel. It divides the DOI entries into groups using 
        the `grouper` function and submits each group to the executor
        for parallel downloading. The number of parallel processes is set to 10.

        :param doi_list: A list of DOIEntry objects representing the DOI entries to be downloaded.
        :type doi_list: List[DOIEntry]
        """        
        executor = concurrent.futures.ProcessPoolExecutor(10)
        futures = [executor.submit(self.download_list_serial, group)
                   for group in grouper(5, doi_list)]
        concurrent.futures.wait(futures)

    def download_list(self, doi_list):
        """Download DOI entries in the given list.

    
        It checks the configuration to determine whether to use the parallel downloader or the serial downloader.
        If the parallel downloader is enabled, the method will invoke the `download_list_parallel` method.
        Otherwise, it will use the `download_list_serial` method to download the DOI entries in serial order.

        :param doi_list: A list of DOIEntry objects representing the DOI entries to be downloaded.
        :type doi_list: List[DOIEntry]
        """        
        parallel = self.config.get_boolean('downloaders', 'parallel_downloader')
        if parallel:
            self.download_list_parallel(doi_list)
        else:
            self.download_list_serial(doi_list)

    def download_list_serial(self, doi_list):
        """Download DOI entries in serial order.

        This method downloads DOI entries from the given list in a serial (sequential) order.
        It iterates through each DOI entry in the list and calls the `download` method on it.
        If the download is successful, the DOI entry is marked as a successful download using
        the `mark_successful_download` method.

        :param doi_list: A list of DOIEntry objects representing the DOI entries to be downloaded.
        :type doi_list: List[DOIEntry]
        """        

        for doi_entry in doi_list:
        # logging.warning(f"journal:{doi_entry.journal_title} not found: {doi_entry.not_found_count} doi: {doi_entry.doi}")
            if self.download(doi_entry):
                doi_instance = DoiEntry(doi_entry)
                doi_instance.mark_successful_download()

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
        if doi_entry.check_file():
            logging.info(f"PDF already downloaded; marking {doi_entry.doi} as downloaded ")
            return True
        
        #how does python know to look at the downloaded column in dois table?
        if doi_entry.downloaded:
            return True
    
        logging.info("==================================================================")
        logging.info(f"Attempting download: {datetime.now()}:{doi_entry.doi} journal: {doi_entry.get_journal()}")
        
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
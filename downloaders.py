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
        spec = importlib.util.find_spec(module_name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module] = module
        return module

    def download_list_parallel(self, doi_list):
        executor = concurrent.futures.ProcessPoolExecutor(10)
        futures = [executor.submit(self.download_list_serial, group)
                   for group in grouper(5, doi_list)]
        concurrent.futures.wait(futures)

    def download_list(self, doi_list):
        parallel = self.config.get_boolean('downloaders', 'parallel_downloader')
        if parallel:
            self.download_list_parallel(doi_list)
        else:
            self.download_list_serial(doi_list)

    def download_list_serial(self, doi_list):
        for doi_entry in doi_list:
            # logging.warning(f"journal:{doi_entry.journal_title} not found: {doi_entry.not_found_count} doi: {doi_entry.doi}")

            if self.download(doi_entry):
                doi_entry.mark_successful_download()

    def download(self, doi_entry: DoiEntry):
        if doi_entry.downloaded:
            return True
        if doi_entry.check_file():
            logging.info(f"PDF already downloaded; marking {doi_entry.doi} as downloaded ")

            return True
        logging.info("==================================================================")
        logging.info(
            f"Attempting download: {datetime.now()}:{doi_entry.doi} journal: {doi_entry.get_journal()}")
        for downloader in self.downloaders:

            if downloader.download(doi_entry):
                return True
        return False

    def create_tables(self):
        for downloader in self.downloaders:
            downloader.create_tables()
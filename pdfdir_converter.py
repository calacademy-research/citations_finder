import os
import shutil
from utils_mixin import Utils
from config import Config
from db_connection import DBConnection


class PDFDirConverter():

    def __init__(self, pdf_directory):
        self.PDF_DIRECTORY = pdf_directory

    def sortDownloads(self):
        total = len(os.listdir(self.PDF_DIRECTORY))
        count = 0
        util = Utils()
        print(f"Beginning PDF sort of directory: {self.PDF_DIRECTORY}")
        for filename in os.listdir(self.PDF_DIRECTORY):
            count += 1
            if (count % 10 == 0):
                print(f"...Processing {count} out of {total}")
            file_path = os.path.join(self.PDF_DIRECTORY, filename)
            if os.path.isfile(file_path):
                doi = util.get_doi_from_path(file_path)
                issn = self._getISSN(doi, file_path)
                if issn == None:
                    continue
                year = self._getYear(doi, file_path)
                new_directory = os.path.join(self.PDF_DIRECTORY, issn, year)
                if not os.path.exists(new_directory):
                    print(f"Creating new PDF directory: {new_directory}")
                    os.makedirs(new_directory)
                new_file_path = os.path.join(new_directory, filename)
                shutil.move(file_path, new_file_path)
                self._updateDatabasePath(doi, new_file_path)
        print('Finished!')

    def _getISSN(self, doi, path):
        query = f"""SELECT issn from dois WHERE doi = '{doi}'"""
        result = DBConnection.execute_query(query)
        if len(result) == 0:
            print(f"...Skipping '{path}': doi not found in database")
            return
        else:
            issn = result[0][0]
            return issn

    def _getYear(self, doi, path):
        query = f"""SELECT published_date from dois WHERE doi = '{doi}'"""
        result = DBConnection.execute_query(query)
        year = result[0][0][:4]
        return year
    
    def _updateDatabasePath(self, doi, path):
        query = f"""UPDATE dois SET full_path='{path}' WHERE doi='{doi}'"""
        DBConnection.execute_query(query)


if '__main__' == __name__:
    config = Config()
    # You can change pdf_directory for testing
    pdf_directory = config.get_string("downloaders", "pdf_directory")
    p = PDFDirConverter(pdf_directory)
    p.sortDownloads()

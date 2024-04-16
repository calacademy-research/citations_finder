from db_connection import DBConnection
import os
from shutil import copyfile
from utils_mixin import Utils
from doi_database import DoiDatabase
import logging


class CopyOut(Utils):
    def __init__(self, year, config):
        self.year = year
        self.config = config

    def get_matches(self):
        """executes query to retrieve rows from two tables - 
        matches, and doi - and keeps the row if doi exists in both 
        table and 'ignore' column in 'matches' table is 0.

        :return: The query results containing matched rows.
        :rtype: list
        """
        sql = f"""select matches.doi, 
                    matches.collection,
                    dois.full_path,
                    dois.published_date,
                    dois.journal_title, 
                    matches.date_added, 
                    matches.notes, 
                    matches.digital_only 
                    from matches, dois where matches.doi = dois.doi and 
                    matches.skip != 1 and
                    dois.{self.sql_year_restriction(self.year, self.year)} order by collection,dois.published_date"""
        results = DBConnection.execute_query(sql)
        return results

    def get_textfile_path(self, doi):
        sql = "SELECT textfile_path FROM collections_papers.scans WHERE doi = %s"
        result = DBConnection.execute_query(sql, (doi,))
        return result[0][0] if result and result[0][0] is not None else None

    def make_target_dir(self, dest_dir, collection):
        """Creates directories that are 3 layers deep,
        'publish', defined in config.ini -> collection -> year

        :param dest_dir: directory (where main.py is stored)
        :type dest_dir: str
        :param collection: collections directory, i.e. botany, within dest_dir
        :type collection: str
        :return: year directory within collection_dir
        :rtype: str
        """
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        collection_dir = dest_dir + f"/{collection}"
        if not os.path.exists(collection_dir):
            os.makedirs(collection_dir)
        year_dir = collection_dir + f"/{self.year}"
        if not os.path.exists(year_dir):
            os.makedirs(year_dir)
        return year_dir

    def _copy_out_file(self, origin_path, collection, dest_dir):
        """Copies an origin file to the destination directory based on the given collection.

        :param origin_path: The path of the origin file to be copied.
        :type origin_path: str
        :param collection: The name of the collection directory to copy the file into.
        :type collection: str
        :param dest_dir: The destination directory where the file will be copied.
        :type dest_dir: str
        """
        target_dir = self.make_target_dir(dest_dir, collection)
        target = target_dir + f"/{os.path.basename(origin_path)}"
        if not os.path.exists(target):
            if target.endswith('.pdf'):
                print(f"New Paper from {origin_path}")
            elif target.endswith('.txt'):
                print(f"New Text from {origin_path}")
            copyfile(origin_path, target)
        else:
            if target.endswith('.pdf'):
                print(f"Paper Already Copied from {origin_path}")
            elif target.endswith('.txt'):
                print(f"Text Already Copied from {origin_path}")

    def generate_file_path(self, doi, file_type='txt'):
        """Generates the full file path for text or PDF files based on DOI.

        :param doi: The DOI of the paper for which to generate the file path.
        :type doi: str
        :param file_type: The type of file to generate path for ('txt' or 'pdf').
        :type file_type: str

        :return: The generated full file path to the file.
        :rtype: str
        """
        # Query to get the issn and published year based on the DOI
        sql = f"SELECT issn, YEAR(published_date) FROM collections_papers.dois WHERE doi='{doi}'"
        results = DBConnection.execute_query(sql)

        if len(results) > 0:
            issn, year = results[0]
            # Get the base directory from the config depending on file type
            if file_type == 'pdf':
                base_path = self.config.get_string("downloaders", "pdf_directory")
            else:  # default to text file directory
                base_path = self.config.get_string("scan", "scan_text_directory")
            # Normalize DOI for filename usage
            normalized_doi = doi.replace('/', '_')
            # Constructing the file path
            file_path = os.path.join(base_path, issn, str(year), f"{normalized_doi}.{file_type}")
            return file_path

        else:
            print(f"No results for doi {doi}!!! : {sql}")
            return None

    def copy_out_files(self, dest_dir="./"):
        """Copies files based on the matched rows retrieved from the 
        database, 'matches' table.
        Skips copying if the 'digital_only' flag is True.

        :param dest_dir: The destination directory where the files will be copied to, defaults to "./"
        :type dest_dir: str, optional
        """
        for cur_match in self.get_matches():
            doi = cur_match[0]
            collection = cur_match[1]
            origin_path = self.generate_file_path(doi,"pdf")
            digital_only = bool(cur_match[7])
            if digital_only is True:
                print("Digital only")
                continue

            self._copy_out_file(origin_path, collection, dest_dir)

            if self.config.get_boolean("copyout", "copyout_txt"):
                text_path = self.generate_file_path(doi,"txt")
                if os.path.exists(text_path):
                    self._copy_out_file(text_path, collection, dest_dir)
                else:
                    print(f"  Missing text file: {text_path}")

    def write_match(self, cur_match, filehandle, db):
        """Write a matched data record to a file.

        The matached data record has 2 parts. The first part includes DOI. 
        The second part is "identifier" from "matched_collectin_ids" table in 
        the databse (example: cas 229582)

        :param cur_match: A tuple containing matched data fields, including DOI, collection, origin_path,published_date, journal_title, date_added, notes, and digital_only.
        :type cur_match: tuple
        :param filehandle: The file handle where the matched data will be written.
        :type filehandle: file
        :param db: An instance of the DoiDatabase class used for retrieving DOI record information.
        :type db: DoiDatabase
        """
        doi = cur_match[0]
        doi_record = db.get_doi(doi)
        collection = cur_match[1]
        origin_path = cur_match[2]
        published_date = cur_match[3]
        journal_title = cur_match[4]
        date_added = cur_match[5]
        notes = cur_match[6]
        digital_only = cur_match[7]
        title = self.clean_string(doi_record.get_title())
        write_string = f"{doi}\t{collection}\t{journal_title}\t{title}\t{published_date}\t{date_added}\t{notes}\t{digital_only}"
        write_string = write_string.replace('None', '-')
        filehandle.write(write_string)
        sql = f"select identifier from matched_collection_ids where matched_collection_ids.doi='{doi}'"
        results = DBConnection.execute_query(sql)

        if len(results) > 0:
            filehandle.write("\t")
            for count, result in enumerate(results):
                result = result[0]
                filehandle.write(result)
                if count < len(results) - 1:
                    filehandle.write(",")
        filehandle.write("\n")

    def dump_file_tsv(self, path="./"):
        """Dump the matched data to a TSV file.

        :param path: The directory path where the TSV file will be saved. Defaults to "./".
        :type path: str, optional
        """
        if not os.path.exists(path):
            os.makedirs(path)
        db = DoiDatabase(self.config)
        filename = f"{path}/matched_{self.year}.tsv"
        fh = open(filename, "w")
        fh.write("doi\tcollection\tjournal_title\ttitle\tpublished_date\tdate_added\tnotes\tdigital_only\n")
        for cur_match in self.get_matches():
            self.write_match(cur_match, fh, db)

    def dump_custom(self, special_note_string, path):
        """Dump matched data (from found_scan_lines table in databsse) 
        with a special note to a TSV file.

        :param special_note_string: A string representing the special note to filter matched data. These include: "antcat", "antweb", "inaturalist", "catalogue of fishes"
        :type special_note_string: str
        :param path: The directory path where the TSV file will be saved.
        :type path: str
        """
        if not os.path.exists(path):
            os.makedirs(path)

        db = DoiDatabase(self.config)
        filename = f"{path}/matched_{self.year}_{special_note_string}.tsv"
        fh = open(filename, "w")
        fh.write("doi\tcollection\tjournal_title\ttitle\tpublished_date\tdate_added\tnotes\tdigital_only\n")

        for cur_match in self.get_matches():
            sql = f"select line from found_scan_lines where doi = '{cur_match[0]}'"
            scan_db_results = DBConnection.execute_query(sql)
            found_special_note = False
            for line_array in scan_db_results:
                line = line_array[0]
                if special_note_string in line.lower():
                    found_special_note = True
                    break
            if found_special_note:
                self.write_match(cur_match, fh, db)
                origin_path = cur_match[2]
                self._copy_out_file(origin_path, special_note_string, path)

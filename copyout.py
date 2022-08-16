from db_connection import DBConnection
import os
from shutil import copyfile
from utils_mixin import Utils

from doi_database import DoiDatabase


class CopyOut(Utils):
    def __init__(self, year):
        self.year = year

    def get_matches(self):
        sql = f"""select matches.doi, 
                    matches.collection,
                    dois.full_path,
                    dois.published_date,
                    dois.journal_title, 
                    matches.date_added, 
                    matches.notes, 
                    matches.digital_only 
                    from matches, dois where matches.doi = dois.doi and 
                    matches.ignore = 0 and
                    dois.{self.sql_year_restriction(self.year, self.year)} order by collection,dois.published_date"""
        results = DBConnection.execute_query(sql)
        return results

    def make_target_dir(self, dest_dir, collection):
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
        target_dir = self.make_target_dir(dest_dir, collection)
        target = target_dir + f"/{os.path.basename(origin_path)}"
        if not os.path.exists(target):
            print(f"New paper: {target}")
            copyfile(origin_path, target)

    def copy_out_files(self, dest_dir="./"):
        for cur_match in self.get_matches():
            collection = cur_match[1]
            origin_path = cur_match[2]
            notes = cur_match[6]
            digital_only = bool(cur_match[7])
            if digital_only is True:
                continue
            self._copy_out_file(origin_path, collection, dest_dir)

    def write_match(self, cur_match, filehandle, db):
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
        if not os.path.exists(path):
            os.makedirs(path)
        db = DoiDatabase()
        filename = f"{path}/matched_{self.year}.tsv"
        fh = open(filename, "w")
        fh.write("doi\tcollection\tjournal_title\ttitle\tpublished_date\tdate_added\tnotes\tdigital_only\n")
        for cur_match in self.get_matches():
            self.write_match(cur_match, fh, db)

    def dump_custom(self, special_note_string, path):
        if not os.path.exists(path):
            os.makedirs(path)

        db = DoiDatabase()
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

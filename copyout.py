from db_connection import DBConnection
import os
from shutil import copyfile
from utils_mixin import Utils

from doi_database import DoiDatabase


class CopyOut(Utils):
    def __init__(self, year):
        self.year = year

    def get_matches(self):
        sql = f"""select matches.doi, matches.collection,dois.full_path,dois.published_date,dois.journal_title from matches, dois where matches.doi = dois.doi and 
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

    def _copy_out_file(self,origin_path, collection,dest_dir):
        target_dir = self.make_target_dir(dest_dir, collection)
        target = target_dir + f"/{os.path.basename(origin_path)}"
        if not os.path.exists(target):
            print(f"New paper: {target}")
            copyfile(origin_path, target)

    def copy_out_files(self, dest_dir="./"):
        for cur_match in self.get_matches():
            collection = cur_match[1]
            origin_path = cur_match[2]
            self._copy_out_file(origin_path,collection,dest_dir)


    def write_match(self, cur_match, filehandle, db):
        doi = cur_match[0]
        doi_record = db.get_doi(doi)
        collection = cur_match[1]
        origin_path = cur_match[2]
        published_date = cur_match[3]
        journal_title = cur_match[4]
        title = self.clean_string(doi_record.get_title())
        filehandle.write(f"{doi}\t{collection}\t{journal_title}\t{title}\t{published_date}")
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
        db = DoiDatabase(start_year=self.year,
                         end_year=self.year,
                         setup=False)
        filename = f"{path}/matched_{self.year}.tsv"
        fh = open(filename, "w")
        for cur_match in self.get_matches():
            self.write_match(cur_match, fh, db)

    def dump_antweb(self, path="./"):
        db = DoiDatabase(start_year=self.year,
                         end_year=self.year,
                         setup=False)
        filename = f"{path}/matched_{self.year}_antweb.tsv"
        fh = open(filename, "w")
        for cur_match in self.get_matches():
            sql = f"select line from found_scan_lines where doi = '{cur_match[0]}'"
            scan_db_results = DBConnection.execute_query(sql)
            antweb=False
            for line_array in scan_db_results:
                line = line_array[0]
                if 'antweb' in line.lower():
                    antweb=True
                    break
            if antweb:
                self.write_match(cur_match, fh, db)
                origin_path = cur_match[2]
                self._copy_out_file(origin_path,"antweb",path)


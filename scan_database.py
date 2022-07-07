from db_connection import DBConnection
from scan import Scan
from utils_mixin import Utils
from doi_database import DoiFactory

class ScanDatabase(Utils):

    # "reset" causes a the whole scan database to be rebuilt.
    # required most of the time; it won't pick up new PDFs without it
    # TODO: Command to scan all elements to ensure they have a scan object
    def __init__(self, doi_db, reset_scan_database=False):
        super().__init__()
        if reset_scan_database:
            self._create_scans_database_table(reset_scan_database)
        self.doi_db = doi_db

    def __str__(self):
        if self.cannot_convert is not False:
            return(f"doi: {self.doi} Score: {self.score} title: {self.title}")
        else:
            return(f"doi: {self.doi} Score: CONVERSION FAILURE title: {self.title}")

    def _create_scans_database_table(self,reset_tables=False):
        if reset_tables:
            try:
                sql = "drop table scans"
                DBConnection.execute_query(sql)
            except Exception:
                pass
            try:

                sql = "drop table found_scan_lines"
                DBConnection.execute_query(sql)
            except Exception:
                pass

        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS scans (
                                            doi text primary key not null,
                                            textfile_path text,
                                            score integer,
                                            cannot_convert boolean,
                                            title text NOT NULL
                                        ); """
        DBConnection.execute_query(sql_create_database_table)

        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS found_scan_lines (
                                            doi text,
                                            line text,
                                            score integer
                                        ); """
        DBConnection.execute_query(sql_create_database_table)

    def scan_single_doi(self,doi):
        scan = Scan(doi_string=doi)
        scan.scan(clear_existing_records=True)
        return scan

    def do_scan(self, doi):
        scan = Scan(doi)
        if scan.score is None:
            if scan.broken_converter is not True:
                scan.scan()

    def scan_pdfs(self, start_year, end_year, rescore = False, directory="./"):
        if not rescore:
            sql = f"""SELECT * FROM dois LEFT JOIN scans ON dois.doi = scans.doi WHERE downloaded = 1 and scans.doi IS NULL
            and {self.sql_year_restriction(start_year,end_year)}"""
            dois = DoiFactory(sql).dois
        else:
            dois = self.doi_db.get_dois(start_year=start_year, end_year=end_year,journal_issn=None)
        # multiprocessing verison:
        # import multiprocessing as mp
        # pool = mp.Pool(mp.cpu_count())
        # results = pool.map(self.do_scan,dois)

        # single process version
        for doi_entry in dois:
            self.do_scan(doi_entry)

    def scan_for_collection_ids(self,reset_tables=False):
        if reset_tables:
            sql = "drop table matched_collection_ids"
            DBConnection.execute_query(sql)

        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS matched_collection_ids (
                                            doi text,
                                            identifier text
                                        ); """
        DBConnection.execute_query(sql_create_database_table)
        select_dois = f"""select doi from matches where ignore = 0"""
        matched_dois = DBConnection.execute_query(select_dois)
        for doi in matched_dois:
            doi=doi[0]
            scan = Scan(doi_string=doi)
            results = scan.scan_collection_ids()
            if results:
                # print(f"Title: {scan.title}")
                for result in results:
                    sql_insert = f"""insert into matched_collection_ids (doi, identifier) VALUES (?,?)"""
                    result = result.strip()
                    if result.startswith("("):
                        result = result[1:]
                    args = [doi,
                            result]
                    DBConnection.execute_query(sql_insert, args)
                    # if '-' in result:
                    #     print(f"doi: {doi} title: {scan.title}")
                    #     print(f" Got bad: {result}")

    def __str__(self):
        good_scan = 0
        bad_scan = 0
        for cur_scan in self.scans.values():
            if cur_scan.found_count > 0:
                good_scan += 1
            else:
                bad_scan += 1

        retval = f"Total scanned: {good_scan + bad_scan}\n"
        retval += f" Good: {good_scan}\n"
        retval += f" Bad: {bad_scan}"
        return retval

    def year_breakdown(self):
        year_hist = {}

        for cur_scan in self.scans.values():
            if cur_scan.found_count > 4:
                date = cur_scan.doi_object.get_date()
                if date.year not in year_hist:
                    year_hist[date.year] = 1
                else:
                    year_hist[date.year] += 1

        for year, counts in year_hist.items():
            print(f"{year}: {counts}")

    def top_papers_by_score(self, year):
        top_papers = []

        for cur_scan in self.scans.values():
            date = cur_scan.doi_object.get_date()
            if date.year != year:
                continue

            if cur_scan.score > 0:
                top_papers.append(cur_scan)

        top_papers = sorted(top_papers)

        for sort in top_papers:
            print(f"{sort}")

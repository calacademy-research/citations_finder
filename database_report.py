from doi_entry import DoiFactory
from db_connection import DBConnection


class DatabaseReport:
    categories = ['downloaded', 'missing', 'total']

    def __init__(self, start_year=None, end_year=None, journal=None):
        self.good_download_count = 0
        self.start_year = start_year
        self.end_year = end_year
        self.dois = None
        self._load_dois(journal=journal)

    def _sql_date_suffix(self, and_var=True):
        retval = ""
        if self.start_year is not None and self.end_year is not None:
            if and_var:
                retval += " and"
            else:
                retval += " where"

            retval += f""" published_date BETWEEN 
               '{self.start_year}-01-01' AND '{self.end_year}-12-31'"""
        return retval

    def _sql_journal_suffix(self, journal, and_var=True):
        retval = ""
        if journal is not None:
            if and_var:
                retval += " and"
            else:
                retval += " where"

            retval += f""" journal_title='{journal}'"""
        return retval

    def _load_dois(self, journal=None):
        select_dois = f"""select * from dois"""
        select_dois += self._sql_date_suffix(False)
        if journal is not None:
            select_dois += f' and journal_title="{journal}"'

        doif = DoiFactory(select_dois)
        self.dois = doif.dois

    def _get_journals(self):
        sql = f"""select distinct journal_title from dois"""
        sql += self._sql_date_suffix(False)

        return DBConnection.execute_query(sql)

    def _get_downloaded(self, journal=None):
        sql = f"""select count(*) from dois where downloaded=TRUE"""
        sql += self._sql_date_suffix()
        sql += self._sql_journal_suffix(journal)

        return DBConnection.execute_query(sql)[0][0]

    # def _get_pending_downloads(self, journal=None):
    #     sql = f"""select count(*) from dois where downloaded=FALSE and long_retry=0 and not_found_count=0"""
    #     sql += self._sql_date_suffix()
    #     sql += self._sql_journal_suffix(journal)

    # return DBConnection.execute_query(sql)[0][0]

    def _get_not_downloaded(self, journal=None):
        sql = f"""select count(*) from dois where downloaded=FALSE"""
        sql += self._sql_date_suffix()
        sql += self._sql_journal_suffix(journal)

        return DBConnection.execute_query(sql)[0][0]

    # def _get_unresolved_downloads(self, journal=None):
    #     sql = f"""select count(*) from dois where downloaded=FALSE and not_found_count=0 and long_retry > 0"""
    #     sql += self._sql_date_suffix()
    #     sql += self._sql_journal_suffix(journal)
    #     return DBConnection.execute_query(sql)[0][0]

    def report(self, journal=None, issn=None, summary=True):

        str = ""
        if summary:
            str += f"Total DOI entries: {len(self.dois)}"
            if self.start_year is not None:
                str += f" years: {self.start_year} -> {self.end_year}\n"
            else:
                str += "\n"

            str += f"Successful downloads: {self._get_downloaded()}\n"
            str += f"Not downloaded: {self._get_not_downloaded()}\n"
        if journal is None:
            journals = self._get_journals()
        else:
            journals = [[journal]]
        journal_stats = {}
        for journal in journals:
            journal = journal[0]
            dict = {'journal': journal}
            for category in DatabaseReport.categories:
                dict[category] = 0
            journal_stats[journal] = dict

        for doi in self.dois:
            journal = doi.journal_title
            stats = journal_stats[journal]

            if not self.start_year <= doi.date.year <= self.end_year:
                continue
            stats['total'] += 1
            if doi.downloaded:
                stats['downloaded'] += 1
            # if not doi.downloaded and doi.long_retry == 0 and doi.not_found_count == 0:
            #     stats['pending'] += 1
            if not doi.downloaded > 0:
                stats['missing'] += 1
            #     downloaded=FALSE and not_found_count=0 and long_retry > 0
            # if not doi.downloaded and doi.long_retry > 0 and doi.not_found_count == 0:
            #     stats['unresolved'] += 1
        from tabulate import tabulate
        table = []

        for journal, stats in journal_stats.items():
            row = []
            for statname, stat in stats.items():
                row.append(stat)
            if stats['downloaded'] > 0:
                percent = stats['downloaded'] / stats['total'] * 100
                # row.append(f"{percent:.0f}%")
                row.append(percent)
            else:
                row.append(0)
            table.append(row)
        sorted_table = sorted(table, key=lambda x: x[4])
        for i, row in enumerate(sorted_table):
            percent_string = f"{row[4]:.0f}%"
            sorted_table[i][4] = percent_string

        str += tabulate(sorted_table, headers=['Journal'] + DatabaseReport.categories + ['%'])

        return str

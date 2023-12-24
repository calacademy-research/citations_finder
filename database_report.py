from doi_entry import DoiFactory
from db_connection import DBConnection
from tabulate import tabulate


class DatabaseReport:
    categories = ['downloaded', 'missing', 'total']

    def __init__(self, doi_database, start_year=None, end_year=None, issn=None):
        self.doi_database = doi_database
        self.good_download_count = 0
        self.start_year = start_year
        self.end_year = end_year
        self.dois = None
        self._load_dois(issn=issn)


    def _sql_date_suffix(self, and_var=True):
        """ Constructs a SQL suffix for filtering records based on start and end years.
        
        :param and_var: Specifies whether to use "AND" or "WHERE" in the SQL query. Defaults to True.
        :type and_var: bool, optional
        :return: The constructed SQL suffix.
        :rtype: str
        """        
        retval = ""
        if self.start_year is not None and self.end_year is not None:
            if and_var:
                retval += " and"
            else:
                retval += " where"

            retval += f""" published_date BETWEEN 
               '{self.start_year}-01-01' AND '{self.end_year}-12-31'"""
        return retval

    def _sql_journal_suffix(self, issn, and_var=True):
        retval = ""
        if issn is not None:
            if and_var:
                retval += " and"
            else:
                retval += " where"

            retval += f""" issn='{issn}'"""
        return retval

    def _load_dois(self, issn=None):
        """ Load DOIs from a database, and potentially filter
        by a specific journal title if desired

        :param journal: The journal title to filter the DOIs by, defaults to None
        :type journal: str, optional
        """        
        select_dois = f"""select * from dois"""
        select_dois += self._sql_date_suffix(False)
        if issn is not None:
            select_dois += f' and issn="{issn}"'

        doif = DoiFactory(select_dois)
        self.dois = doif.dois

    def _get_journals(self):
        """Get a list of distinct journal titles from the database.

        :return: A list of unique journal titles present in the database.
        :rtype: List[str]
        """        
        sql = f"""select distinct issn from dois"""
        sql += self._sql_date_suffix(False)

        return DBConnection.execute_query(sql)

    def _get_journal_title(self,issn):
        sql = f"""select name from journals where issn ='{issn}'"""

        value = DBConnection.execute_query(sql)
        return value

    def _get_downloaded(self, issn=None):
        """Get the count of downloaded DOI entries.

        :param journal: The specific journal name for which to get the count, defaults to None.
        :type journal: str, optional
        :return: The count of downloaded DOI entries for the given journal or the entire database.
        :rtype: int
        """        
        sql = f"""select count(*) from dois where downloaded=TRUE"""
        sql += self._sql_date_suffix()
        sql += self._sql_journal_suffix(issn)

        return DBConnection.execute_query(sql)[0][0]

    # def _get_pending_downloads(self, journal=None):
    #     sql = f"""select count(*) from dois where downloaded=FALSE and long_retry=0 and not_found_count=0"""
    #     sql += self._sql_date_suffix()
    #     sql += self._sql_journal_suffix(journal)

    # return DBConnection.execute_query(sql)[0][0]

    def _get_not_downloaded(self, issn=None):
        """Get the count of NOT downloaded DOI entries.

        :param journal: The specific journal name for which to get the count, defaults to None.
        :type journal: str, optional
        :return: The count of NOT downloaded DOI entries for the given journal or the entire database.
        :rtype: int
        """        
        sql = f"""select count(*) from dois where downloaded=FALSE"""
        sql += self._sql_date_suffix()
        sql += self._sql_journal_suffix(issn)

        return DBConnection.execute_query(sql)[0][0]

    # def _get_unresolved_downloads(self, journal=None):
    #     sql = f"""select count(*) from dois where downloaded=FALSE and not_found_count=0 and long_retry > 0"""
    #     sql += self._sql_date_suffix()
    #     sql += self._sql_journal_suffix(journal)
    #     return DBConnection.execute_query(sql)[0][0]

    # we use not available because it's possible
    # that the open_url is null (not available) but we haven't
    # queried it yet, so not_available would also be null
    def _get_unpaywall_has_open_link(self, issn=None):
        sql = f"""select count(*)
        from unpaywall_downloader,
             dois
          where unpaywall_downloader.doi = dois.doi
          and (unpaywall_downloader.not_available = False or unpaywall_downloader.open_url is not null)
          """

        sql += self._sql_date_suffix()
        sql += self._sql_journal_suffix(issn)
        sql = sql.replace("'s", "''s")  # hack. this should be by issn

        return int(DBConnection.execute_query(sql)[0][0])

    def _get_unpaywall_has_err_code(self, issn=None):
        sql = f"""select count(*) from dois,unpaywall_downloader where dois.doi = unpaywall_downloader.doi 
                    and downloaded=FALSE and unpaywall_downloader.error_code """

        sql += self._sql_date_suffix()
        sql += self._sql_journal_suffix(issn)
        sql = sql.replace("'s", "''s")
        return int(DBConnection.execute_query(sql)[0][0])

    def _get_unpaywall_failed_download(self, issn=None):
        sql = f"""select count(*) from dois,unpaywall_downloader where dois.doi = unpaywall_downloader.doi 
                    and downloaded=FALSE and unpaywall_downloader.most_recent_attempt is not NULL """

        sql += self._sql_date_suffix()
        sql += self._sql_journal_suffix(issn)
        sql = sql.replace("'s", "''s")
        return int(DBConnection.execute_query(sql)[0][0])

    def report(self, issn=None, summary=True):
        """Generate a report on the database statistics. Note this takes a while
        to run

        :param journal: The specific journal name for which to generate the report, defaults to None.
        :type journal: str, optional
        :param issn: The ISSN (International Standard Serial Number) of the journal, defaults to None.
        :type issn: str, optional
        :param summary: If True, include a summary of general statistics; if False, exclude the summary, defaults to True.
        :type summary: bool, optional
        :return: A formatted string containing the report with statistics.
        :rtype: str
        """        
        str = ""
        if summary:
            str += f"Total DOI entries: {len(self.dois)}"
            if self.start_year is not None:
                str += f" years: {self.start_year} -> {self.end_year}\n"
            else:
                str += "\n"

            str += f"Successful downloads: {self._get_downloaded()}\n"
            str += f"Not downloaded: {self._get_not_downloaded()}\n"
        if issn is None:
            issns = self._get_journals()
        else:
            issns = [[issn]]
        journal_stats = {}
        for cur_issn in issns:
            issn = cur_issn[0]
            dict = {'journal': issn}
            for category in DatabaseReport.categories:
                dict[category] = 0
            journal_stats[issn] = dict

        for doi in self.dois:
            issn = doi.issn
            try:
                stats = journal_stats[issn]

                if not self.start_year <= doi.date.year <= self.end_year:
                    continue
                stats['total'] += 1
                if doi.downloaded:
                    stats['downloaded'] += 1
                else:
                    stats['missing'] += 1
            except KeyError as e:
                # usually a doi with a missing journal
                pass
        table = []

        for issn, stats in journal_stats.items():
            row = []
            row.append(self._get_journal_title(issn))
            open_link_num = self._get_unpaywall_has_open_link(issn)

            # Downloaded, missing, total
            for statname, stat in stats.items():
                row.append(stat)
            if stats['total'] > 0:
                percent = open_link_num / stats['total'] * 100
            else:
                percent = 0
            # %open
            row.append(f"{percent:.0f}%")
            # %got (downloaded)
            if stats['downloaded'] > 0:
                percent = stats['downloaded'] / stats['total'] * 100
                # row.append(f"{percent:.0f}%")
                row.append(percent)
            else:
                row.append(0)
            # raw number with open links (UP link)
            row.append(open_link_num)
            # Number of not downloaded with error codes
            row.append(self._get_unpaywall_has_err_code(issn))
            row.append(self._get_unpaywall_failed_download(issn))

            table.append(row)
        sorted_table = sorted(table, key=lambda x: x[5])
        for i, row in enumerate(sorted_table):
            try:
                percent_string = f"{row[6]:.0f}%"
            except Exception as e:
                pass
            sorted_table[i][6] = percent_string

        str += tabulate(sorted_table,
                        headers=['Journal'] +
                                ['ISSN']+
                                DatabaseReport.categories +
                                ['%open'] +
                                ["%got"] +
                                ["UP link"] +
                                ["UP err"] +
                        ["Failed"])
        return str

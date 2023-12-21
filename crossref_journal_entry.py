from db_connection import DBConnection
import json


class CrossrefJournalEntry():
    def __init__(self, json_details):
        self.details = json_details
        self.doi = json_details['DOI']
        self.title = json_details['title'][0]
        if not self._check_exists():
            self._insert_database()

    def _insert_database(self):
        json_string = json.dumps(self.details)
        clean_details = json_string.replace('\'', '\\')
        sql_insert = f"""INSERT INTO crossref_journal_data (doi,
                                            title,
                                            details)
                               VALUES (%s,%s,%s)
                               """

        args = [self.doi,
                self.title,
                clean_details]
        DBConnection.execute_query(sql_insert, args)

    def _check_exists(self):
        query = f"select doi from crossref_journal_data where doi=\"{self.doi}\""
        results = DBConnection.execute_query(query)
        if len(results) >= 1:
            return True
        return False

    @staticmethod
    def create_tables():
        """    Creates database tables if they do not already exist.

        This function creates three tables:
        1. 'issns' table with columns 'issn' (primary key) and 'type'.
        2. 'journals' table with columns 'issn' (primary key), 'name', 'type', 'start_year', and 'end_year'.
        3. 'crossref_journal_data' table with columns 'doi' (primary key), 'title', and 'details'.

        The tables are created only if they don't already exist.

        """        
        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS issns (
                                            issn varchar(100) primary key NOT NULL,
                                            type varchar(50)
                                        ); """
        DBConnection.execute_query(sql_create_database_table)

        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS journals (
                                            issn varchar(100) primary key NOT NULL,
                                            name varchar(1024),
                                            type varchar(50)
                                        ); """
        DBConnection.execute_query(sql_create_database_table)
        sql_create_database_table = """create table if not exists crossref_journal_data
                                    (
                                        doi     varchar(255) not null
                                            primary key,
                                        title   varchar(1024) not null,
                                        details mediumtext
                                    );"""
        DBConnection.execute_query(sql_create_database_table)

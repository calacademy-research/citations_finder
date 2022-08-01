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
                               VALUES (?,?,?)
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
        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS issns (
                                            issn text primary key NOT NULL,
                                            type text
                                        ); """
        DBConnection.execute_query(sql_create_database_table)

        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS journals (
                                            issn text primary key NOT NULL,
                                            name text,
                                            type text,
                                            start_year INT,
                                            end_year INT
                                        ); """
        DBConnection.execute_query(sql_create_database_table)
        sql_create_database_table = """create table if not exists crossref_journal_data
                                    (
                                        doi     text not null
                                            primary key,
                                        title   text not null,
                                        details text
                                    );"""
        DBConnection.execute_query(sql_create_database_table)

import sqlite3
import logging

class DBConnector(object):

    def __init__(self):
        self.dbconn = None

    def create_connection(self):
        return sqlite3.connect('doi_database.db', timeout=30.0)

    # For explicitly opening database connection
    def __enter__(self):
        self.dbconn = self.create_connection()
        return self.dbconn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dbconn.close()


class DBConnection(object):
    connection = None

    @classmethod
    def get_connection(cls, new=False):
        """Creates return new Singleton database connection"""
        if new or not cls.connection:
            cls.connection = DBConnector().create_connection()
        return cls.connection

    @classmethod
    def execute_query(cls, query, args=None):
        connection = cls.get_connection()
        try:
            cursor = connection.cursor()
        except Exception as e:
            logging.error(f"Connection error; recreating connection.")
            connection = cls.get_connection(new=True)  # Create new connection
            cursor = connection.cursor()
        try:
            if args is None:
                cursor.execute(query)
            else:
                cursor.execute(query, args)
            connection.commit()
        except Exception as e:
            logging.critical(f"Bad SQL: {e}:\n{query}")
            raise e
        result = cursor.fetchall()
        cursor.close()
        return result

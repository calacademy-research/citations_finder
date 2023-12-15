import logging
import mysql.connector
import yaml


class DBConnector(object):

    def __init__(self):
        self.dbconn = None
        self.db_config = self.read_db_config()

    def read_db_config(self):
        with open('./vm/vm_passwords.yml', 'r') as file:
            config = yaml.safe_load(file)
        return config

    # def create_connection(self):
    #     return sqlite3.connect('doi_database.db', timeout=30.0)

    def create_connection(self):
        return mysql.connector.connect(
            host=self.db_config['database_url'],
            user=self.db_config['database_user'],  # Replace with your username
            password=self.db_config['database_password'],

            database=self.db_config['database_name'],  # Replace with your database name
            port=self.db_config['database_port']
        )


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
        """ Execute a SQL query on the database connection.

        This code attempts to create a cursor object for the database connection.
        If an error occurs, such as a connection timeout, the code logs an error
        message and creates a new connection before creating the cursor object again.
        Then code executes the SQL query using the cursor object.
        If the args parameter is not None, it substitutes the parameter values into
        the query using placeholder variables. If an error occurs during the
        query execution, such as a syntax error in the SQL, the code logs a critical
        error message and raises the error.


        :param query: The query to be executed
        :type query: str
        :param args: Optional arguments to be substituted in the query, defaults to None
        :type args: list or None, optional
        :raises e: Raises an exception if there is an error executing the query
        :return: The result of the query execution
        :rtype: Any
        """
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
            if query.strip().upper().startswith("SELECT"):
                result = cursor.fetchall()
                return result  # Return results for SELECT queries
            else:
                connection.commit()  # Commit for INSERT, UPDATE, DELETE
        except Exception as e:
            logging.critical(f"Bad SQL: {e}:\n{query}")
            raise e
        result = cursor.fetchall()
        cursor.close()
        return result


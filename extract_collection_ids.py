from db_connection import DBConnection

class ExtractCollectionIds():
    def __init__(self):
        pass

    def scan(self,doi_string):
        select_dois = f"""select * from matches where doi = '{doi_string}'"""
        matched_dois = DBConnection.execute_query(select_dois)

        regex = '(([ \(\[])+|^)(?i)cas[: ]+[ ]*[0-9\-]+'

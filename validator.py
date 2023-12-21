from db_connection import DBConnection
from utils_mixin import Utils
import subprocess
import os
import re
from colorama import Fore, Back, Style
from ete3 import NCBITaxa
from scan import Scan
from datetime import datetime
import logging

ncbi = NCBITaxa()


# ncbi.update_taxonomy_database()


# f"{Fore.MAGENTA + self.chromosome.id + Fore.WHITE}:" \
class Match(Utils):
    def __init__(self, doi, score, title, full_path, published_date, notes=None, digital_only=None, collection=None):
        self.doi = doi
        self.score = score
        self.title = title
        self.published_date = published_date
        self.full_path = full_path
        self.notes = notes
        self.digital_only = digital_only
        self.collection = collection

    def generate_notes(self):
        """Generate and replace notes based on specified flagged terms in the scanned text.

        This method generates notes for a scanned document based on specific flagged terms that are found
        in the scanned text lines. It searches for predefined flagged terms such as 'inaturalist', 'antweb',
        'antcat', and 'catalog of fishes' within the scanned text lines associated with the DOI.

        The method retrieves lines and scores from the 'found_scan_lines' table in the database that match the
        given DOI. For each line, it checks whether any of the flagged terms are present. If a flagged term is
        found in a line, the corresponding flag is recorded in the 'matches' dictionary.

        After processing all the lines, the method constructs a list of matched flag notes from the 'matches' dictionary.
        These matched flag notes are then joined together using commas to create the final 'notes' string.

        Finally, the method uses the 'replace_note' method to replace the existing notes associated with the DOI
        with the newly generated notes.

        :return: None
        """        

        flag_notes = ['inaturalist', 'antweb', 'antcat', 'catalog of fishes']
        sql = f"select line,score from found_scan_lines where doi = '{self.doi}'"
        lines = DBConnection.execute_query(sql)
        matches = {}
        for line in lines:
            matched_line = line[0]
            for flag_note in flag_notes:
                if flag_note in matched_line:
                    matches[flag_note] = True
        match_list = []
        for flag_note in matches.keys():
            match_list.append(flag_note)
        notes = ",".join(match_list)
        self.replace_note(notes)

    def replace_note(self, notes):
        self.notes = notes

    def print(self):
        print("--------------")
        print(f"Score: {self.score} title: {self.title}")
        print(f"doi: {self.doi} date:{self.published_date} path: {self.full_path}")
        if self.notes is not None and len(self.notes) > 0:
            print(f"Notes: {self.notes}")
        if self.digital_only is not None and len(self.digital_only) > 0:
            print(f"digital_only: {self.digital_only}")

    def print_matched_lines(self):
        """Print scanned lines with highlighted matched strings and their associated scores.

        This method retrieves the scanned lines along with their scores and matched strings from the
        'found_scan_lines' table in the database for a specific DOI. It then iterates through each line
        and processes the matched string and score to display the line with highlighted matched strings
        in different colors based on the score.

        The color of the highlighted matched string depends on the score value:
        - If the score is less than 0, the matched string is highlighted in magenta.
        - If the score is between 0 and 200, the matched string remains the default color.
        - If the score is greater than 200, the matched string is highlighted in yellow.
        - If the score is greater than 300, the matched string is highlighted in red.

        If a matched string is present in the line, the method replaces the matched string in the line with
        the highlighted version using the appropriate color. If the matched string is `None`, the method
        does not perform any replacement.

        Note: This method is useful for visually inspecting and highlighting matched strings in the scanned text.

        :return: None
        """        
        sql = f"select line,score,matched_string from found_scan_lines where doi = '{self.doi}'"
        lines = DBConnection.execute_query(sql)
        for line in lines:
            matched_line = line[0]
            color = Fore.BLUE
            score = line[1]
            matched = line[2]
            if score < 0:
                color = Fore.MAGENTA
            if score > 200:
                color = Fore.YELLOW
            if score > 300:
                color = Fore.RED

            # we have a case where "matched" is none
            if matched is not None:
                try:
                    matched_line = matched_line.replace(matched, f'{color}{matched}{Fore.RESET}')
                except Exception as e:
                    print(f"Error case - debug me! Missing payload matched, root case this. {e}")
            else: # what do we want to do if matched string is not None?
                pass
            # logging.debug(f"    {regex_tuple[0]}\t{matched_line}")

            # matched_line = matched_line.replace('california',f'{Fore.MAGENTA}california{Fore.RESET}')
            # matched_line = matched_line.replace('cas',f'{Fore.RED}cas{Fore.RESET}')

            logging.info(f"{score}: {matched_line}")

    def open(self):
        """Open the associated PDF file using the default system PDF viewer.
        """        
        command = "/usr/bin/open"
        pwd = os.getcwd()
        pdf_file = f"{pwd}/{self.full_path}"
        subprocess.call([command, pdf_file])

    # Ignore is for papers that aren't correct matches
    def update(self, ignore, collection=None,digital_only=None):
        """Updates match records for the DOI entry in the database. It replaces existing records
        with new data and attributes.

        :param ignore: Indicates whether the DOI entry should be ignored, typically a boolean value.
        :type ignore: bool
        :param collection: The collection associated with the DOI entry, defaults to None.
        :type collection: str, optional
        :param digital_only: Indicates whether the DOI entry is digital-only, defaults to None.
        :type digital_only: bool, optional
        :return: None
        """        
        #  for updating match records
        # sql = f"""delete from matches where doi='{self.doi}'"""
        # DBConnection.execute_query(sql)
        if digital_only is not None:
            self.digital_only = digital_only
        sql = f""" replace into matches (doi,collection,ignore,date_added,notes,digital_only) values (%s,%s,%s,%s,%s,%s)"""
        args = [self.doi, collection, ignore, datetime.now(), self.notes, self.digital_only]
        DBConnection.execute_query(sql, args)


class Validator(Utils):
    def __init__(self, reset_matches_database=False):
        self.matches = []

        self.create_tables(reset_matches_database=reset_matches_database)

    def get_matched_paper_dois(self):
        sql = f"""select doi from matches where ignore=FALSE"""
        results = DBConnection.execute_query(sql)
        return [x[0] for x in results]

    @classmethod
    def create_tables(self, reset_matches_database=False):
        """Creates a database table named "matches" if it 
        doesn't already exist. It also includes an optional parameter 
        reset_matches_database to determine whether the existing 
        "matches" table should be dropped before creating a new one.

        :param reset_matches_database: Determines whether the existing "matches" table should be dropped before creating a new one, defaults to False
        :type reset_matches_database: bool, optional

        """        
        if reset_matches_database:
            sql = "drop table matches"
            DBConnection.execute_query(sql)
        sql_create_database_table = """ create table if not exists matches
                                        (
                                            doi          varchar(255)       not null
                                                primary key,
                                            collection   varchar(1024)       null,
                                            `ignore`     tinyint(1) null,
                                            date_added   date       null,
                                            notes        varchar(8192)       null,
                                            digital_only tinyint(1) null
                                        ); """


        DBConnection.execute_query(sql_create_database_table)

    def copy_matches(self, target_dir):
        sql = """select dois.doi, dois.full_path, dois.published_date from dois,matches,scans
                                    where
                                    matches.doi = dois.doi and matches.ignore=FALSE"""
        results = DBConnection.execute_query(sql)
        for result in results:
            doi = result[0]
            full_path = result[1]
            f"cp full_path {target_dir}"
            command = "/bin/cp"
            subprocess.call([command, full_path, target_dir])

    def audit(self, start_year, end_year):
        """Run a query that combines tables 'scans' and 'dois', 
        based on the 'doi' column. Then filter results based on 
        start_year and end_year, score not null and >0, 
        and  doi not null. The resulting merged table is called 
        'candidates'. Subsequently, rename the columns, 
        create  new object 'Match' using these columns
        and append to 'matches' list. Lastly, invoke 'generate_notes' 
        method on 'matches' list, and self.prompt 
        method of the current object, passing the current 'match' object as an argument

        :param start_year: interactive validate step start year
        :type start_year: int
        :param end_year: interactive validate step end year
        :type end_year: int
        """        

        sql = f"""select dois.doi, dois.full_path, dois.published_date, scans.title, scans.score from scans,dois
                                    left join matches m on dois.doi = m.doi
                                    where
                                    scans.doi = dois.doi and
                                    dois.{self.sql_year_restriction(start_year, end_year)} and
                                    scans.score is not null and
                                    m.doi is NULL and
                                    score > 0
                                    order by score desc """
        
        candidates = DBConnection.execute_query(sql)
        for candidate in candidates:
            doi = candidate[0]
            full_path = candidate[1]
            published_date = candidate[2]
            title = candidate[3]
            score = candidate[4]
            self.matches.append(Match(doi, score, title, full_path, published_date))

        for match in self.matches:
            match.generate_notes()
            self.prompt(match)

    def audit_digital_only(self, start_year, end_year):
        sql = f"""select dois.doi, matches.collection, dois.full_path, dois.published_date, scans.title, scans.score, matches.notes
                    from scans,
                         dois,
                         matches
                             left join matches m on dois.doi = m.doi
                    where matches.doi = scans.doi
                      and scans.doi = dois.doi
                      and matches.digital_only is NULL
                      and dois.{self.sql_year_restriction(start_year, end_year)} 
                      and scans.score is not null
                      and length(matches.notes) > 0
                      and score > 0
                    order by score desc
        """

        candidates = DBConnection.execute_query(sql)
        for candidate in candidates:
            doi = candidate[0]
            collection = candidate[1]
            full_path = candidate[2]
            published_date = candidate[3]
            title = candidate[4]
            score = candidate[5]
            notes = candidate[6]
            self.matches.append(Match(doi, score, title, full_path, published_date, notes=notes, collection=collection))

        for match in self.matches:
            self.prompt_digital(match)

    def get_lineage(self, word, verbose=False):
        """Retrieves the taxonomic lineage of a given word (typically a taxonomic name) using the NCBI Taxonomy
        database. It uses the `get_name_translator` and `get_lineage` functions from the `ncbi` module to fetch the
        taxonomic lineage information.

        :param word: The word for which the taxonomic lineage needs to be retrieved.
        :type word: str
        :param verbose: If True, display additional verbose information, defaults to False.
        :type verbose: bool, optional
        :return: A list of taxonomic names representing the lineage of the given word.
        :rtype: list[str]
        """        
        name2taxid = ncbi.get_name_translator([word])
        if len(name2taxid) == 0:
            return None
        if verbose:
            logging.info(f"Word: {word}")
        assert len(name2taxid) == 1
        name = list(name2taxid.keys())[0]
        taxid = name2taxid[name][0]
        # logging.debug(f"   taxid: {taxid}")
        lineage = ncbi.get_lineage(taxid)
        names_dict = ncbi.get_taxid_translator(lineage)
        lineage_names = [names_dict[taxid] for taxid in lineage]

        names = [item.lower() for item in lineage_names]
        return names

    def categorize_lineage(self, lineages, verbose=False):
        """Categorizes a given set of lineages into predefined departments.

        :param lineages: A list of lineages to categorize.
        :type lineages: list[str]
        :param verbose: If True, display verbose matching information, defaults to False.
        :type verbose: bool, optional
        :return: The categorized department name, or None if no match is found.
        :rtype: str or None
        """        
        # lanka matching to ento, incorrect
        # Matching insecta to entomology via lineage: ['root', 'cellular organisms', 'eukaryota', 'opisthokonta', 'metazoa', 'eumetazoa', 'bilateria', 'protostomia', 'ecdysozoa', 'panarthropoda', 'arthropoda', 'mandibulata', 'pancrustacea', 'hexapoda', 'insecta', 'dicondylia', 'pterygota', 'neoptera', 'endopterygota', 'coleoptera', 'polyphaga', 'cucujiformia', 'chrysomeloidea', 'chrysomelidae', 'galerucinae', 'alticini', 'lanka']
        # It's in entomology
        #   Lineage:['root', 'cellular organisms', 'eukaryota', 'opisthokonta', 'metazoa', 'eumetazoa', 'bilateria', 'protostomia', 'ecdysozoa', 'panarthropoda', 'arthropoda', 'mandibulata', 'pancrustacea', 'hexapoda', 'insecta', 'dicondylia', 'pterygota', 'neoptera', 'endopterygota', 'coleoptera', 'polyphaga', 'cucujiformia', 'chrysomeloidea', 'chrysomelidae', 'galerucinae', 'alticini', 'lanka']
        #
        #
        # Word: carybdea
        # Word: cnidaria
        # Word: cubozoa
        # Word: carybdeidae
        # Word: carybdea
        #   Lineage:['root', 'cellular organisms', 'eukaryota', 'opisthokonta', 'metazoa', 'eumetazoa', 'cnidaria', 'cubozoa', 'carybdeida', 'carybdeidae', 'carybdea']
        #   Lineage:['root', 'cellular organisms', 'eukaryota', 'opisthokonta', 'metazoa', 'eumetazoa', 'cnidaria']
        #   Lineage:['root', 'cellular organisms', 'eukaryota', 'opisthokonta', 'metazoa', 'eumetazoa', 'cnidaria', 'cubozoa']
        #   Lineage:['root', 'cellular organisms', 'eukaryota', 'opisthokonta', 'metazoa', 'eumetazoa', 'cnidaria', 'cubozoa', 'carybdeida', 'carybdeidae']
        #   Lineage:['root', 'cellular organisms', 'eukaryota', 'opisthokonta', 'metazoa', 'eumetazoa', 'cnidaria', 'cubozoa', 'carybdeida', 'carybdeidae', 'carybdea']
        # --------------
        ento_names = ["araneae", "arachnida", "hymenoptera", "insecta", "scolopendridae", "myriapoda"]
        izg_names = ['porifera', 'echinodermata', 'spiralia', 'crustacea']
        om_names = ["aves", "mammalia"]
        i_names = ["actinopterygii", "chondrichthyes", "actinopterygii"]
        herp_names = ["lepidosauria", "amphibia", "toxicofera", "squamata"]
        botany_names = ["plantae", "streptophyta"]
        skip_names = ["California", "data", "areas", "sea", "virginia", "argentina", "arizona", "andes"]
        all_names = {'entomology': ento_names,
                     'izg': izg_names,
                     'o&m': om_names,
                     "ichthyology": i_names,
                     "herpetology": herp_names,
                     "botany": botany_names};
        retval = None

        for department, name_array in all_names.items():
            for name in name_array:
                for lineage in lineages:
                    skip = False
                    for skip_name in skip_names:
                        if skip_name in lineage:
                            skip = True
                    if skip is False and name in lineage:
                        if retval is not None:
                            if department != retval:
                                logging.info(f"Conflict between {retval} and {department}, returning none")
                                return None
                        if verbose:
                            logging.info(f"Matching {name} to {department} via lineage: {lineage}")
                        retval = department

        return retval

    def analyze_title(self, title, verbose=False):
        """Analyzes a title to determine the relevant department based on taxonomy keywords.

        :param title: The title to analyze.
        :type title: str
        :param verbose: If True, display verbose information during analysis, defaults to False.
        :type verbose: bool, optional
        """        
        # Valid taxa: Curcuma
        # ['root', 'cellular organisms', 'Eukaryota', 'Viridiplantae', 'Streptophyta', 'Streptophytina', 'Embryophyta', 'Tracheophyta', 'Euphyllophyta', 'Spermatophyta', 'Magnoliopsida', 'Mesangiospermae', 'Liliopsida', 'Petrosaviidae', 'commelinids', 'Zingiberales', 'Zingiberaceae', 'Curcuma']

        title = self.clean_string(title)
        found_lineages = []
        for word in title.split():
            word = word.lower()
            lineage = self.get_lineage(word, verbose)
            if lineage is not None:
                found_lineages.append(lineage)
        department = self.categorize_lineage(found_lineages, verbose)

        if department is not None:
            logging.info(f"It's in {Fore.GREEN}{department}{Fore.RESET}")
        if verbose:
            for lineage in found_lineages:
                logging.info(f"  Lineage:{lineage}")

    def prompt(self, match):
        """Prompt the user for actions related to a given match.

        :param match: The match to prompt for.
        :type match: Match
        """        
        exit = False
        while not exit:
            match.print()
            title = match.title
            self.analyze_title(title)
            option = input("Keep(K) print lines(L) Discard(D) open(O) skip(s) Verbose(V)")
            option = option.lower()
            if option == "o":
                match.open()
            elif option == "k":
                self.prompt_add_type(match)
                exit = True
            elif option == "s":
                exit = True
            elif option == "v":
                self.analyze_title(title, verbose=True)
            elif option == "d":
                match.update(ignore=True, collection="None")
                exit = True
            elif option == "l":
                match.print_matched_lines()

    def prompt_digital(self, match):
        exit = False
        while not exit:
            digital_only = None
            match.print()
            title = match.title
            self.analyze_title(title)
            option = input("digital only? y/n/(o)pen,(l)ines,(s)kip")
            option = option.lower()
            if option == "o":
                match.open()

            elif option == "y":
                digital_only = True
                exit = True
            elif option == "s":
                exit = True
            elif option == "n":
                digital_only = False
                exit = True
            elif option == "d":
                match.update(ignore=True, collection="None")
                exit = True
            elif option == "l":
                match.print_matched_lines()
        match.update(False, collection=match.collection,digital_only=digital_only)

    def prompt_add_type(self, match):
        """Prompt the user to add a collection type to the given match.

        :param match: The match to add a collection type to.
        :type match: Match
        """        
        collection_type = None
        while collection_type is None:
            option = input(
                "Herpetology(H) Ichthyology(I) O&M(M) IZ&G(Z) Anthropology(A) Entomology(E) Botany(B) Other(O) Library(l)")
            option = option.lower()
            if option == "h":
                collection_type = "herpetology"
            elif option == "i":
                collection_type = "ichthyology"
            elif option == "m":
                collection_type = "o&m"
            elif option == "z":
                collection_type = "iz&g"
            elif option == "a":
                collection_type = "anthropology"
            elif option == "e":
                collection_type = "entomology"
            elif option == "b":
                collection_type = "botany"
            elif option == "o":
                collection_type = "other"
            elif option == "l":
                collection_type = "library"
            elif option == "g":
                collection_type = "geology"
        match.update(ignore=False, collection=collection_type)

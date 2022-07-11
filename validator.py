from db_connection import DBConnection
from utils_mixin import Utils
import subprocess
import os
import re
from colorama import Fore, Back, Style
from ete3 import NCBITaxa
import enchant
from scan import Scan
from datetime import datetime

ncbi = NCBITaxa()


# ncbi.update_taxonomy_database()


# f"{Fore.MAGENTA + self.chromosome.id + Fore.WHITE}:" \
class Match(Utils):
    def __init__(self, doi, score, title, full_path, published_date):
        self.doi = doi
        self.score = score
        self.title = title
        self.published_date = published_date
        self.full_path = full_path

    def print(self):
        print("--------------")
        print(f"Score: {self.score} title: {self.title}")
        print(f"doi: {self.doi} date:{self.published_date} path: {self.full_path}")

    def print_matched_lines(self):
        sql = f"select line,score from found_scan_lines where doi = '{self.doi}'"
        lines = DBConnection.execute_query(sql)
        regex_tuples = Scan.get_regex_score_tuples()
        for line in lines:
            matched_line = line[0]
            matches = []
            for regex_tuple in regex_tuples:
                result = re.search(regex_tuple[0], matched_line)
                if result is not None:
                    matches.append((result.group(0), regex_tuple[1]))

            matches.sort(key=lambda x: x[1], reverse=True)
            if len(matches) > 0:
                color = Fore.BLUE
                score = matches[0][1]
                matched = matches[0][0]
                if score < 0:
                    color = Fore.MAGENTA
                if score > 200:
                    color = Fore.YELLOW
                if score > 300:
                    color = Fore.RED

                matched_line = matched_line.replace(matched, f'{color}{matched}{Fore.RESET}')
                # print(f"    {regex_tuple[0]}\t{matched_line}")

                # matched_line = matched_line.replace('california',f'{Fore.MAGENTA}california{Fore.RESET}')
                # matched_line = matched_line.replace('cas',f'{Fore.RED}cas{Fore.RESET}')

                print(f"{score}: {matched_line}")

    def open(self):
        command = "/usr/bin/open"
        pwd = os.getcwd()
        pdf_file = f"{pwd}/{self.full_path}"
        subprocess.call([command, pdf_file])

    def update(self, ignore, collection=None):
        #  for updating match records
        # sql = f"""delete from matches where doi='{self.doi}'"""
        # DBConnection.execute_query(sql)

        if ignore:
            tf = "TRUE"
        else:
            tf = "FALSE"
        sql = f""" insert into matches (doi,collection,ignore,date_added) values (?,?,?,?)"""
        args = [self.doi, collection, ignore, datetime.now()]
        DBConnection.execute_query(sql, args)


class Validator(Utils):
    def __init__(self, reset_matches_database=False):
        self.matches = []

        self._create_tables(reset_matches_database=reset_matches_database)

    def get_matched_paper_dois(self):
        sql = f"""select doi from matches where ignore=FALSE"""
        results = DBConnection.execute_query(sql)
        return [x[0] for x in results]

    def _create_tables(self, reset_matches_database=False):
        if reset_matches_database:
            sql = "drop table matches"
            DBConnection.execute_query(sql)
        sql_create_database_table = """ CREATE TABLE IF NOT EXISTS matches (
                                                doi text primary key NOT NULL,
                                                collection text,
                                                ignore boolean,
                                                date_added DATE
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
        sql = f"""select dois.doi, dois.full_path, dois.published_date, scans.title, scans.score from scans,dois
                                    left join matches m on dois.doi = m.doi
                                    where
                                    scans.doi = dois.doi and
                                    dois.{self.sql_year_restriction(start_year, end_year)} and
                                    scans.score is not null and
                                    m.doi is NULL and
                                    score > 0
                                    order by score desc 
        """

        candidates = DBConnection.execute_query(sql)
        for candidate in candidates:
            doi = candidate[0]
            full_path = candidate[1]
            published_date = candidate[2]
            title = candidate[3]
            score = candidate[4]
            self.matches.append(Match(doi, score, title, full_path, published_date))

        for match in self.matches:
            self.prompt(match)

    def get_lineage(self, word, verbose=False):
        name2taxid = ncbi.get_name_translator([word])
        if len(name2taxid) == 0:
            return None
        if verbose:
            print(f"Word: {word}")
        assert len(name2taxid) == 1
        name = list(name2taxid.keys())[0]
        taxid = name2taxid[name][0]
        # print(f"   taxid: {taxid}")
        lineage = ncbi.get_lineage(taxid)
        names_dict = ncbi.get_taxid_translator(lineage)
        lineage_names = [names_dict[taxid] for taxid in lineage]

        names = [item.lower() for item in lineage_names]
        return names

    def categorize_lineage(self, lineages, verbose=False):
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
                                print(f"Conflict between {retval} and {department}, returning none")
                                return None
                        if verbose:
                            print(f"Matching {name} to {department} via lineage: {lineage}")
                        retval = department

        return retval

    def analyze_title(self, title, verbose=False):
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
            print(f"It's in {Fore.GREEN}{department}{Fore.RESET}")
        if verbose:
            for lineage in found_lineages:
                print(f"  Lineage:{lineage}")

    def prompt(self, match):
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

    def prompt_add_type(self, match):
        collection_type = None
        while collection_type is None:
            option = input("Herpetology(H) Ichthyology(I) O&M(O) IZ&G(Z) Anthropology(A) Entomology(E) Botany(B)")
            option = option.lower()
            if option == "h":
                collection_type = "herpetology"
            elif option == "i":
                collection_type = "ichthyology"
            elif option == "o":
                collection_type = "o&m"
            elif option == "z":
                collection_type = "iz&g"
            elif option == "a":
                collection_type = "anthropology"
            elif option == "e":
                collection_type = "entomology"
            elif option == "b":
                collection_type = "botany"
        match.update(ignore=False, collection=collection_type)

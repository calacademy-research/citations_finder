import re
import os
from config import Config
from db_connection import DBConnection
from doi_entry import DoiFactory
import logging
from io import StringIO
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from tabula import read_pdf
from PyPDF2 import PdfReader
import threading


class Scan:
    broken_converter: bool
    # TODO: this only encompasses a few of the tags we end up scanning for
    # in more detail with user specified things later - and I think it's currently the screening
    # step. that's bad; let's review to ensure that the top level screen encompasses
    # all the strings currently in _get_collection_manager_names and
    # _get_scored_strings.
    config = Config()

    def __init__(self, doi_object=None, doi_string=None):
        """Initializes an instance of the Scan class.

        :param doi_object: An object representing a Digital Object Identifier (DOI), defaults to None.
        :type doi_object: DOIObjectType, optional
        :param doi_string: A string representing a DOI, defaults to None.
        :type doi_string: str, optional
        :raises NotImplementedError: If neither doi_object nor doi_string is provided.
        :raises RecordNotFoundException: If the DOI query does not yield the expected results.
        """
        self.references_keywords = ["references", "referencias", "литература", "literature cited"]

        self.text_directory = self.config.get_string('scan', 'scan_text_directory')
        if not os.path.exists(self.text_directory):
            os.mkdir(self.text_directory)
            logging.info(f"Created directory to store interpolated text files: {self.text_directory}")
        if doi_object is None and doi_string is None:
            raise NotImplementedError("Provide an object or a string")
        if doi_string is not None and doi_object is None:
            select_doi = f"""select * from dois where doi = '{doi_string}'"""
            doi_object = DoiFactory(select_doi).dois
            if len(doi_object) != 1:
                raise RecordNotFoundException(f"{select_doi}")
            else:
                doi_object = doi_object[0]

        doi_string = doi_object.doi
        sql = f"""select * from scans where doi = '{doi_string}'"""
        scan_db_results = DBConnection.execute_query(sql)
        if len(scan_db_results) == 1:
            # logging.debug(f"{scan_db_results}")
            self.doi_string = scan_db_results[0][0]
            self.textfile_path = scan_db_results[0][1]
            self.score = scan_db_results[0][2]
            self.broken_converter = scan_db_results[0][3]
            self.title = scan_db_results[0][4]
            self.doi_object = doi_object
        else:
            self._init_from_object(doi_object)
            self._write_to_db()

        self.found_lines = []  # not currently saved

    @classmethod
    def clear_db_entry(self, doi):
        sql = f"delete from scans where doi='{doi}'"
        DBConnection.execute_query(sql)
        sql = f"delete from found_scan_lines where doi='{doi}'"
        DBConnection.execute_query(sql)

    def _write_to_db(self, write_scan_lines=False, clear_existing_records=False):
        """Stores information about a scan operation in the database. It inserts or replaces records in the 'scans'
        table, containing details such as DOI, file path, score, converter status, and title. If specified, it also logs
        individual found scan lines with their associated scores and matched strings in the 'found_scan_lines' table.

        :param write_scan_lines: If True, write found scan lines to the database, defaults to False
        :type write_scan_lines: bool, optional
        :param clear_existing_records: If True, clear existing records before writing, defaults to False
        :type clear_existing_records: bool, optional
        """
        if clear_existing_records:
            Scan.clear_db_entry(self.doi_string)
        sql_insert = f"""replace into scans (doi, textfile_path,score,cannot_convert,title) VALUES (%s,%s,%s,%s,%s)"""
        args = [self.doi_string,
                self.textfile_path,
                self.score,
                self.broken_converter,
                self.doi_object.get_title()]
        DBConnection.execute_query(sql_insert, args)
        if write_scan_lines and len(self.found_lines) > 0:
            for score_tuple in self.found_lines:
                sql_insert = f"""insert into found_scan_lines (doi, line, score, matched_string) VALUES (%s,%s,%s,%s)"""
                args = [self.doi_string,
                        score_tuple[0],
                        score_tuple[1],
                        score_tuple[2]]
                DBConnection.execute_query(sql_insert, args)

    def _init_from_object(self, doi_object):
        """Initializes the object using information from a DOI object.

        :param doi_object: The DOI object containing information about the associated document.
        :type doi_object: DOIObjectType  # Replace 'DOIObjectType' with the actual type of the DOI object
        :raises FileNotFoundError: If the PDF file associated with the DOI is missing.
        """
        self.textfile_path = None
        self.broken_converter = None
        if doi_object.check_and_update_file_path_variables() is False:
            raise FileNotFoundError(
                f"Missing PDF for doi {doi_object.doi}. path would be {doi_object.generate_file_path()} title: {doi_object.get_title()}")


        self.doi_object = doi_object
        self.doi_string = doi_object.doi
        self.full_path = doi_object.full_path
        self.title = doi_object.get_title()
        self._convert_pdf()
        self.found_lines = []
        self.score = None

    def __lt__(self, other):
        return self.score < other.score

    def __str__(self):
        str = f"{self.score}   {self.doi_string}:({self.doi_object.get_journal()})  {self.doi_object.details['title'][0]}"
        return str

    def extract_text_from_pdf(self, pdf_path):
        logging.getLogger('pdfminer').setLevel(logging.CRITICAL)

        output = StringIO()
        with open(pdf_path, 'rb') as file:
            laparams = LAParams(line_overlap=0.3, char_margin=2.0, line_margin=0.5, word_margin=0.1, boxes_flow=0.5)
            extract_text_to_fp(file, output, laparams=laparams)
        text = output.getvalue()
        output.close()
        return re.sub(r'\s+', ' ', text).replace('\n', ' ').replace('\-\s+', '')

    def extract_tables_from_pdf(self, pdf_path):
        all_tables = []
        try:
            # Determine the number of pages in the PDF
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                total_pages = len(pdf_reader.pages)

            # Iterate through each page to extract tables
            for page in range(1, total_pages + 1):
                try:
                    tables = read_pdf(pdf_path, pages=page, multiple_tables=True)
                    all_tables.extend(tables)
                except Exception as page_error:
                    logging.error(f"Error extracting tables on page {page}: {page_error}")

            return all_tables

        except Exception as e:
            logging.error(f"Error in processing PDF {pdf_path}: {e}")
            return []

        return all_tables

    def fix_spaced_headings(self, text, headings):
        for heading in headings:
            spaced_pattern = r'\s*'.join(char for char in heading)
            pattern = re.compile(r'\b' + spaced_pattern + r'\b', re.IGNORECASE)
            text = pattern.sub(heading, text)
        return text

    def _get_textfile_path(self):
        issn = self.doi_object.issn
        year = self.doi_object.get_date().year
        doi_basename = os.path.basename(self.doi_object.full_path)
        doi_basename = doi_basename.rsplit(".", 1)[0]
        return os.path.join(self.text_directory, issn, str(year), doi_basename + ".txt")



    def _create_textfile_path(self, path):
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)

        try:
            pdf_path = f"{os.getcwd()}/{self.doi_object.full_path}"
            text = self.extract_text_from_pdf(pdf_path)
            tables = self.extract_tables_from_pdf(pdf_path)

            text += " ".join(table.to_string(index=False, header=True) for table in
                             tables) if tables else "No tables found or an error occurred."

            text = self.fix_spaced_headings(text,
                                            ["ACKNOWLEDGMENTS", "INTRODUCTION", "ABSTRACT", "CONCLUSION", "REFERENCES",
                                             "METHODS", "RESULTS", "DISCUSSION", "LITERATURE REVIEW", "BACKGROUND",
                                             "RESEARCH PAPER", "literature cited", "ЛИТЕРАТУРА"])

            text_file_path = self._get_textfile_path()
            self._create_textfile_path(text_file_path)
            with open(text_file_path, 'w') as file:
                file.write(text)
            self.textfile_path = text_file_path
        except RecursionError as e: # bug in library
            logging.error(f"RecursionError occurred while processing {pdf_path}: {e}")


    def _run_converter_with_timeout(self):
        converter_thread = threading.Thread(target=self._run_converter_with_timeout)
        converter_thread.start()
        timeout_minutes = 10
        converter_thread.join(timeout=(60 * timeout_minutes))
        if converter_thread.is_alive():
            logging.error(f"PDF conversion timeout; operation exceeded {timeout_minutes} minutes.")
            return False
        return True
    def _convert_pdf(self, force=False):
        """Checks if a text file corresponding to the DOI object's PDF file
        exists in the specified text directory. If not, it uses the `_run_converter`
        method to convert the PDF to a text file. If the conversion is successful, the
        path to the generated text file is stored in `self.textfile_path`.

        :param force: If set to True, forces re-conversion even if the text file exists, defaults to False
        :type force: bool, optional
        :return: True if the conversion is successful or the text file already exists, False otherwise
        :rtype: bool
        """

        doi_textfile_path = self._get_textfile_path()

        if self.broken_converter:
            return False


        if not os.path.exists(doi_textfile_path) or force is True:
            if self.config.get_boolean('scan', 'disable_txt_generation'):
                logging.warning(f"    Missing text file {doi_textfile_path}, txt generateion disabled")
                return False
            logging.warning(f"    Missing txt file, generating {doi_textfile_path} from {self.doi_object.full_path}")
            self._run_converter_with_timeout()
            logging.warning(f"     Generation complete.")
            if not os.path.exists(doi_textfile_path):

                logging.error("PDF conversion failure; marking as failed and continuing.")
                self.broken_converter = True
                return False
        if os.path.exists(doi_textfile_path):
            self.textfile_path = doi_textfile_path
        return True

    @classmethod
    def _get_collection_manager_names(cls):
        collection_manager_names = cls.config.get_list('scan_search_keys', 'collection_manager_names')
        all_name_variations = []
        for test_string, score in collection_manager_names:
            test_string = test_string.lower()
            name_parts = test_string.split()
            # Case 1: last name only
            if len(name_parts) == 1:
                all_name_variations.append((test_string, score))
            else:
                first_part = name_parts[0]
                last_part = name_parts[-1]
                middle_parts = name_parts[1:-1]
                initials = [p[0] for p in name_parts]

                # Full name
                all_name_variations.append((' '.join(name_parts), score))
                # First + Last
                all_name_variations.append((f"{first_part} {last_part}", score))
                # Initials + Last
                all_name_variations.append((f"{' '.join(initials[:-1])}. {last_part}", score))
                all_name_variations.append((f"{''.join(initials[:-1])}. {last_part}", score))
                # First Initial + Middle Initial + Last
                if middle_parts:
                    all_name_variations.append(
                        (f"{first_part[0]}. {' '.join([m[0] for m in middle_parts])}. {last_part}", score))
                    all_name_variations.append(
                        (f"{first_part[0]} {' '.join([m[0] for m in middle_parts])} {last_part}", score))
                    all_name_variations.append(
                        (f"{first_part[0]}.{''.join([m[0] for m in middle_parts])}.{last_part}", score))
                    all_name_variations.append(
                        (f"{first_part[0]}.{''.join([m[0] for m in middle_parts])}. {last_part}", score))
                # Initials only
                all_name_variations.append((f"{' '.join(initials)}", score))
                all_name_variations.append((f"{''.join(initials)}", score))

                # Handle cases with dots and without for each part
                for i in range(1, len(middle_parts) + 1):
                    middle_initials = [p[0] for p in middle_parts[:i]]
                    without_middle = ' '.join([first_part, ' '.join(middle_initials), last_part])
                    with_dots = ' '.join([f"{p[0]}." for p in name_parts[:-1]]) + ' ' + last_part
                    all_name_variations.append((without_middle, score))
                    all_name_variations.append((with_dots, score))

                    # Combining middle initials without space
                    combined_middle = ''.join(middle_initials)
                    combined_with_dots = f"{first_part[0]}." + ''.join(
                        [f"{m}." for m in combined_middle]) + f" {last_part}"
                    combined_without_dots = f"{first_part[0]}" + combined_middle + f" {last_part}"
                    all_name_variations.append((combined_with_dots, score))
                    all_name_variations.append((combined_without_dots, score))

        return all_name_variations

    # @classmethod
    # def _get_collection_manager_names(cls):
    #     """Retrieves a list of collection manager names from the configuration,
    #     processes them for various variations, and returns a list of tuples containing
    #     the processed name variations and associated scores.
    #
    #     :return: A list of tuples containing processed name variations and scores
    #     :rtype: list
    #     """
    #     collection_manager_names = cls.config.get_list('scan_search_keys', 'collection_manager_names')
    #     all_name_variations = []
    #     for test_string, score in collection_manager_names:
    #         test_string = test_string.lower()
    #         # Case 1: last name only like 'shevock'
    #         if len(test_string.split()) == 1:
    #             all_name_variations.append((test_string, score))
    #             continue
    #         # Case 2: parsing full names with first, last, and middle
    #         if len(test_string.split()) == 3:
    #             firstname, middlename, lastname = test_string.split()
    #             all_name_variations.append((f"{firstname} {middlename} {lastname}", score))
    #         else:
    #             firstname, lastname = test_string.split()
    #         first_letter = firstname[0]
    #         # Case 3: parsing initial names like 'D.H. Kavanaugh'
    #         if firstname.count('.') > 1:
    #             all_name_variations.append((f"{firstname} {lastname}", score))
    #             all_name_variations.append((f"{firstname}{lastname}", score))
    #             all_name_variations.append((f"{firstname[:-1]} {lastname}", score))
    #             continue
    #         # Case 4: parsing full names with first and last
    #         elif len(firstname) != 1 and len(firstname.replace('.', '')) != 1:
    #             all_name_variations.append((f"{firstname} {lastname}", score))
    #             all_name_variations.append((f"{first_letter}. {lastname}", 200))
    #             all_name_variations.append((f"{first_letter} {lastname}", 200))
    #         # Case 5: initial name like 'd catania' or 'd. catania'
    #         else:
    #             all_name_variations.append((f"{first_letter}. {lastname}", score))
    #             all_name_variations.append((f"{first_letter} {lastname}", score))
    #     return all_name_variations

    @classmethod
    def _get_scored_strings(cls):
        """Retrieves a list of scored strings for matching from the configuration
        and returns it.

        :return: A list of scored strings for matching as defined in config.ini
        :rtype: list
        """
        # Test that hypehens and colons are parsed correctly in the
        # reguar expression sets
        string_set_pre_reference = cls.config.get_list('scan_search_keys', 'scored_strings')
        return string_set_pre_reference

    @classmethod
    def get_regex_score_tuples(cls):
        retval = []
        collection_tag_regex =  cls.config.get_string('scan_search_keys','collections_regex_match')

        retval.append((collection_tag_regex, 300))
        for regex_tuple in Scan._get_scored_strings() + Scan._get_collection_manager_names():
            regex = regex_tuple[0].lower()
            retval.append((regex, regex_tuple[1]))

        return retval

    def scan(self, clear_existing_records=False):
        """Perform a scan on the text content, evaluating various conditions to determine a score.

        :param clear_existing_records: Clear existing records if True, defaults to False
        :type clear_existing_records: bool, optional
        :return: True if scanning is successful and results are logged, False otherwise
        :rtype: bool
        """
        # logging.debug(f"Scanning: {self.textfile_path}")
        if self._convert_pdf() is False:
            # logging.warning(f"Missing PDF, not scanning: {self.textfile_path}")
            self._write_to_db()
            return False
        if clear_existing_records or self.score is None:
            self.score = 0
        regex = self.config.get_string('scan_search_keys','collections_regex_match')
        results = self._scan_with_regex(regex, 300, ok_after_references=True, do_score=False)
        for result in results:
            hyphen_count = result.count('-')
            if hyphen_count < 2:
                # logging.debug(f"Hyphens ok: {result}")
                self.score += 300
            else:
                # logging.debug(f"Hyphens bad: {result}")
                self.score -= 20

        collection_manager_names = Scan._get_collection_manager_names()

        string_set_pre_reference = Scan._get_scored_strings()
        string_set_pre_reference = string_set_pre_reference + collection_manager_names
        self._scan_keywords(string_set_pre_reference, ok_after_references=False)

        string_set_post_reference = collection_manager_names

        self._scan_keywords(string_set_post_reference, ok_after_references=True)

        if self.score > 0:
            logging.info(f"{self.score}\t{self.title}")
        self._write_to_db(write_scan_lines=True, clear_existing_records=clear_existing_records)

        return True

    def _scan_keywords(self, string_set, ok_after_references=False):
        """Scans a set of test strings for keywords using regular expressions and updates the score accordingly.

        :param string_set: A set of tuples containing test strings and their corresponding scores.
        :type string_set: set(tuple(str, int))
        :param ok_after_references: Indicates whether scoring is allowed after references, defaults to False.
        :type ok_after_references: bool, optional
        """
        for test_string, score in string_set:
            test_string = test_string.lower()
            # logging.info(f"Scanning test string: {test_string}")
            regex = f"(?i)(([ \(\[])+|^){test_string}(([ ,.:])+|$)"
            regex_result_count = self._scan_with_regex(regex, score, ok_after_references)
            # if regex_result_count > 0:
            #     logging.info(f"Found: {test_string} Score: {self.score}")

    def scan_specimen_ids(self):
        if self.score is None:
            self.score = 0
        regex = self.config.get_string('scan_search_keys','collections_regex_match')

        return self._scan_with_regex(regex, 1, False)

    def _scan_with_regex(self, regex, score_per_line, ok_after_references, do_score=True):
        results = []
        logging.debug(f"Scanning with regex: {regex}")
        found_count = 0
        with open(self._get_textfile_path(), "r") as a_file:
            lines = [line.lower().strip() for line in a_file if line.strip()]
        lines = self.split_references_from_lines(lines)

        for i, line in enumerate(lines):
            if not ok_after_references and self._is_references_section(line):
                # logging.debug("Stopping scan before references.")
                break
            result = re.search(regex, line)
            if result:
                results.append(result.group(0))
                contexts = self.extract_context(line, regex,15)
                for context in contexts:
                    self.found_lines.append((context, score_per_line, result.group(0)))
                    found_count += 1

        if do_score:
            self._update_score(found_count, score_per_line)
        return results


    def extract_context(self, line, regex, window=20):
        words = line.split()
        match_positions = [m.start() for m in re.finditer(regex, line)]
        contexts = []
        for position in match_positions:
            start_pos = position
            end_pos = position
            start_space_count = end_space_count = 0

            while start_space_count < window and start_pos > 0:
                start_pos -= 1
                if line[start_pos] == ' ':
                    start_space_count += 1

            while end_space_count < window and end_pos < len(line) - 1:
                end_pos += 1
                if line[end_pos] == ' ':
                    end_space_count += 1

            match_word_start = line.rfind(' ', 0, start_pos) + 1
            match_word_end = line.find(' ', end_pos, len(line))
            if match_word_end == -1: match_word_end = len(line)

            context = line[max(0, match_word_start):min(len(line), match_word_end)]
            contexts.append(context)

        return contexts


    def _prepare_line_for_search(self, cur_line, next_words):
        if cur_line is not None:
            cur_line = cur_line.strip().rstrip('-')
            for i, next_word in enumerate(next_words[:4]):
                cur_line += f" {next_word}" if cur_line[-1] != '-' else next_word
        return cur_line

    def _is_references_section(self, next_line):
        return any(keyword in next_line for keyword in self.references_keywords)

    def split_references_from_lines(self, lines):
        pattern = re.compile(r'(' + '|'.join(self.references_keywords) + ')', re.IGNORECASE)
        split_lines = []
        references_start = None
        for i, line in enumerate(reversed(lines)):
            if references_start is None and any(
                    keyword.lower() in line.lower() for keyword in self.references_keywords):
                references_start = len(lines) - i - 1
                break
        if references_start is not None:
            for i, line in enumerate(lines):
                if i == references_start:
                    parts = re.split(pattern, line, maxsplit=1)
                    if len(parts) > 1:
                        split_lines.extend([parts[0]] + [parts[1] + ''.join(parts[2:])])
                    else:
                        split_lines.append(line)
                else:
                    split_lines.append(line)
        else:
            split_lines = lines
        return split_lines

    def _update_score(self, found_count, score_per_line):
        old_score = self.score
        self.score += score_per_line * found_count
        # if found_count > 0:
        #     logging.debug(f"Score change. From {old_score} to {self.score}")


class RecordNotFoundException(Exception):
    pass

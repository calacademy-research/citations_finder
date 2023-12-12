import requests
from collections import defaultdict
import csv
import logging

def _getGBIFResults(gbif_url):
    """Retrieves the results of gbif_url in json format, 
    and capture the "results" portion (contains a lot of metadata about 
    a scientific article). GBIF means Global Biodiversity 
    Information Facility, an international network and research
    infrastructure aimed at providing open access to data about 
    all types of life on Earth, including plants, animals, fungi,
    and microbes

    :param gbif_url: gbif_api_collection_links as defined in congfig.ini
    :type gbif_url: str
    :return: jason results from gbif_api_collection_links 
    :rtype: list
    """    
    response = requests.get(gbif_url, allow_redirects=True)
    response_data = response.json()
    results = response_data['results']
    return results

def _getCrossrefResults(doi, journal_dict):
    """Uses crossref api to retrieve in json format all relevant 
    doi data, particularly "message"(all the metadata) and "container_title" (journal name).
    Next, loops over all the the doi titles, create a journal dictionary 
    in the format of:
        { "Journal Name":
        {issn value: issn type,issn value: issn type}

    :param doi: _description_
    :type doi: _type_
    :param journal_dict: _description_
    :type journal_dict: _type_
    :return: _description_
    :rtype: _type_
    """    
    crossref_url = f"https://api.crossref.org/works/{doi}"
    crossref_response = requests.get(crossref_url, allow_redirects=True)
    crossref_response.raise_for_status()
    crossref_data = crossref_response.json()
    title = crossref_data['message']['container-title'][0]
    if title not in journal_dict:
        issn_types = crossref_data['message']['issn-type']
        for issn in issn_types:
            journal_dict[title][issn['value']] = issn['type']
    return journal_dict


def _findISSNByJournalTitle(result, journal_dict, total, errors=None):
    """Finds ISSN of a journal by its title and update the journal_dict.

    Try and find journal name (crossref: "source", renamed in code to "title") 
    in journal_dict. If not found, add to the journal_dict, with { "Journal Name":
        {issn value: issn type}.
    If there is an error due to the journal name being absent from crossref, AND errors is not None (True),
    return "Journal title cannot be found". 
    If error out by only errors is not None (True), return "ISSN of journal '{title}' 
    cannot be found". 
    Both of those errors are added to list "errors". Lastly, return journal_dict_


    :param result: A dictionary containing journal information, including the 'source' field representing the journal title.
    :type result: dict
    :param journal_dict: A dictionary containing existing journal information, where the keys are journal titles and the values are dictionaries of ISSN values and their types.
    :type journal_dict: dict
    :param total: The total number of processed items.
    :type total: int
    :param errors: A list to store error messages, defaults to None.
    :type errors: list, optional
    :return: The updated journal_dict.
    :rtype: dict
    """    
    """

    """    
    try:
        title = result['source']
        if title not in journal_dict:
            crossref_url = f"https://api.crossref.org/journals?query={title}"
            crossref_response = requests.get(crossref_url, allow_redirects=True)
            crossref_response.raise_for_status()
            crossref_data = crossref_response.json()
            issn_types = crossref_data['message']['items'][0]['issn-type']
            for issn in issn_types:
                journal_dict[title][issn['value']] = issn['type']
    except (KeyError, IndexError, requests.exceptions.RequestException):
        if 'source' not in result and errors != None:
            errors.append(f"Search {total}: Journal title cannot be found")
        elif errors != None:
            errors.append(f"Search {total}: ISSN of journal '{title}' cannot be found")
    finally:
        return journal_dict

def _getExistingJournals(file_name):
    """Retrieve existing journals from a file 'journals.tsv'.

    :param file_name: Name of the file to read the journals from.
    :type file_name: str
    :return: Dictionary of existing journals, where the ISSN is the key and the value is set to None.
    :rtype: dict
    """    
    existing_journals = {}
    with open(file_name, 'r') as tsvin:
        for line in csv.reader(tsvin, delimiter='\t'):
            try:
                if len(line) == 0 or line[0].startswith('#'):
                    continue
                issn = line[0]
                if issn not in existing_journals:
                    existing_journals[issn] = None
            except Exception as e:
                logging.warning(f"Parsing error: {line}, skipping.")
                continue
    return existing_journals


def addJournals(file_name, url):
    """reads existing journals from a file 'journals.tsv', retrieves journal information 
    from api.gbif.org, updates the journal dictionary with ISSN and ISSN type, 
    and writes new journal information to the same file.

    :param file_name: Name of the file 'journals.tsv' to which the journal 
    information will be appended.
    :type file_name: str
    :param url: URL of the GBIF API to retrieve results.
    :type url: str
    """
    journal_dict = defaultdict(dict)
    total = 0

    existing_journals = _getExistingJournals(file_name)
    results = _getGBIFResults(url)

    for item in results:
        total += 1
        if (total % 10 == 0):
            logging.info(f"...Done {total} out of {len(results)}")
        try:
            doi = item['identifiers']['doi']
            journal_dict = _getCrossrefResults(doi, journal_dict)
        except (KeyError, IndexError, requests.exceptions.RequestException) as e:
            journal_dict = _findISSNByJournalTitle(item, journal_dict, total)

    with open(file_name, 'a') as file:
        for journal, issn_dict in sorted(journal_dict.items()):
            for issn, issn_type in issn_dict.items():
                if issn not in existing_journals:
                    file.write(f"{issn}\t{journal}\t{issn_type}\n")
    logging.info(f"...Done {total} out of {total}")


def printJournalList(url):
    """Print a list of journals and their associated ISSN numbers based on a given URL.

    :param url: The URL of the data source.
    :type url: str
    """    
    journal_dict = defaultdict(dict)
    total = 0
    errors = []
    issn_count = 0

    results = _getGBIFResults(url)

    for item in results:
        total += 1
        if (total % 10 == 0):
            logging.info(f"Done {total} out of {len(results)}")
        try:
            doi = item['identifiers']['doi']
            journal_dict = _getCrossrefResults(doi, journal_dict)
        except (KeyError, IndexError, requests.exceptions.RequestException) as e:
            journal_dict = _findISSNByJournalTitle(item, journal_dict, total, errors)

    for journal, issn_dict in sorted(journal_dict.items()):
        for issn, issn_type in issn_dict.items():
            logging.info(f"{issn}\t{journal}\t{issn_type}")
            issn_count += 1

    logging.info(f"\nTotal Number of Results: {total} | Unique Journals Found: {len(journal_dict)} | Not Found: {len(errors)} | Unique ISSN's Found: {issn_count} | Duplicates: {total - len(journal_dict) - len(errors)}")
    for e in errors:
        logging.info(e)


if __name__ == '__main__':
    limit = 20
    botany_url = f"`https://api.gbif.org/v1/literature/search?contentType=literature&year=2021,%20%20%202022&literatureType=journal&gbifDatasetKey=f934f8e2-32ca-46a7-b2f8-b032a4740454`&limit={limit}"
    printJournalList(botany_url)
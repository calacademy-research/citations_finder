import requests
from collections import defaultdict
import csv
import logging

def _getGBIFResults(gbif_url):
    response = requests.get(gbif_url, allow_redirects=True)
    response_data = response.json()
    results = response_data['results']
    return results


def _getCrossrefResults(doi, journal_dict):
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
                print(f"Parsing error: {line}, skipping.")
                continue
    return existing_journals


def addJournals(file_name, url):
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

    print(f"\nTotal Number of Results: {total} | Unique Journals Found: {len(journal_dict)} | Not Found: {len(errors)} | Unique ISSN's Found: {issn_count} | Duplicates: {total - len(journal_dict) - len(errors)}")
    for e in errors:
        print(e)


if __name__ == '__main__':
    limit = 20
    botany_url = f"https://api.gbif.org/v1/literature/search?contentType=literature&year=2021,%20%20%202022&literatureType=journal&gbifDatasetKey=f934f8e2-32ca-46a7-b2f8-b032a4740454&limit={limit}"
    printJournalList(botany_url)
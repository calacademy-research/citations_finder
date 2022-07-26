import requests
from collections import defaultdict

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


def _findISSNByJournalTitle(result, journal_dict, total, errors):
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
        if 'source' not in result:
            errors.append(f"Search {total}: Journal title cannot be found")
        else:
            errors.append(f"Search {total}: ISSN of journal '{title}' cannot be found")
    finally:
        return journal_dict


def printJournalList(url):
    journal_dict = defaultdict(dict)
    total = 0
    errors = []
    issn_count = 0

    results = _getGBIFResults(url)

    for item in results:
        total += 1
        # print(f"Processing Result {total}...")
        try:
            doi = item['identifiers']['doi']
            journal_dict = _getCrossrefResults(doi, journal_dict)
        except (KeyError, IndexError, requests.exceptions.RequestException) as e:
            journal_dict = _findISSNByJournalTitle(item, journal_dict, total, errors)

    for journal, issn_dict in sorted(journal_dict.items()):
        for issn, issn_type in issn_dict.items():
            print(f"{issn}\t{journal}\t{issn_type}")
            issn_count += 1

    print(f"\nTotal Number of Results: {total} | Unique Journals Found: {len(journal_dict)} | Not Found: {len(errors)} | Unique ISSN's Found: {issn_count} | Duplicates: {total - len(journal_dict) - len(errors)}")
    for e in errors:
        print(e)


limit = 1000
botany_url = f"https://api.gbif.org/v1/literature/search?contentType=literature&year=2021,%20%20%202022&literatureType=journal&gbifDatasetKey=f934f8e2-32ca-46a7-b2f8-b032a4740454&limit={limit}"
printJournalList(botany_url)
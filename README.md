# Citations finder for natural history museums

Locates citations in literature for a single natural history museum. This is meant to supplement
literature references which do not include usage of museum collections. Distinguishes between purely
electronic collections (databses and other projects) and physcial collections.

## Approach

Identifies DOIs based on journals listed in journals.tsv. Uses crossref.org to extract DOIs of interest.
These are passed on to custom downloaders to acquire papers (PDFs). Currently, this is only "unpaywall.org",
which
includes all open source literature, but downloaders can be custom written for subscriptions that
any given institution may have.

These papers are then converted to txt files and scanned for custom phrases, each of which has
an associated score (scores can be negative).

These results are then presented to the user, sorted from high to low scores. The results are
scanned for taxonomic nomenclature and sorted into the appropriate collection.

Finally, the human verified papers are exported into a directory, and a summary is exported to TSV.

### Existing PDFs

PDFs are stored in the "pdf_directory" set in config.ini. The format is derived from
DOIs, thusly:

    sanitized_identifier = doi_string.replace('/', '_')
    dest_path = sanitized_identifier + ".pdf"

Ensure any existing PDFs conform to this format, place them in said directory, and run
download. Download will use downloaded papers when available.

Note that if your doi_database is empty (i.e. if you haven't done the initial and/or forced
download for crossref in config.ini) you can import these papers by using the "import_pdfs"
function in doi_database.db. currently this would need to be hardcoded for a one-time run in
main.py

# Steps

config.ini contains initial configuration. An example config.ini is in config.template.ini.
The only entrypoint is main.py - so

```#python3 ./main.py ```

will start the program. What gets run is then controlled by the contents of config.ini.

0. **General**:

   Generate a report of downloaded papers on launch. Takes some time to run, so it
   can be disabled.


1. **Crossref DOI updates**

   Ingests the list of targeted publications from journals.tsv. See settings; this is a no-op
   after the initial run. If it's not already marked in the database as complete,
   downloads all the DOI data from crossref from each in the year range indicated.

Currently won't download papers newer than the oldest requested. In other words, if at any time users
requested papers from, say, 2014 and ONLY 2014, the system will assume that papers newer than
2014 have all been downloded. In case of partial downloads use force-download option for missing years.

Downloads from crossref "politely" using a back-off algorithm to not saturate their site.

1. **download (downloaders)**

   Runs the downloader modules (derived from class "downloader") in the order listed in modules.

   **WARNING: this will ERASE the "firefox_save_directory". see "firefox downloading" below for details.**


3. **scan**

   Scans are the results of the automated scoring process. They are not vetted by humans - after scans run
   through the scoring process (this step)
   Generates a score for each paper of interest. On instantiation, scan either loads the existing scan and
   score from the scans table in the database or if absent, it initialises these values and converts PDFs to
   txt.
   It then scores by running the set of regular expressions, (currently hardcoded; these
   belong in config.ini) to generate scores for the papers that have been downloaded.


4. **scan_for_specimen_ids**

   An attempt to harvest the actual specimen ids. Doesn't work very well (formats in papers are
   nonstandard, and often in appendices that aren't necessarily attached to the public PDF). Results
   stored in matched_specimen_ids in the database, linking specimen ID to DOI. Added to copyout report.

5. **validate**

   Interactive step to validate hits in the collection. Does a pretty good job based on linnean naming
   to determine which collection each paper belongs to. Runs from high scores to low.

6. **copyout**

   Copies the papers identified in the validate step to a directory in config.ini and exports tsv summaries
   of the hits.

## General info:

Uses a local sqlite (doi_database.db) database as a datastore, and will create this file and run the DDL as
needed.
config.ini has detailed comments on initial settings. Most of this currently relies on unpaywall.org,
but downloaders are modular and could be written for any paid subscriptions that you have access to.
Downloaders have their own custom SQL tables and can have independent retry logic.

## Development status:

Fully tested; the current major problem is hardcoding of CAS specific search terms. These can
(and should) be moved to config.ini.

## Firefox downloading:

Some sites have enabled ddos protection. As a last resort, it is possible to have the citations_finder
launch a firefox browser, hit the URL in question with the actual browser, save the result, and import it.
This requires some configuration tweaking; on the mac (the only platform tested thus far), we use the
pyautogui module to simulate user keyboard input (command-s to save). For this to work, you
must enable the application running citations_finder (e.g.: command, or pycharm) to do keyboard input.



# Technical notes

All times stored are in localtime, not GMT.

The program performs poorly if the host system sleeps. Prevent that with programs like
"amphetamine" for mac

# Installation and running

Currently only tested on mac. create a virtual environment using the requirements.txt file.

# TODOS

* Examine metapub: https://github.com/metapub as a possible source for how to download papers and/or approach

* Examine https://github.com/scholarly-python-package/scholarly/blob/main/scholarly/_proxy_generator.py
  as a potenital source of captcha bypasses (also
  check https://scholarly.readthedocs.io/en/stable/quickstart.html#using-proxies)

* We're hitting a lot of ddos protections. Detect this condition and Integrate with a VPN (ala nord vpn)
  to auto rotate the origin IP to see if this gets around the ddos wall. [no known vpn api works on mac,
  more research required]

* archive.org downloader (may be subsumed in unpaywall.org)

* start_year and end_year are useful in journals but they're also may be being used in some cases
  to determine if dois are downloaded. Audit the usage of journals start_year and end_year
  to ensure they're not overgeneralized.

* unpaywall_downloader:  "download_link" doesn't work very well. Most of the time this links to an
  html version of the paper. Currently only handles direct-to-PDF links. However, it's hard to tell the
  differnce between an html-ified paper and a "can't find" or a ddos protection page. Possible solutions:
  look for the existance of a "download pdf" button. This might indicate that it is indeed an html-ified
  paper (we'd need to support that, but it's actually a better data source than pdf->text) or actually
  use said button's URL to download the true PDF.

* Get specimen count compare to pubs on a per institution ratio

* note known failure case - we don't always OCR 90 degree rotated tables

* journals.tsv has good coverage for herp, IZ. Everything else could be expanded.

* parallelize the scan

* are keywords available through crossref.org? scan them for scores

* once we ID collections papers, calculate their citation impact

* can google scholar do smarter searches for possible references?

* web interface that supports uploading pdf/dois (bulk?)

* ResearchGate or Academia.edu have many papers that have been uploaded by authors.

* Impact factor for our references per crossref?

* gather metrics from digital collections?

* Scan doi repo for string, compare to google scholar

* Scan microsoft academic for string, compare to google scholar

* Support adding PDFs from journals that lack DOIs. e.g.: Herpetological Conservation & Biology

* Test that hypehens and colons are parsed correctly in the regular expression search sets

* Bug: Scan is picking up "j, fong" (example) when it should be scanning only for "j. fong"

* Todo: Add "cas number" to exclusion when above bug is fixed

* TODO: bug in scanning (potentially very bad) - in scan.py:
  this only encompasses a few of the tags we end up scanning for
  in more detail with user specified things later - and I think it's currently the screening
  step. that's bad; let's review to ensure that the top level screen encompasses
  all the strings currently in _get_collection_manager_names and
  _get_scored_strings.

* TODO: doi_database downloading from crossref - api only presents with "oldest year", but
  if the results come in date order it would be possbile to download specific years instead of oldest
  to now. It is likely that this is so, someone should confirm with RTFM

  * Bug: in certain conditions, we can show a paper as downloaded but not have the 
     corresponding PDF. Running "update_pdf_file_link" true will update the downloaded flag
     in the DOI record. However, (only tested for unpaywall_downloader), the missing papers
     that have an unpaywall downloader row entry are NOT retried. Underlying bug should be found
     and fixed, but cleared this with:

             DELETE FROM collections_papers.unpaywall_downloader
          WHERE EXISTS (
              SELECT 1
              FROM collections_papers.dois
              WHERE unpaywall_downloader.doi = dois.doi
                AND unpaywall_downloader.not_available != 1
                AND dois.downloaded = 0
          );




* Generalize to work on windows - use os.path.join instead of slashes using (os.path.sep) and os.path.join.

* Change __full_path__ field name in doi database table to __relative_path__ and propagate change across package

Can't download these; it should work! 10.3390/plants11071002 10.3390/plants11081024 10.3390/plants11081012 are
similar.

Peerj - write a downloader:
app3_1 | Downloading from Unpaywall URL: https://peerj.com/articles/10006.pdf
app3_1 | Starting new HTTPS connection (1): peerj.com:443
app3_1 | /usr/local/lib/python3.10/dist-packages/urllib3/connectionpool.py:1099: InsecureRequestWarning:
Unverified HTTPS request is being made to host 'peerj.com'. Adding certificate verification is strongly
advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
app3_1 | warnings.warn(
app3_1 | https://peerj.com:443 "GET /articles/10006.pdf HTTP/1.1" 400 1702
app3_1 | Traceback (most recent call last):
app3_1 | File "/app/unpaywall_downloader.py", line 209, in _download_unpaywall
app3_1 | return self._attempt_download(doi_entry)
app3_1 | File "/app/unpaywall_downloader.py", line 276, in _attempt_download
app3_1 | response, self.error_code = self._download_url_to_pdf_bin(doi_entry, self.open_url,
self.PDF_DIRECTORY)
app3_1 | File "/app/downloader.py", line 80, in _download_url_to_pdf_bin
app3_1 | if 'html' not in r.headers['Content-Type']:
app3_1 | File "/usr/local/lib/python3.10/dist-packages/requests/structures.py", line 52, in __getitem__
app3_1 | return self._store[key.lower()][1]
app3_1 | KeyError: 'content-type'
app3_1 | Unexpected exception during download: 'content-type'
app3_1 | FAILED download
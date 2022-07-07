# Citations finder for natural history museums



  Locates citations in literature for a single natural history museum. 

## Approach

  Uses custom downloaders to acquire papers. Currently, this is only "unpaywall.org", which 
includes all open source literature, but downloaders can be custom written for subscriptions that 
any given institution may have.
  
These papers are then converted to txt files and scanned for custom phrases, each of which has 
an associated score (scores can be negative). 

These results are then presentd to the user, sorted from high to low scores. The results are
scanned for taxonomic nomenclature and sorted into the appropriate collection. 

Finally, the human verified papers are exported into a directory, and a summary is exported to TSV.


### Existing PDFs
  PDFs are stored in the "pdf_directory" set in config.ini. The format is derived from 
DOIs, thusly:

    sanitized_identifier = doi_string.replace('/', '_')
    dest_path = sanitized_identifier + ".pdf"

  Ensure any existing PDFs conform to this format, place them in said directory, and run
verify. Instead of downloading, the verification step will import the existing PDFs into the 
database.


# Steps

config.ini contains initial configuration. An example config.ini is in config.template.ini.

0. **General**:

    Generate a report of downloaded papers on launch. Takes some time to run, so it
    can be disabled.


1. **Crossref DOI updates**

   Ingests the list of targeted publications from journals.tsv. See settings; this is a no-op
   after the initial run. If it's not already marked in the database as complete, 
   downloads all the DOI data from crossref from each journal up to the year indicated. (crossref only
   supports downloading from a given date until most recent). Downlads from crossref "politely" using 
   a back-off algorithm to not saturate their site.


1. **verify (downloaders)**

   Runs the downloader modules (derived from class "downloader") in the order listed in modules. 
  
    **WARNING: this will ERASE the "firefox_save_directory". see "firefox downloading" below for details.**


3. **scan**

    Converts PDFs to text and Runs the set of regular expressions, (currently hardcoded; these
    belong in config.ini) to generate scores for the papers that have been downloaded. 


4. **scan_for_collection_ids** 

    An attempt to harvest the actual specimen ids. Doesn't work very well.

5. **validate**

   Interactive step to validate hits in the collection. Does a pretty good job based on linnean naming
   to determine which collection each paper belongs to. Runs from high scores to low. 

6. **copyout**

    Copies the papers identified in the validate step to a directory in config.ini and exports tsv summaries
    of the hits.


## General info:
Uses a local sqlite (doi_database.db) database as a datastore, and will create this file and run the DDL as needed.
config.ini has detailed comments on initial settings. Most of this currently relies on unpaywall.org,
but downloaders are modular and could be written for any paid subscriptions that you have access to.
Downloaders have their own custom SQL tables and can have independent retry logic.

## Development status:
As of 7/7/22: big rewrite prior to release; have only re-tested through step 3 (scan)

## Firefox downloading:
Some sites have enabled ddos protection. As a last resort, it is possible to have the citations_finder
launch a firefox browser, hit the URL in question with the actual browser, save the result, and import it.
This requires some configuration tweaking; on the mac (the only platform tested thus far), we use the
pyautogui module to simulate user keyboard input (command-s to save). For this to work, you 
must enable the application running citations_finder (e.g.: command, or pycharm) to do keyboard input.

**WARNING WARNING WARNING**:
This will ERASE the contents of firefox_save_directory. Recommended that you change the default firefox 
save directory to something specific while running in this mode.

# Installation and running
Currently only tested on mac. create a virtual environment using the requirements.txt file. 

# TODOS
 * PDF directory is flat; should with one directory per issn, at least, and possibly per year. Write 
   converter for existing downloads and then update the Utils.get_filename_from_doi_string function.

 * Generalize to work on windows - use os.path.join instead of slashes

 * scan for collection ids should be "Scan for specimen IDs" 

 * put custom phrases to scan for (and scoring) into config.ini
 
 * archive.org downloader

 * Use proper logging and log levels - everything is prints now.

 * Get specimen count compare to pubs on a per instutiuion ratio

 * Get DOI metadata from datacite: https://support.datacite.org/docs/api-queries

 * note known failure case - we don't always OCR 90 degree rotated tables

 * parallelize the scan

 * are keywords available through crossref.org? scan them for scores

 * once we ID collections papers, calculate their citation impact

 * can google scholar do smarter searches for possible references?

 * web interface that supports uploading pdf/dois (bulk?)

 * ResearchGate or Academia.edu have many papers that have been uploaded by authors.

 * Impact factor for our references per crossref?

 * gather metrics from antweb

 * Scan doi repo for string, compare to google scholar

 * Scan microsoft academic for string, compare to google scholar

 * Support adding PDFs from journals that lack DOIs. e.g.: Herpetological Conservation & Biology
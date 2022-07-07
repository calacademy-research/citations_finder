# citations finder for natural history museums

Note: This is a proof of concept that worked better than expected. There's a lot of cleanup to be done.

config.ini contains initial configuration. Customize at will. 


Steps:

0: General
    Generate a report of downloaded papers on launch. Takes some time to run, so it
    can be disabled.

1: Crossref DOI updates
  Ingests the list of targeted publications from journals.tsv. See settings; this is a no-op
after the initial run. If it's not already marked in the database as complete, 
downloads all the DOI data from crossref from each journal up to the year indicated. (crossref only
supports downloading from a given date until most recent). Downlads from crossref "politely" using 
a back-off algorithm to not saturate their site.

2: verify (downloaders)
  Runs the downloader modules (derived from class "downloader") in the order listed in modules. 
  WARNING: this will ERASE the "firefox_save_directory". see "firefox downloading" below for details.

3: scan
  Converts PDFs to text and Runs the set of regular expressions, (currently hardcoded; these 
belong in config.ini) to generate scores for the papers that have been downloaded. 

4: scan_for_collection_ids (TODO: should be specimen Ids)
  An attempt to harvest the actual specimen ids. Doesn't work very well.

5: validate
  Interactive step to validate hits in the collection. Does a pretty good job based on linnean naming
to determine which collection each paper belongs to. Runs from high scores to low. 

6: copyout
  Copies the papers identified in the validate step to a directory in config.ini and exports tsv summaries
of the hits.

General info:
Uses a local sqlite (doi_database.db) database as a datastore, and will create this file and run the DDL as needed.
config.ini has detailed comments on initial settings. Most of this currently relies on unpaywall.org,
but downloaders are modular and could be written for any paid subscriptions that you have access to.
Downloaders have their own custom SQL tables and can have independent retry logic.

Development status:
As of 7/6/22: big rewrite prior to release; have only re-tested through step 2 (downloading)

Firefox downloading:
Some sites have enabled ddos protection. As a last resort, it is possible to have the citations_finder
launch a firefox browser, hit the URL in question with the actual browser, save the result, and import it.
This requires some configuration tweaking; on the mac (the only platform tested thus far), we use the
pyautogui module to simulate user keyboard input (command-s to save). For this to work, you 
must enable the application running citations_finder (e.g.: command, or pycharm) to do keyboard input.

WARNING WARNING WARNING:
This will ERASE the contents of firefox_save_directory. Recommended that you change the default firefox 
save directory to something specific while running in this mode.


TODO: pdf directory is flat; should with one directory per issn, at least, and possibly per year.
TODO: format this file to MD
TODO: archive.org downloader
TODO: Use proper logging and log levels
TODO: Get specimen count compare to pubs on a per instutiuion ratio
TODO: Get DOI metadata from datacite: https://support.datacite.org/docs/api-queries
TODO note known failure case - we don't always OCR 90 degree rotated tables
TODO parallelize the scan
TODO: are keywords available through crossref.org? scan them for scores
TODO: once we ID collections papers, calculate their citation impact
TODO: can google scholar do smarter searches for possible references?
TODO: web interface that supports uploading pdf/dois (bulk?)
TODO: ResearchGate or Academia.edu have many papers that have been uploaded by authors.
TODO: Impact factor for our references per crossref?
TODO: gather metrics from antweb

#  TODO: Scan doi repo for string, compare to google scholar
#  TODO: Scan microsoft academic for string, compare to google scholar
# TODO: Support adding PDFs from journals that lack DOIs. e.g.: Herpetological Conservation & Biology
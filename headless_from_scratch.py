from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import TimeoutException

import os
from datetime import datetime
from db_connection import DBConnection
from utils_mixin import Utils




#====================================================================================
#These two below are checking the most recent downlaod and renaming them to doi name .pdf
def get_latest_downloaded_file(directory_issn_year):
    # Get a list of all files in the specified download path
    list_of_files = os.listdir(directory_issn_year)
    # Use the max function to find the file with the latest creation time
    latest_file = max(list_of_files, key=lambda x: os.path.getctime(os.path.join(directory_issn_year, x)))
    print(latest_file)
    # Construct the full path to the latest file
    directory_issn_year_textname= os.path.join(directory_issn_year, latest_file)
    return directory_issn_year_textname,latest_file

def check_and_rename_file(directory_issn_year, doi):
    directory_issn_year_textname, latest_file = get_latest_downloaded_file(directory_issn_year)
    # Check if the file exists at the specified file path
    if os.path.exists(directory_issn_year_textname):

        # Construct the full path to the new file
        directory_issn_year_doiname = os.path.join(os.path.dirname(directory_issn_year_textname), 
                                                   Utils.get_filename_from_doi_string(doi))
        
        # Rename the existing file to the new file name
        os.rename(directory_issn_year_textname, directory_issn_year_doiname)
        
        # Print a success message
        print(f"File successfully downloaded and renamed to {doi}")
    else:
        # Print a message if the file does not exist
        print("Download unsuccessful. File not found.")

#===================================================================================

def headless_downlad(doi):
    options = Options()
    
    #creating directory in which pdfs will be stored
    directory_issn_year = os.path.join("/Users/Sophiaaa/Documents/CalAcademy/citations_finder/headlessdata", issn, str(published_date.year))
    if not os.path.exists(directory_issn_year):
        print(f"Creating new PDF directory: {directory_issn_year}")
        os.makedirs(directory_issn_year)
    

    #setting preferences
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", directory_issn_year)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf,application/x-pdf")
    #below line triggers brower.get to hang and timeout. Without it, headless function wouldnt work
    options.set_preference("pdfjs.disabled", True)
    options.add_argument("--headless")
    os.environ['MOZ_HEADLESS'] = '1'


    #Initializing browser
    browser = webdriver.Firefox(options=options)

    browser.set_page_load_timeout(10)

    try:
        try:
            #performs headless download
            browser.get(open_url)


        except TimeoutException as e:
            print(f"TimeoutException: {e}, ")
            print("Checking whether pdf has been downloaded")
        
        finally:
            #check whether file has been downloaded prior to time out, if so, rename it, other wise, make uncessful downlaod
            check_and_rename_file(directory_issn_year,doi)

    finally:
        browser.quit()

#===================================================================



doi_list = [
    "10.1002/ece3.8967",
    "10.1002/ece3.9137",
    "10.1002/ece3.9169",
    "10.1073/pnas.2023286118",
    "10.1080/14772000.2022.2084471",
    "10.1002/ar.24853",
    "10.1002/ar.24839",
    "10.1111/mec.16060",
    "10.1073/p"
    ]
DATETIME_FORMAT0 = "%Y-%m-%d %H:%M:%S.%f"
DATETIME_FORMAT1 = "%Y-%m-%d %H:%M:%S"

for doi in doi_list:
    sql = f"""
        SELECT 
            ud.most_recent_attempt, 
            ud.open_url, 
            ud.most_recent_firefox_failure,
            ud.error_code,
            ud.not_available,
            d.issn,
            d.published_date
        FROM 
            unpaywall_downloader AS ud
        JOIN
            dois AS d
        ON
            ud.doi = d.doi
        WHERE 
            ud.doi = '{doi}'
        """    
    results = DBConnection.execute_query(sql)

    if len(results) == 0:
        most_recent_attempt = None
    else:
        most_recent_attempt = datetime.strptime(results[0][0],DATETIME_FORMAT0)
        open_url = results[0][1]
        most_recent_firefox_failure = results[0][2]
        error_code = results[0][3]
        not_available = results[0][4]
        issn = results[0][5]
        published_date = datetime.strptime(results[0][6],DATETIME_FORMAT1)
        headless_downlad(doi)




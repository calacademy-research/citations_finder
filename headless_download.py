import selenium
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile

from selenium.webdriver.support.ui import WebDriverWait

import os
import platform
import time

class HeadlessDownload:
    web_driver_pathname = r'/Users/Sophiaaa/Documents/CalAcademy/citations_finder/citations_finder/bin/geckodriver'
    firefox_pathname = r'/Applications/Firefox.app/Contents/MacOS/firefox'

    def __init__(self, headless=True) -> None:
        """ Initializes a HeadlessDownload object.

        :param headless: Whether to run the browser in headless mode (default is False).
        :type headless: bool
        """        
        service = Service(HeadlessDownload.web_driver_pathname)
        options = Options()
        options.binary_location = HeadlessDownload.firefox_pathname
        options.headless = headless
        options.add_argument('--user-data-dir=/Applications/Firefox.app/Contents/MacOS/firefox')
        os.environ['MOZ_HEADLESS'] = '1'


        #below refer to https://www.browserstack.com/guide/download-file-using-selenium-python
        self.profile = webdriver.FirefoxProfile()
        self.profile.set_preference("browser.download.folderList", 2)
        self.profile.set_preference("browser.download.manager.showWhenStarting", False)
        #below directory will need to change
        self.profile.set_preference("browser.download.dir", "/Users/Sophiaaa/Documents/CalAcademy/citations_finder/headlessdata")
        self.profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream,application/pdf,application/x-pdf,application/vnd.pdf")


        self.profile.set_preference("pdfjs.disabled", True)
        self.profile.set_preference("pref.downloads.disable_button.edit_actions", True)
        self.profile.set_preference("browser.helperApps.neverAsk.openFile", "application/octet-stream,application/pdf,application/x-pdf,application/vnd.pdf")

        self.driver = webdriver.Firefox(service=service, options=options)
        self.driver.set_page_load_timeout(30)

    def about(self):
        """Prints information about the operating system, Firefox version, and Selenium version.
        """        
        print("OS:", platform.system())
        print("Firefox version:", "105.0.3")
        print("Selenium version:", selenium.__version())

    def get_page_contents(self):
        """Opens a webpage, activates a link, and retrieves the text content of the resulting page.

        :return: Text content of the webpage.
        :rtype: str
        """  
        try:      
            #self.driver.get("https://www.pnas.org/content/pnas/118/34/eiti3421118.full.pdf")
            self.driver.get("https://onlinelibrary.wiley.com/doi/pdfdirect/10.1002/ece3.9169")

        except NoSuchElementException:
            print("PDF link not found")

    
        time.sleep(10)
        self.driver.quit()

# create an instance of the class, print document page contents, and environment
page = HeadlessDownload()
page.get_page_contents()

import selenium
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import os
import platform

# Sample to send keys with selenium in headless mode
# Tested with the following environment
#   MacOS 13.5.2 (22G91)
#   Firefox version 118.0
#   Selenium version 4.13.0
#
class HeadlessDownload:
    web_driver_pathname = r'/Users/Sophiaaa/Documents/CalAcademy/citations_finder/citations_finder/bin/geckodriver'
    firefox_pathname = r'/Applications/Firefox.app/Contents/MacOS/firefox'

    def __init__(self, headless = True) -> None:
        """ Initializes a HeadlessDownload object.

        :param headless: Whether to run the browser in headless mode (default is False).
        :type headless: bool
        """        
        #os.environ["PATH"] += os.pathsep + 'c:/bin/geckodriver.exe'
        service = Service(HeadlessDownload.web_driver_pathname)
        options = Options()
        options.binary_location = HeadlessDownload.firefox_pathname
        options.headless = headless
        os.environ['MOZ_HEADLESS'] = '1' # sets an environment variable named MOZ_HEADLESS to the value '1'. In the context of Firefox and Selenium, setting MOZ_HEADLESS to '1' is used to enable headless mode for the Firefox browser.
        self.driver = webdriver.Firefox(service=service, options=options)

    def about(self):
        """Prints information about the operating system, Firefox version, and Selenium version.

        """        
        print("OS:",platform.system())
        print("Firefox version:", "105.0.3")
        print("Selenium version:", selenium.__version__)

    def get_page_contents(self):
        """Opens a webpage, activates a link, and retrieves the text content of the resulting page.

        :return: Text content of the webpage.
        :rtype: str
        """        
        self.driver.get("https://bioone.org/journals/lundellia/volume-23/issue-1/1097-993X-23.1.28/Rare-Specimens-Yield-DNA-to-Confirm-Additional-Members-of-Tribe/10.25224/1097-993X-23.1.28.pdf")
        # use XPath to find the link
        e = self.driver.find_element(By.XPATH, "//a[@href='/documentation']")
        # send key to activate link
        e.send_keys(Keys.ENTER)
        # Might need to wait for page to load but this page is fast
        pass
        # get text body from resulting page
        body = self.driver.find_element(By.TAG_NAME, "body")
        body_text = body.text
        self.driver.quit()
        return body_text

# create instance of class, print document page contents and environment
page = HeadlessDownload()
print(page.get_page_contents())
print(page.about())
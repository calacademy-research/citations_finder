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
#   Windows 11 
#   Firefox version 105.0.3
#   Selenium version 4.5.0
#
class DocumentationPage:
    web_driver_pathname = r'C:\bin\geckodriver.exe'
    firefox_pathname = r'C:\Program Files\Mozilla Firefox\firefox.exe'

    def __init__(self, headless = False) -> None:
        #os.environ["PATH"] += os.pathsep + 'c:/bin/geckodriver.exe'
        service = Service(DocumentationPage.web_driver_pathname)
        options = Options()
        options.binary_location = DocumentationPage.firefox_pathname
        options.headless = headless
        self.driver = webdriver.Firefox(service=service, options=options)

    def about(self):
        print("OS:",platform.system())
        print("Firefox version:", "105.0.3")
        print("Selenium version:", selenium.__version__)

    def get_page_contents(self):
        self.driver.get("http://selenium.dev")
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
page = DocumentationPage(headless = True)
print(page.get_page_contents())
print(page.about())
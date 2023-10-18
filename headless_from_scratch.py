from selenium import webdriver
from selenium.webdriver.firefox.options import Options

import os




options = Options()
options.set_preference("browser.download.folderList", 2)
options.set_preference("browser.download.manager.showWhenStarting", False)
options.set_preference("browser.download.dir", "/Users/Sophiaaa/Documents/CalAcademy/citations_finder/headlessdata")
options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf,application/x-pdf")
options.set_preference("pdfjs.disabled", True)


options.add_argument("--headless")
os.environ['MOZ_HEADLESS'] = '1'

browser = webdriver.Firefox(options=options)
browser.set_page_load_timeout(3)

#below line never stops running, even after successful download. Added timeout. Still need to figure out how to handle
browser.get("https://www.pnas.org/content/pnas/118/34/eiti3421118.full.pdf")


browser.quit()
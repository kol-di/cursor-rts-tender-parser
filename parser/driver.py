from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import time


WEBSITE_URL = r'https://www.rts-tender.ru/'


def init_driver():
    service = webdriver.ChromeService(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--ignore-urlfetcher-cert-requests')
    options.add_argument('--allow-insecure-localhost')
    options.add_argument('--ignore-certificate-errors-spki-list')
    options.accept_insecure_certs = True
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(WEBSITE_URL)
    driver.execute_script(r"Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    time.sleep(10)
    
    return driver
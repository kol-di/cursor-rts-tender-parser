from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
import time

WEBSITE_URL = r'https://www.rts-tender.ru/'


def init_driver():
    service = webdriver.ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.get(WEBSITE_URL)
    driver.execute_script(r"Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    time.sleep(6)
    with open('start_source.html', 'w+') as f:
        f.write(driver.page_source)
    time.sleep(10)
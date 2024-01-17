from selenium import webdriver
import multiprocessing as mp
import time


WEBSITE_URL = r'https://www.rts-tender.ru/'

DRIVER = None   # this variable is local to each subprocess


def init_driver(driver_path, headless=True):
    service = webdriver.ChromeService(driver_path)
    options = webdriver.ChromeOptions()

    # ignore ssl handshake
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--ignore-urlfetcher-cert-requests')
    options.add_argument('--allow-insecure-localhost')
    options.add_argument('--ignore-certificate-errors-spki-list')

    #disable popups
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')

    options.add_argument('--log-level=3')
    if headless:
        options.add_argument('--headless')
    
    options.accept_insecure_certs = True
    driver = webdriver.Chrome(service=service, options=options)
    # driver.set_page_load_timeout(10)
    driver.get(WEBSITE_URL)
    driver.execute_script(r"Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    time.sleep(10)
    
    global DRIVER
    DRIVER = driver

    driver_id = mp.current_process().pid
    print(f'Драйвер {driver_id} подключен')


def quit_driver():
    DRIVER.quit()
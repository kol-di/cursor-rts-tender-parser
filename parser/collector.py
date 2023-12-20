from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import re
import time

from .utils import xpath_soup


def close_popup(driver):
    popup_close_btn = driver.find_element(By.CLASS_NAME, 'consultation_modal').find_element(
        By.CLASS_NAME, 'modal-close'
    )
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(popup_close_btn)).click()



def next_page(driver, page_num):
    """
    Jumps to the next page
    return: True/False if was able to jump to the next page
    """
    pager_interact = driver.find_element(By.ID, 'pager')
    try:
        WebDriverWait(pager_interact, 2).until(EC.visibility_of_all_elements_located((By.TAG_NAME, "li")))
    except TimeoutException:    # no pages hence empty search result
        return False

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    li_pages = soup.find('ul', {'id': 'pager'}).find_all('li')
    for page in li_pages:
        try:
            next_link = page.find('a', {'class': 'page-link'})
            if next_link.get_text() == str(page_num):
                current_url = driver.current_url
                try:
                    WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_soup(next_link)))).click()
                except ElementClickInterceptedException:
                    close_popup(driver)
                    WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_soup(next_link)))).click()
                # only return when successfully redirected
                WebDriverWait(driver, 10).until(lambda driver: driver.current_url != current_url)
                return True
        except AttributeError:
            pass
    return False



def _parse_number(txt):
    return re.search(r"№?(\d+)", txt).group(1)


def collect_page_contents(driver, file):
    # card items dont seem to appear immidiately
    content_interact = WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.ID, 'content')))
    # content_interact = driver.find_element(By.ID, 'content')
    try:
        WebDriverWait(content_interact, 5).until(EC.visibility_of_all_elements_located((By.CLASS_NAME, "card-item")))
    except TimeoutException:    # if no card items then search result is empty
        return

    # parse html tree
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    content = soup.find('div', {'id': 'content'})
    for card in content.find_all('div', {'class': 'card-item'}):
        label = card.find('div', {'class': 'card-item__about'}).find('a').get_text()
        print(_parse_number(label), file=file)


def collect(driver, output_file):
    f = open(output_file, 'w')

    collect_page_contents(driver, f)
    next_page_numb = 2
    while next_page(driver, next_page_numb):
        collect_page_contents(driver, f)
        next_page_numb += 1

    f.close()
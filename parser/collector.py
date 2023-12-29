from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    ElementClickInterceptedException, 
    StaleElementReferenceException)
import re
import time
from tqdm import tqdm
from typing import Tuple, Callable

from .utils import xpath_soup, native_click


def filter_unique(path):
    if path.is_file():
        with open(path, 'r') as f:
            records = set([l.strip() for l in f.readlines()])
        with open(path, 'w') as f:
            for rec in records:
                f.write(f'{rec}\n')


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
                    el_click = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_soup(next_link))))
                    native_click(el_click, driver)
                except ElementClickInterceptedException:
                    close_popup(driver)
                    el_click = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_soup(next_link)))).click()
                    native_click(el_click, driver)
                # only return when successfully redirected
                try:
                    WebDriverWait(driver, 20).until(lambda driver: driver.current_url != current_url)
                except TimeoutException:
                    driver.refresh()
                    return next_page(driver, page_num)
                return True
        except AttributeError:
            pass

    return False



def _clean_label(txt):
    return re.search(r"№?(\d+)", txt).group(1)


def collect_page_contents(driver):
    collected = []

    # card items dont seem to appear immidiately
    content_interact = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.ID, 'content')))
    # content_interact = driver.find_element(By.ID, 'content')
    try:
        WebDriverWait(content_interact, 5).until(EC.visibility_of_all_elements_located((By.CLASS_NAME, "card-item")))
    except TimeoutException:    # if no card items then search result is empty
        return collected

    # parse html tree
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    content = soup.find('div', {'id': 'content'})
    for card in content.find_all('div', {'class': 'card-item'}):
        label = card.find('div', {'class': 'card-item__about'}).find('a').get_text()
        collected.append(_clean_label(label))

    return collected


def element_text_is_not_empty(locator: Tuple[str, str]) -> Callable:
    """An expectation for checking if the given text is not empty

    locator, text
    """

    def _predicate(driver):
        try:
            element_text = driver.find_element(*locator).text
            return bool(element_text)
        except StaleElementReferenceException:
            return False

    return _predicate


def progress_bar_len(driver, res_per_page=10):
    count_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "Notifications")))
    count_tab = WebDriverWait(count_btn, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "main-tabs__count")))
    WebDriverWait(count_tab, 10).until(element_text_is_not_empty((By.TAG_NAME, "span")))
    count_text = count_tab.find_element(By.TAG_NAME, "span").text
    count = int(''.join([c for c in count_text if c.isnumeric()]))

    return int(count / res_per_page)


def collect(driver, output_file=None, db_conn=None):

    with tqdm(total=progress_bar_len(driver)) as pbar:
        collected = []

        collected.extend(collect_page_contents(driver))
        next_page_numb = 2
        pbar.update(1)

        while next_page(driver, next_page_numb):
            collected.extend(collect_page_contents(driver))
            next_page_numb += 1
            pbar.update(1)

        # new_collected = db_conn.get_new_numbers(collected)
        # if new_collected:
        #     with open(output_file, 'a') as f:
        #         for num in new_collected:
        #             print(num, file=f)

    # print(f'Найдено {len(collected)}, из них {len(new_collected)} новых')
    # return len(new_collected)
    return collected


def output_collected(output_file, collected, db_conn):
    new_collected = db_conn.get_new_numbers(collected)
    if new_collected:
        with open(output_file, 'a') as f:
            for num in new_collected:
                print(num, file=f)
    
    print(f'Найдено {len(collected)}, из них {len(new_collected)} новых')
    len(new_collected)
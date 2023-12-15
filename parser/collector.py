from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
import re


def final_page():
    pass


def next_page(driver, page_num):
    """
    Jumps to the next page
    return: True/False if was able to jump to the next page
    """
    print('inside next_page')
    pager_interact = driver.find_element(By.ID, 'pager')
    WebDriverWait(pager_interact, 10).until(EC.visibility_of_all_elements_located((By.TAG_NAME, "li")))

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    li_pages = soup.find('ul', {'id': 'pager'}).find_all('li')
    print(soup.find('ul', {'id': 'pager'}))
    print(f'li_pages {li_pages}')
    for page in li_pages:
        print('found some pages')
        try:
            next_link = page.find('a', {'class': 'page-link'})
            print(f'found text {next_link.get_text()}')
            if page.find('a', {'class': 'page-link'}).get_text() == str(page_num):
                # next_link.click()
                WebDriverWait(page, 10).until(
                    EC.element_to_be_clickable((By.TAG_NAME, "a"))).click()
                return True
        except AttributeError:
            pass
    return False



def _parse_number(txt):
    return re.search(r"№?(\d+)", txt).group(1)


def collect_page_contents(driver):
    # card items dont seem to appear immidiately
    content_interact = driver.find_element(By.ID, 'content')
    WebDriverWait(content_interact, 10).until(EC.visibility_of_all_elements_located((By.CLASS_NAME, "card-item")))

    # parse html tree
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    content = soup.find('div', {'id': 'content'})
    for card in content.find_all('div', {'class': 'card-item'}):
        label = card.find('div', {'class': 'card-item__about'}).find('a').get_text()
        print(_parse_number(label))


def collect(driver):
    next_page_numb = 2
    while next_page(driver, next_page_numb):
        
        collect_page_contents(driver)
        # move_to_next_page(driver)
        next_page_numb += 1
        # break
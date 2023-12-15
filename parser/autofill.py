from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
import dataclasses
from typing import List
from enum import Enum
import itertools
import time
from datetime import date, timedelta
import logging


class WidgetType(Enum):
    GRID = 'grid'
    LIST = 'list'
    DATE_RANGE = 'date_range'
    NESTED_LIST = 'nested_list'


@dataclass(frozen=True)
class SearchEntry:
    name: str
    options: List[str]
    type: WidgetType


@dataclass
class SerachParams():
    quick_settings: SearchEntry = field(
        default=SearchEntry(
            'быстрые настройки', 
            ['Искать в файлах', 'Точное соответствие', 'Исключить совместные закупки', 'Только МСП / СМП'], 
            WidgetType.GRID)
    )
    trade_platforms: SearchEntry = field(
        default=SearchEntry(
            'торговая площадка', 
            ['РТС-тендер'], 
            WidgetType.LIST)
    )
    publish_date: SearchEntry = field(
        default=SearchEntry(
            'фильтры по датам', 
            ['Подача Заявок'], 
            WidgetType.DATE_RANGE
        )
    )
    okpd: SearchEntry = field(
        default=SearchEntry(
            'окпд2', 
            ['10.86.10.191', '10.89.99.000'], 
            WidgetType.NESTED_LIST
        )
    )


def fill(driver):
    search_params = SerachParams()

    fill_search_params(
        driver, 
        r"https://www.rts-tender.ru/poisk/search?keywords=&isFilter=1", 
        search_params)
    while True: 
        time.sleep(20)


def xpath_soup(element):
    """
    Generate xpath of soup element
    :param element: bs4 text or node
    :return: xpath as string
    """
    components = []
    child = element if element.name else element.parent
    for parent in child.parents:  # type: bs4.element.Tag
        siblings = parent.find_all(child.name, recursive=False)
        components.append(
            child.name if 1 == len(siblings) else '%s[%d]' % (
                child.name,
                next(i for i, s in enumerate(siblings, 1) if s is child)
                )
            )
        child = parent
    components.reverse()
    return '/%s' % '/'.join(components)


def _nested_list_dfs(ul, code, is_root=False):
    # use xpath to only iterate top level descendants 
    lis = WebDriverWait(ul, 10).until(EC.visibility_of_all_elements_located((By.XPATH, './li')))
    for li in lis:
        # uncollapse list if collapsed
        if 'settings-tree--show' not in li.get_attribute('class'):
            try:
                # no button on the leaf level
                btn = li.find_element(By.TAG_NAME, 'button')
                btn.click()
            except:
                pass

        if not is_root:
            label = li.find_element(By.TAG_NAME, 'label').find_element(By.TAG_NAME, 'b').text
            if code.startswith(label) or ((len(label) == len(code)) and code.startswith(label[:-1])):
                if code == label:
                    return li.find_element(By.TAG_NAME, 'label')
                ul = li.find_element(By.TAG_NAME, 'ul')
                return _nested_list_dfs(ul, code)
        else:
            ul = li.find_element(By.TAG_NAME, 'ul')
            root_match = _nested_list_dfs(ul, code)
            if root_match is not None:
                return root_match


def fill_parameter(driver, el, search_entry: SearchEntry):
    match search_entry.type:
        case WidgetType.GRID | WidgetType.LIST:
            # grid rows contain checkbox options. Usually there is only one, but can be more
            grid_rows = el.find_all("div", {"class", "grid-row"})
            for grid_row in grid_rows:
                for grid_val in grid_row.find_all("div", {"class", "grid-column-4-1"}):
                    grid_val_label = grid_val.find("label").get_text()

                    # match hardcoded fields with actutal checkboxes
                    for match_option in search_entry.options:
                        if str.lower(match_option) in str.lower(grid_val_label):
                            checkbox = grid_val.find("input")
                            checkbox_interact = driver.find_element(By.XPATH, xpath_soup(checkbox))

                            # check checkbox if it is not selected but is in our list
                            if not checkbox_interact.is_selected():
                                checkbox_label = grid_val.find("label")
                                checkbox_label_interact = driver.find_element(
                                    By.XPATH, xpath_soup(checkbox_label))
                                checkbox_label_interact.click()
        case WidgetType.DATE_RANGE:
            grid_row = el.find("div", {"class", "grid-row"})
            for grid_col in grid_row.find_all("div", {"class", "grid-column-2"}):
                col_title_text = grid_col.find("div", {"class", "form-group__title"}).get_text()
                for match_option in search_entry.options:
                    if str.lower(match_option) in str.lower(col_title_text):
                        date_interval = [date.today() - timedelta(days=1), date.today()]
                        datepicker_cells = grid_col.find_all("input", {"class": "datepicker"})
                        for datepicker, date_val in zip(datepicker_cells, date_interval):
                            datepicker_interact = driver.find_element(By.XPATH, xpath_soup(datepicker))
                            datepicker_interact.send_keys(date_val.strftime("%d-%m-%Y"))
                            # close blocking react widget
                            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        case WidgetType.NESTED_LIST:
            ul = driver.find_element(By.XPATH, xpath_soup(el))
            for code in search_entry.options:
                checkbox = _nested_list_dfs(ul, code, is_root=True)
                checkbox.click()
            





def show_more(driver):
    """Click show more in all search options"""
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    filter_el = soup.find("div", {"class": "modal-settings-filter__main"})
    filter_options = filter_el.find_all("div", {"class": "modal-settings-section"})
    for filter_option in filter_options:
        for msr in filter_option.find_all("div", {"class": "modal-settings-row"}):
            if (msr_a := msr.find("a")) is not None:
                if 'показать еще' in str.lower(msr.get_text()):
                    msr_a_interact = driver.find_element(By.XPATH, xpath_soup(msr_a))
                    msr_a_interact.click()



def uncollapse_options(driver):
    """Make collapsed options visible"""
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    filter_el = soup.find("div", {"class": "modal-settings-filter__main"})
    filter_options = filter_el.find_all("div", {"class": "modal-settings-section"})
    for filter_option in filter_options:

        # this field might be collapsed
        filter_title_el = filter_option.find(
            "div", {"class": "filter-title"}).find(
                "div", {"class": "title-collapse title-collapse--more"}
        )
        if filter_title_el is None:
            filter_title_el = filter_option.find(
                "div", {"class": "filter-title"}).find(
                    "div", {"class": "title-collapse title-collapse--less"}
            )
            # click to uncollapse
            driver.find_element(By.XPATH, xpath_soup(filter_title_el)).click()


def remove_selection(driver):
    """Remove checkbox selection in all options"""
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    filter_el = soup.find("div", {"class": "modal-settings-filter__main"})
    filter_options = filter_el.find_all("div", {"class": "modal-settings-section"})
    for filter_option in filter_options:
        for msr in filter_option.find_all("div", {"class": "modal-settings-row filter-helpers"}):
            if msr_a_all := msr.find_all("a"):
                for msr_a in msr_a_all:
                    if 'снять всё' in str.lower(msr_a.get_text()):
                        msr_a_interact = driver.find_element(By.XPATH, xpath_soup(msr_a))
                        msr_a_interact.click()


def get_modal_settings_row(filter_option, search_entry: SearchEntry):
    match search_entry.type:
        case WidgetType.GRID | WidgetType.DATE_RANGE:
            modal_settings_rows = filter_option.find_all("div", {"class", "modal-settings-row"})
            for msr in modal_settings_rows:
                if "filter-helpers" not in msr.get("class"):
                    return msr       
        case WidgetType.LIST:
            modal_settings_rows = filter_option.find_all("div", {"class", "modal-settings-row"})
            for msr in modal_settings_rows:
                if (msr_a := msr.find("a")) is not None:
                    # LIST type widgets also contain checkbox grid, but with extra buttons
                    if 'свернуть' in str.lower(msr_a.get_text()):
                        # nested msr in LIST type
                        return msr.find("div", {"class", "modal-settings-row"})
        # for NESTED_LIST there's no msr but we return the deepest definitve structure
        case WidgetType.NESTED_LIST:
            return filter_option.find("div", {"class": "settings-tree"}).find("ul")
        

def click_search(driver):
    search_btn = driver.find_element(
        By.CLASS_NAME, 'bottomCenterSearch').find_element(
            By.TAG_NAME, 'button'
        )
    search_btn.click()


def fill_search_params(driver, search_url, search_params):
    driver.get(search_url)
    # the below functions need to be called separately to recreate soup each time
    uncollapse_options(driver)
    show_more(driver)
    remove_selection(driver)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    filter_el = soup.find("div", {"class": "modal-settings-filter__main"})
    filter_options = filter_el.find_all("div", {"class": "modal-settings-section"})
    
    for filter_option in filter_options:
        filter_title_el = filter_option.find(
            "div", {"class": "filter-title"}).find(
                "div", {"class": "title-collapse title-collapse--more"})
        try:
            filter_title_el_text = filter_title_el.get_text()
        except AttributeError:
            logging.error(f'DOM object {filter_option.find("div", {"class": "filter-title"})} has no attribute <div> with classes "title-collapse title-collapse--more"')

        # look for match of input field title with our options
        for search_field in dataclasses.fields(search_params):
            search_entry = getattr(search_params, search_field.name)
            search_entry_name = getattr(search_entry, 'name')

            # if html text matches our hardcoded field title
            if str.lower(search_entry_name) in str.lower(filter_title_el_text):
                modal_settings_row = get_modal_settings_row(filter_option, search_entry)
                fill_parameter(
                    driver, 
                    modal_settings_row, 
                    search_entry)
                
    click_search(driver)

    
    
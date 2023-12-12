from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
import dataclasses
from typing import List
from enum import Enum
import itertools
import time


class WidgetType(Enum):
    GRID = 'grid'
    LIST = 'list'


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


def xpath_soup(element):
    """
    Generate xpath of soup element
    :param element: bs4 text or node
    :return: xpath as string
    """
    components = []
    child = element if element.name else element.parent
    for parent in child.parents:
        """
        @type parent: bs4.element.Tag
        """
        previous = itertools.islice(parent.children, 0, parent.contents.index(child))
        xpath_tag = child.name
        xpath_index = sum(1 for i in previous if i.name == xpath_tag) + 1
        components.append(xpath_tag if xpath_index == 1 else '%s[%d]' % (xpath_tag, xpath_index))
        child = parent
    components.reverse()
    return '/%s' % '/'.join(components)


def run_search(driver):
    search_params = SerachParams()

    fill_search_params(driver, r"https://www.rts-tender.ru/poisk/search?keywords=&isFilter=1")
    time.sleep(20)


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


def get_modal_settings_row(driver, filter_option, search_entry: SearchEntry):
    match search_entry.type:
        case WidgetType.GRID:
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


def fill_search_params(driver, search_url):
    search_params = SerachParams()
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

        # look for match of input field title with our options
        for search_field in dataclasses.fields(search_params):
            search_entry = getattr(search_params, search_field.name)
            search_entry_name = getattr(search_entry, 'name')

            # if html text matches our hardcoded field title
            if str.lower(search_entry_name) in str.lower(filter_title_el.get_text()):
                modal_settings_row = get_modal_settings_row(driver, filter_option, search_entry)
                fill_parameter(
                    driver, 
                    modal_settings_row, 
                    search_entry)

    
    
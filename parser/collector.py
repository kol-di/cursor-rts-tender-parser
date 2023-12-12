from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
import dataclasses
from typing import List
from enum import Enum
import itertools


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


def fill_parameter(driver, el, search_entry: SearchEntry):
    match search_entry.type:
        case WidgetType.GRID:
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
        
        # case WidgetType.LIST:





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


def get_modal_settings_row(filter_option, search_entry: SearchEntry):
    match search_entry.type:
        case WidgetType.GRID:
            modal_settings_rows = filter_option.find_all("div", {"class", "modal-settings-row"})
            for msr in modal_settings_rows:
                if "filter-helpers" not in msr.get("class"):
                    modal_settings_row = msr
                    break        
        case WidgetType.LIST:
            modal_settings_rows = filter_option.find_all("div", {"class", "modal-settings-row"})
            for msr in modal_settings_rows:
                if msr.find("div", {"class", "form-control-search"}) is not None:
                    modal_settings_row = msr
                    break
    
    return modal_settings_row


def remove_selection(driver, filter_option):
    msr_helper = filter_option.find("div", {"class", "modal-settings-row filter-helpers"})
    a_tags = msr_helper.find_all("a")
    for a_tag in a_tags:
        if str.lower(a_tag.get_text()) in 'снять всё':
            a_tag_interact = driver.find_element(By.XPATH, xpath_soup(a_tag))
            a_tag_interact.click()
            break


def fill_search_params(driver, search_url):
    search_params = SerachParams()
    driver.get(search_url)
    uncollapse_options(driver)

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
                remove_selection(driver, filter_option)
                modal_settings_row = get_modal_settings_row(filter_option, search_entry)
                fill_parameter(
                    driver, 
                    modal_settings_row, 
                    search_entry)

    
    
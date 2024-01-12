from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
import dataclasses
from typing import List, Optional, Union
from enum import Enum
import itertools
import time
from datetime import date, timedelta
import logging
import sys
import chardet
from pathlib import Path
from concurrent import futures

from .utils import xpath_soup, native_click, get_pid


FILTER_URL = r"https://www.rts-tender.ru/poisk/search?keywords=&isFilter=1"

class WidgetType(Enum):
    GRID = 'grid'
    LIST = 'list'
    DATE_RANGE = 'date_range'
    NESTED_LIST = 'nested_list'
    TEXT = 'text'


class SearchEntry:
    def __init__(self, name=None, type=None, options=None, extra=None):
        self._name: str = name
        self._type: WidgetType = type
        self._options: List[str] = options
        self._extra: Optional[Union[int, str]] = extra

    @property
    def name(self): return self._name
    
    @name.setter
    def name(self, val):
        self._name = val

    @property
    def type(self): return self._type

    @type.setter
    def type(self, val):
        self._type = val

    @property
    def options(self): return self._options

    @options.setter
    def options(self, val):
        self._options = val

    @property
    def extra(self): return self._extra

    @extra.setter
    def extra(self, val):
        self._extra = val


class SearchParams:
    def __init__(self):
        self.quick_settings: SearchEntry = SearchEntry(
            name='быстрые настройки', 
            type=WidgetType.GRID, 
            options=['Искать в файлах', 'Точное соответствие']
        )
        self.trade_platforms: SearchEntry = SearchEntry(
            name='торговая площадка', 
            type=WidgetType.LIST, 
            options=[]
        )
        self.regulation: SearchEntry = SearchEntry(
            name='правило проведения', 
            type=WidgetType.GRID, 
            options=['44-фз']
        )
        self.publish_date: SearchEntry = SearchEntry(
            name='фильтры по датам', 
            type=WidgetType.DATE_RANGE, 
            options=['Опубликовано'], 
            extra=1
        )
        self.okpd: SearchEntry = SearchEntry(
            name='окпд2', 
            type=WidgetType.NESTED_LIST, 
            options=[], 
            extra='tree'
        )
        self.keyword: SearchEntry = SearchEntry(
            name=None, 
            type=WidgetType.TEXT, 
            options=[]
        )


class FillError(Exception):
    pass


def get_input_data(input):
    if isinstance(input, Path):
        with open(input, 'rb') as f:
            dec = chardet.detect(f.read())
        with open(input, encoding=dec['encoding']) as f:
            input_data = []
            for line in f:
                input_data.append(line.strip())
    if isinstance(input, str):
        input_data = [input]
    
    return input_data


def fill(driver, input_data, mode, search_interval, kw_policy=None, okdp_policy=None):
    if mode is None:
        print("No mode provided")
        # logging.error("No mode provided")
        sys.exit()
    if input_data is None or not input_data:
        return None

    search_url = FILTER_URL

    search_params = SearchParams()
    # fill new search params from input
    search_params.publish_date.extra = search_interval

    if mode == 'kw' and kw_policy is not None:
        search_params.keyword.options = input_data
        if kw_policy == 'all':
            search_params.quick_settings.options = ['Искать в файлах', 'Точное соответствие']
        if kw_policy == 'any':
            search_params.quick_settings.options = ['Искать в файлах']
    if mode == 'okpd' and okdp_policy is not None: 
        search_params.okpd.options = input_data
        if okdp_policy == 'tree':
            search_params.okpd.extra = 'tree'
        if okdp_policy == 'text':
            search_params.okpd.extra = 'text'

    failure = fill_search_params(
        driver, 
        search_url,
        search_params)
    
    # wait redirect
    # WebDriverWait(driver, 10).until(lambda driver: driver.current_url != search_url)

    try:
        WebDriverWait(driver, 10).until(lambda driver: driver.current_url != search_url)
    except TimeoutException:
        print(f'Драйвер {get_pid()}: первышен лимит времени при переходе на страницу результатов. Перезапускаю заполнение параметров')
        driver.refresh()
        return fill(driver, input_data, mode, search_interval, kw_policy, okdp_policy)

    return failure


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

        try:
            if not is_root:
                label = li.find_element(By.TAG_NAME, 'label').find_element(By.TAG_NAME, 'b').text
                if code.startswith(label) or ((len(label) == len(code)) and code.startswith(label[:-1]) and label.endswith('0')):
                    if code == label:
                        return li.find_element(By.TAG_NAME, 'label')
                    ul = WebDriverWait(li, 5).until(EC.presence_of_element_located((By.TAG_NAME, 'ul')))
                    if (ret := _nested_list_dfs(ul, code)) is not None:
                        return ret
            else:
                ul = WebDriverWait(li, 5).until(EC.presence_of_element_located((By.TAG_NAME, 'ul')))
                root_match = _nested_list_dfs(ul, code)
                if root_match is not None:
                    return root_match
        except TimeoutException as e:
            pass
            # logging.error(f"Process {get_pid()}: Exception when unrolling nested list for code {code} occured", exc_info=True)


def _code_searchbox_input(code, searchbox, driver):
    # clear previous
    clear_btn = WebDriverWait(searchbox, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, "cstm-button-clear"))
    )
    native_click(clear_btn, driver)

    # senf code to input field
    input = WebDriverWait(searchbox, 10).until(
        EC.element_to_be_clickable((By.TAG_NAME, "input"))
    )
    input.send_keys(code)

    # wait for autocomplete to appear
    autocomp = WebDriverWait(searchbox, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, "cstm-search__autocomplite"))
    )
    suggest = WebDriverWait(autocomp, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, "cstm-search__suggest"))
    )

    # discover option with needed code
    WebDriverWait(suggest, 20).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "b"), code)
    )
    native_click(suggest, driver)


def fill_parameter(driver, el, search_entry: SearchEntry):
    if el is None:
        print(f"Драйвер {get_pid()}: не удалось заполнить параметр {search_entry.name}")
        return
        # logging.warning(f"No parameter to fill for type {search_entry.type.name}")

    # return options which cant be filled
    failed = []

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
                        date_interval = [date.today() - timedelta(days=search_entry.extra), date.today()]
                        datepicker_cells = grid_col.find_all("input", {"class": "datepicker"})
                        for datepicker, date_val in zip(datepicker_cells, date_interval):
                            datepicker_interact = driver.find_element(By.XPATH, xpath_soup(datepicker))
                            datepicker_interact.send_keys(date_val.strftime("%d-%m-%Y"))
                            # close blocking react widget
                            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        case WidgetType.NESTED_LIST:
            if search_entry.extra == 'tree':
                # element for checkbox input
                code_tree = el.find("div", {"class": "settings-tree"}).find("ul")
                ul = driver.find_element(By.XPATH, xpath_soup(code_tree))

                for code in search_entry.options:
                    checkbox = _nested_list_dfs(ul, code, is_root=True)
                    if checkbox is not None:
                        print(f'Найден код {code} в дереве')
                        checkbox.click()
                    else:
                        print(f'Не удалось найти код {code} в дереве')
                        failed.append(code)

            if search_entry.extra == 'text':
                searchbox = el.find("div", {"class": "form-control-search"})
                searchbox_interact = driver.find_element(By.XPATH, xpath_soup(searchbox))
                code = search_entry.options
                assert isinstance(code, str)
                _code_searchbox_input(code, searchbox_interact, driver)
                print(f'Найден код {code} в строке поиска')

        case WidgetType.TEXT:
            input_interact = driver.find_element(By.XPATH, xpath_soup(el))
            for option in search_entry.options:    
                input_interact.send_keys(option)
                webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()

    return failed


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
    try:
        WebDriverWait(driver, 2).until(EC.visibility_of_all_elements_located((By.CLASS_NAME, 'title-collapse--more')))
        WebDriverWait(driver, 2).until(EC.visibility_of_all_elements_located((By.CLASS_NAME, 'title-collapse--less')))
    except TimeoutException:
        print(f'Драйвер {get_pid()}: не удалось найти все опции фильтра')
        # uncollapse_options(driver)
        raise FillError
    
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
            filter_title_interact = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xpath_soup(filter_title_el)))
            )
            native_click(filter_title_interact, driver)

            # make sure element is uncollapsed
            WebDriverWait(filter_title_interact, 10).until(
                EC.text_to_be_present_in_element_attribute(
                    (By.XPATH, "."), 
                    "class", 
                    "title-collapse--more"
                )
            )


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
                        if (msr_res := msr.find("div", {"class", "modal-settings-row"})) is not None:
                            return msr_res
                        # else:
                        #     print('No modal settings row for type LIST')
                        #     raise Exception
        # for NESTED_LIST there's no msr but we return the deepest definitve structure
        case WidgetType.NESTED_LIST:
            return filter_option
        case _:
            pass
        
    print(f'Драйвер {get_pid()}: no modal settings row for {search_entry.name}')
        

def click_search(driver):
    search_btn = driver.find_element(
        By.CLASS_NAME, 'bottomCenterSearch').find_element(
            By.TAG_NAME, 'button'
        )
    search_btn.click()


def fill_search_params(driver, search_url, search_params):
    # try:
    #     driver.get(search_url)
    #     # refresh if filter page load is stuck
    #     WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element_attribute(
    #         (By.CLASS_NAME, 'consultation_modal'), 'style', 'display: none'))
    # except TimeoutException:
    #     print(f'Драйвер {get_pid()}: превышен лимит времени при переходе на страницу фильтров. Перезапускаю заполнение параметров')
    #     driver.refresh()
    #     return fill_search_params(driver, search_url, search_params)

    # print(f'driver {get_pid()} redirected to serach_url')
    # the below functions need to be called separately to recreate soup each time

    def __fill_prep(driver, search_url):
        driver.get(search_url)
        WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element_attribute(
            (By.CLASS_NAME, 'consultation_modal'), 'style', 'display: none'))

        uncollapse_options(driver)
        show_more(driver)
        remove_selection(driver)    

    with futures.ThreadPoolExecutor() as executor:    
        future = executor.submit(__fill_prep, driver, search_url)
        try:
            future.result(timeout=20)
        except (futures.TimeoutError, TimeoutException, ElementClickInterceptedException, FillError):
            print(f'Драйвер {get_pid()}: не удалось подготовить фильтры для заполнения. Перезапускаю заполнение')
            driver.refresh()
            return fill_search_params(driver, search_url, search_params)

    # print(f'driver {get_pid()} is ready to fill')

    # store fill success/failure results
    fill_failure = {}

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
            pass
            # print(f'DOM object {filter_option.find("div", {"class": "filter-title"})} has no attribute <div> with classes "title-collapse title-collapse--more"')
            # logging.error(f'DOM object {filter_option.find("div", {"class": "filter-title"})} has no attribute <div> with classes "title-collapse title-collapse--more"')

        # look for match of input field title with our options
        for search_entry in vars(search_params).values():
            # for text we have separate logic
            if search_entry.type is WidgetType.TEXT:
                continue
            search_entry_name = search_entry.name

            # if html text matches our hardcoded field title
            if str.lower(search_entry_name) in str.lower(filter_title_el_text):
                modal_settings_row = get_modal_settings_row(filter_option, search_entry)
                fill_res = fill_parameter(
                    driver, 
                    modal_settings_row, 
                    search_entry)
                fill_failure[search_entry.type] = fill_res
                
    # separate fill logic for text
    input = soup.find("div", {"class": "modal-settings-search"}).find(
        "div", {"class": "main-search__controls"}).find(
            "input"
        )
    keyword_search_params = search_params.keyword
    fill_res = fill_parameter(driver, input, keyword_search_params)
    fill_failure[search_entry.type] = fill_res
                
    click_search(driver)

    return fill_failure

    
    
import sys
import argparse
from parser.driver import init_driver
from parser.autofill import fill
from parser.collector import collect
import configparser
import time
import logging
from datetime import datetime


CONFIG_PATH = '.\conf.ini'


def get_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', required=False, choices=['okdp', 'kw'], 
                    help='Режим поиска по кодам/по фразам. Если не задан, будет искать по всему')
    ap.add_argument('--kw-policy', required=False, choices=['all', 'any'], 
                    help='Искать по любым/по всем фразам из списка. Только для поиска по словам')
    ap.add_argument('--search-interval-days', required=False, type=int, 
                    help='Интервал поиска в днях. Конец интервала равен сегодняшней дате')
    return ap.parse_args() 


def get_conf(conf_path):
    conf = configparser.ConfigParser()
    conf.read(conf_path)
    return conf


def init_logging(log_path, level=logging.WARNING):
    log_path = fr'{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}_{log_path}'
    logging.basicConfig(
        filename=log_path, 
        format='%(asctime)s %(message)s', 
        encoding='utf-8', 
        level=level
    )


def main(argv):
    ap = get_args(argv)
    conf = get_conf(CONFIG_PATH)
    init_logging(conf['logging'].get('log_path'))

    # different launch optins for different argv combinations
    if (mode := getattr(ap, 'mode', None)) is not None:
        driver = init_driver()

        if mode == 'kw':
            input_folder = conf['data'].get('input_folder_keyword')
        if mode == 'okdp':
            input_folder = conf['data'].get('input_folder_okpd')

        search_interval = conf['runtime'].get('search_interval_days')
        if getattr(ap, 'search_interval_days', None) is not None:
            search_interval = ap.search_interval_days

        if mode == 'kw':
            kw_policy = conf['runtime'].get('kw_search_policy')
            if getattr(ap, 'kw_policy', None) is not None:
                kw_policy = ap.kw_policy

        fill(driver, input_folder, mode, search_interval, kw_policy)
        collect(driver, conf['data'].get('output_folder'), mode)

    while True: 
        time.sleep(20)


if __name__ == '__main__':
    main(sys.argv[1:])
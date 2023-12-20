import sys
import argparse
from parser.driver import init_driver
from parser.autofill import fill
from parser.collector import collect
import configparser
import time
import logging
from datetime import datetime
from pathlib import Path


CONFIG_PATH = '.\conf.ini'


def get_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', required=False, choices=['okpd', 'kw'], 
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


def _in_out_file_gen(input_folder, output_folder, out_prefix=''):
    """
    Iterates files in input folder. Creates corresponding output files
    yield: (input file path, output file path)
    """
    dir_path = Path(input_folder)
    for in_file_path in dir_path.iterdir():
        with open(in_file_path, 'r') as f:
            if f.readable():
                out_file_path = Path(output_folder) / f'{out_prefix}{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}.txt'
                # create the new file
                with open(out_file_path, 'w') as _:
                    pass
                yield (in_file_path, out_file_path)
            else:
                logging.warning(f"Can't read file {in_file_path}")



def main(argv):
    ap = get_args(argv)
    conf = get_conf(CONFIG_PATH)
    init_logging(conf['logging'].get('log_path'))

    # get common launch settings
    mode = getattr(ap, 'mode', None)
    search_interval = conf['runtime'].getint('search_interval_days')
    if getattr(ap, 'search_interval_days', None) is not None:
        search_interval = ap.search_interval_days
    output_folder = conf['data'].get('output_folder')

    # launch in different modes with different params. None mode means launch everything
    if mode is None or mode == 'kw':
        input_folder = conf['data'].get('input_folder_keyword')
        kw_policy = conf['runtime'].get('kw_search_policy')
        if getattr(ap, 'kw_policy', None) is not None:
            kw_policy = ap.kw_policy

        driver = init_driver()
        del_files = []
        for (input_file, output_file) in _in_out_file_gen(input_folder, output_folder, 'по_словам_'):
            fill(driver, input_file, mode, search_interval, kw_policy)
            collect(driver, output_file)
            driver.close()
            del_files.append(input_file)
        for file in del_files:
            file.unlink()
        driver.quit()

    if mode is None or mode == 'okpd':
        input_folder = conf['data'].get('input_folder_okpd')

        driver = init_driver()
        del_files = []
        for (input_file, output_file) in _in_out_file_gen(input_folder, output_folder, 'по_окпд_'):
            fill(driver, input_file, mode, search_interval)
            collect(driver, output_file) 
            del_files.append(input_file)
        for file in del_files:
            file.unlink()
        driver.quit()


if __name__ == '__main__':
    main(sys.argv[1:])
import sys
import argparse
import configparser
import time
import logging
from datetime import datetime
from pathlib import Path
import multiprocessing as mp
from functools import partial
from itertools import chain

from parser.driver import init_driver, quit_driver
from parser.autofill import fill, get_input_data, WidgetType
from parser.collector import collect, filter_unique, output_collected
from parser.utils import get_pid, chunk_into_n
from db.connection import DBConnection


CONFIG_PATH = '.\conf.ini'


def get_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', required=False, choices=['okpd', 'kw'], 
                    help='Режим поиска по кодам/по фразам. Если не задан, будет искать по всему')
    ap.add_argument('--kw-policy', required=False, choices=['all', 'any'], 
                    help='Искать по любым/по всем фразам из списка. Только для поиска по словам')
    ap.add_argument('--search-interval-days', required=False, type=int, 
                    help='Интервал поиска в днях. Конец интервала равен сегодняшней дате')
    ap.add_argument('--headless', required=False, choices=['y', 'n'], default='y',
                    help='Запуск без интерфейса')
    ap.add_argument('--num-proc', required=False, type=int, 
                    help='Количество запускаемых процессов')
    return ap.parse_args() 


def get_conf(conf_path):
    conf = configparser.ConfigParser()
    conf.read(conf_path)
    return conf


def init_logging(log_path, level=logging.WARNING):
    log_dir = Path(log_path)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / fr'{datetime.now().strftime("%d_%m_%Y_%H_%M_%S")}.log'
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
    in_folder_path = Path(input_folder)
    out_folder_path = Path(output_folder)
    out_folder_path.mkdir(parents=True, exist_ok=True)

    for in_file_path in in_folder_path.iterdir():
        with open(in_file_path, 'r') as f:
            if f.readable():
                out_file_path = out_folder_path / f'{out_prefix}{datetime.now().strftime("%d_%m_%Y_%H_%M_%S")}.txt'
                yield (in_file_path, out_file_path)
            else:
                logging.warning(f"Can't read file {in_file_path}")


def mp_kw_job(input_data, search_interval, kw_policy):
    print(f'Драйвер {get_pid()}: поиск по словам {input_data}')

    # fight mp map chunksize heuristic
    if len(input_data) and isinstance(input_data[0], list):
        input_data = list(chain(*input_data))

    # driver object is global to each subprocess
    from parser.driver import DRIVER

    collected = []
    fill_res = fill(DRIVER, input_data, 'kw', search_interval, kw_policy=kw_policy)
    if fill_res is not None:
        collected = collect(DRIVER)

    print(f'Драйвер {get_pid()}: собрано {len(collected)}')

    return collected


def mp_okpd_job(input_data, search_interval):
    print(f'Драйвер {get_pid()}: поиск по кодам {input_data}')

    # fight mp map chunksize heuristic
    if len(input_data) and isinstance(input_data[0], list):
        input_data = list(chain(*input_data))

    # driver object is global to each subprocess
    from parser.driver import DRIVER

    collected = []
    fill_res = fill(DRIVER, input_data, 'okpd', search_interval, okdp_policy='tree')
    if fill_res is not None:
        # if all codes were not filled then search uses all codes, so we skip
        if len(fill_res[WidgetType.NESTED_LIST]) < len(input_data):
            collected.extend(collect(DRIVER))
        if fill_res[WidgetType.NESTED_LIST]:
            for code in fill_res[WidgetType.NESTED_LIST]:
                fill(DRIVER, code, 'okpd', search_interval, okdp_policy='text')
                collected.extend(collect(DRIVER))
    
    print(f'Драйвер {get_pid()}: собрано {len(collected)}')

    return collected


def main(argv):
    ap = get_args(argv)
    conf = get_conf(CONFIG_PATH)
    init_logging(conf['logging'].get('log_path'))
    db_conn = DBConnection(**conf['database'])
    print('Установлено соединение с БД')

    # get common launch settings
    mode = getattr(ap, 'mode', None)
    num_proc = conf['runtime'].getint('num_proc')
    if getattr(ap, 'num_proc', None) is not None:
        num_proc = ap.num_proc 
    search_interval = conf['runtime'].getint('search_interval_days')
    if getattr(ap, 'search_interval_days', None) is not None:
        search_interval = ap.search_interval_days
    output_folder = conf['data'].get('output_folder')

    with mp.Manager() as manager:
        # spawn multiple drivers
        with manager.Pool(processes=num_proc) as pool:
            try:
                # create subprocesses with distinct drivers
                driver_init_res = []
                for _ in range(num_proc):
                    driver_init_res.append(pool.apply_async(init_driver, kwds={'headless': ap.headless=='y'}))
                for res in driver_init_res:
                    res.get()

                # launch in different modes with different params. None mode means launch everything
                if mode is None or mode == 'kw':
                    input_folder = conf['data'].get('input_folder_keyword')
                    kw_policy = conf['runtime'].get('kw_search_policy')
                    if getattr(ap, 'kw_policy', None) is not None:
                        kw_policy = ap.kw_policy

                    del_files = []
                    for (input_file, output_file) in _in_out_file_gen(input_folder, output_folder, 'по_словам_'):
                        print(f'Поиск по ключевым словам из файла {input_file}')
                        input_data = get_input_data(input_file)

                        mp_kw_job_partial = partial(mp_kw_job, search_interval=search_interval, kw_policy=kw_policy)
                        chunks = chunk_into_n(input_data, num_proc)
                        collected = pool.map(mp_kw_job_partial, chunks, 1)
                        output_collected(output_file, list(chain(*collected)), db_conn)
                        filter_unique(output_file)

                        del_files.append(input_file)
                    for file in del_files:
                        file.unlink()
                    

                if mode is None or mode == 'okpd':
                    input_folder = conf['data'].get('input_folder_okpd')

                    del_files = []
                    for (input_file, output_file) in _in_out_file_gen(input_folder, output_folder, 'по_окпд_'):
                        print(f'Поиск по кодам ОКПД из файла {input_file}')
                        input_data = get_input_data(input_file)

                        okpd_kw_job_partial = partial(mp_okpd_job, search_interval=search_interval)
                        chunks = chunk_into_n(input_data, num_proc)
                        collected = pool.map(okpd_kw_job_partial, chunks, 1)
                        output_collected(output_file, list(chain(*collected)), db_conn)
                        filter_unique(output_file)

                        del_files.append(input_file)
                    for file in del_files:
                        file.unlink()
                        
            finally:
                # quit all drivers
                driver_quit_res = []
                for _ in range(num_proc):
                    driver_quit_res.append(pool.apply_async(quit_driver))
                for res in driver_quit_res:
                    res.get()

                pool.terminate()
                pool.join()

    db_conn.close()


if __name__ == '__main__':
    main(sys.argv[1:])
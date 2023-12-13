import sys
import argparse
from parser.driver import init_driver
from parser.collector import run_search
import time
import logging


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('-m', '--mode', required=False)
    ap.add_argument('-f', '--file', required=(('--mode' in argv) or ('-m' in argv)))
    ap.parse_args()

    logging.basicConfig(
        filename='runtime.log', 
        format='%(asctime)s %(message)s', 
        encoding='utf-8', 
        level=logging.WARNING
    )

    driver = init_driver()
    run_search(driver)

    time.sleep(10)


if __name__ == '__main__':
    main(sys.argv[1:])
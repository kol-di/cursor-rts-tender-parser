import sys
import argparse
from parser.driver import init_driver
from parser.collector import run_search
import time


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('-m', '--mode', required=False)
    ap.add_argument('-f', '--file', required=(('--mode' in argv) or ('-m' in argv)))
    ap.parse_args()
    driver = init_driver()
    run_search(driver)

    time.sleep(10)


if __name__ == '__main__':
    main(sys.argv[1:])
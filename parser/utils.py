from math import floor
import multiprocessing as mp


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


def native_click(el, driver):
    driver.execute_script("arguments[0].click();", el)


def chunk_into_n(lst, n):
    min_size = floor(len(lst) / n)
    rem = len(lst) - min_size * n
    result = []
    prev_idx = 0
    for _ in range(n):
        next_idx = prev_idx + min_size
        if rem > 0:
            next_idx += 1
            rem -= 1
        result.append(lst[prev_idx:next_idx])
        prev_idx = next_idx

    return result

def get_pid():
    proc = mp.current_process()
    return proc.pid
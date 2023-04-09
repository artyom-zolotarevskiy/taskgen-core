import os
import glob
from taskgen.config import config, __SETTINGS_FOLDER__
from taskgen.functions import get_omega_folders

def get_choise_prob(folder):
    '''
    Функция выводит вероятность выбора данной папки в ее директории.
    '''
    omega_folders = get_omega_folders(os.path.dirname(folder))
    return omega_folders.count(folder) / len(omega_folders)


def count_tasks(folder=config.get('GENERAL', 'bank_folder')):
    '''
    Считает количество задач, находящихся в данной папке.
    Уровень вложенности папок не ограничен.
    '''
    return len(glob.glob(os.path.join(folder, '**', '*.ipynb'), recursive=True))


def count_tex_substitutions(folder=config.get('GENERAL', 'bank_folder')):
    '''
    Считает количество tex файлов подстановок, находящихся в данной папке.
    Уровень вложенности папок не ограничен.
    '''
    return len(glob.glob(os.path.join(folder, '**', 'substitutions', 'tex', 'substitution_*.tex'), recursive=True))


def count_html_substitutions(folder=config.get('GENERAL', 'bank_folder')):
    '''
    Считает количество html файлов подстановок, находящихся в данной папке.
    Уровень вложенности папок не ограничен.
    '''
    return len(glob.glob(os.path.join(folder, '**', 'substitutions', 'html', 'substitution_*_problem.html'),
                         recursive=True))

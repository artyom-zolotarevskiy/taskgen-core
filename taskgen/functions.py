import os.path
import glob
import logging
import math
import shutil
import json
from taskgen.config import config, __SETTINGS_FOLDER__

def get_parametrizator_path(folder, logging_enabled=True):
    """
    Выдает путь к файлу параметризации (*.ipynb) задачи, который находится в переданной папке.
    """
    lst = glob.glob(os.path.join(folder, '*.ipynb'))
    if len(lst) == 1:
        path = lst[0]
        return path
    elif len(lst) > 0:
        path = lst[0]
        if logging_enabled:
            logging.warning(
                'В папке "' + folder + '" лежит несколько файлов с расширением .ipynb. \n'
                                       'В качестве файла параметризации выбран "' + path + '".')
        return path
    else:
        if logging_enabled:
            logging.error(
                'Файл параметризации не найден в папке: "' + folder + '". \n'
                                                                      'Это должен быть файл с расширением .ipynb. Имя может быть любое.')
        return False


def get_template_path(folder):
    """
    Выдает путь к файлу шаблону (*.tex) задачи, который находится в переданной папке.
    """
    lst = glob.glob(os.path.join(folder, '*.tex'))
    if len(lst) == 1:
        path = lst[0]
        return path
    elif len(lst) > 0:
        path = lst[0]
        logging.warning(
            'В папке "' + folder + '" лежит несколько файлов с расширением .tex. \n'
                                   'В качестве файла шаблона выбран "' + path + '".')
        return path
        if os.path.basename(folder) != 'data':
            logging.error(
                'Файл шаблона не найден в папке: "' + folder + '". \n'
                                                               'Это должен быть файл с расширением .tex. Имя может быть любое.')
        return False

def get_omega_folders(folder):
    '''
    Выводит список папок, умножив кол-во вхождений каждой папки на коэффициент, указанный в ее названии.
    '''
    omega_folders = []
    # разделителем может быть любой знак, в данном случае проверяем x английское и х русское
    delimiter_list = ['x', 'х']
    for path in sorted(glob.glob(os.path.join(folder, '**'))):
        factor = 1
        for delimiter in delimiter_list:
            arr = path.split(delimiter)
            if len(arr) == 1:
                continue
            try:
                factor = math.ceil(float(arr[-1]))
                break
            except:
                continue
        omega_folders += [path] * factor
    return omega_folders


def remove_substitutions(folder=config.get('GENERAL', 'bank_folder')):
    '''
    Удаляет папки "substitutions", "data" и "tmp" для каждой задачи.
    '''
    tasks_folders_list = map(lambda path: os.path.dirname(path),
                             glob.glob(os.path.join(folder, '**', '*.ipynb'), recursive=True))
    for task_folder in tasks_folders_list:
        if os.path.exists(os.path.join(task_folder, 'substitutions')):
            shutil.rmtree(os.path.join(task_folder, 'substitutions'))
        if os.path.exists(os.path.join(task_folder, 'data')):
            shutil.rmtree(os.path.join(task_folder, 'data'))
        if os.path.exists(os.path.join(task_folder, 'tmp')):
            shutil.rmtree(os.path.join(task_folder, 'tmp'))

    logging.info('Папки "substitutions", "data" и "tmp" удалены для всех задач!')


def copy_taskgen_sty(folder=os.getcwd(), force=False, logging_enabled=True):
    '''
    Копирует стилевой файл "taskgen.sty" из папки настроек в указанную (по умолчанию в текущую).
    Если в указанной папке уже есть "taskgen.sty", то он его перезапишет в том случае,
    если дата изменения "taskgen.sty" в папке настроек более поздняя.

    :param folder: путь к папке, в которую нужно скопировать стилевой файл
    :param force: нужно ли перезаписывать стилевой файл, если он уже есть в указанной директории и у него более
    поздняя дата редактирования, чем у файла из папки настроек
    '''
    if os.path.basename(folder) == 'data':
        return None
    dst_taskgen_sty_path = os.path.join(folder, 'taskgen.sty')
    primary_taskgen_sty_path = os.path.join(__SETTINGS_FOLDER__, 'taskgen.sty')
    if force or not os.path.exists(dst_taskgen_sty_path) or \
            os.path.getmtime(primary_taskgen_sty_path) > os.path.getmtime(dst_taskgen_sty_path):
        shutil.copyfile(primary_taskgen_sty_path, dst_taskgen_sty_path)
        if logging_enabled:
            logging.info(
                'Cтилевой файл TeX "taskgen.sty" из папки настроек "' + __SETTINGS_FOLDER__ + '" скопирован в папку "' +
                folder + '"')
        return True
    else:
        if logging_enabled:
            logging.info(
                'Cтилевой файл TeX "taskgen.sty" уже есть в указанной директории! Используйте функцию с параметром ' +
                '"force=True" для перезаписи файла!')
        return False


def copy_taskgen_4ht(folder=os.getcwd(), force=False, logging_enabled=True):
    '''
    Копирует файл конфигурации make4ht "taskgen.4ht" из папки настроек в указанную (по умолчанию в текущую).
    Если в указанной папке уже есть "taskgen.4ht", то он его перезапишет в том случае,
    если дата изменения "taskgen.4ht" в папке настроек более поздняя.

    :param folder: путь к папке, в которую нужно скопировать файл конфигурации make4ht
    :param force: нужно ли перезаписывать файл конфигурации, если он уже есть в указанной директории и у него более
    поздняя дата редактирования, чем у файла из папки настроек
    '''
    if os.path.basename(folder) == 'data':
        return None
    dst_taskgen_4ht_path = os.path.join(folder, 'taskgen.4ht')
    primary_taskgen_4ht_path = os.path.join(__SETTINGS_FOLDER__, 'taskgen.4ht')
    if force or not os.path.exists(dst_taskgen_4ht_path) or \
            os.path.getmtime(primary_taskgen_4ht_path) > os.path.getmtime(dst_taskgen_4ht_path):
        shutil.copyfile(primary_taskgen_4ht_path, dst_taskgen_4ht_path)
        if logging_enabled:
            logging.info(
                'Файл конфигурации make4ht "taskgen.4ht" из папки настроек "' + __SETTINGS_FOLDER__ +
                '" скопирован в папку "' + folder + '"')
        return True
    else:
        if logging_enabled:
            logging.info(
                'Файл конфигурации make4ht "taskgen.4ht" уже есть в указанной директории! Используйте функцию с параметром ' +
                '"force=True" для перезаписи файла!')
        return False


def copy_template_files(folder=os.getcwd(), extensions=['js', 'css', 'png'], force=False):
    '''
    Копирует файлы с данными расширениями из папки шаблона в указанную (по умолчанию в текущую).
    Если в указанной папке уже есть какой-либо файл, то он его перезапишет
    в том случае, если дата изменения в папке шаблона более поздняя.

    :param folder: путь к папке, в которую нужно скопировать файлы из папки шаблона
    :param force: нужно ли перезаписывать файл, если он уже есть в указанной директории
    и у него более поздняя дата редактирования, чем у файла из папки шаблона
    '''
    if os.path.basename(folder) == 'data':
        return None
    for extension in extensions:
        # получаем список файлов в папке шаблона
        template_folder = os.path.join(os.path.dirname(__SETTINGS_FOLDER__),
                                       config.get('GENERAL', 'templates_folder'), 'html')
        files = glob.glob(os.path.join(template_folder, '*.' + extension))
        # копируем файлы в указанную папку
        for primary_path in files:
            dst_path = os.path.join(folder, os.path.basename(primary_path))
            if force or not os.path.exists(dst_path) or \
                    os.path.getmtime(primary_path) > os.path.getmtime(dst_path):
                shutil.copyfile(primary_path, dst_path)

def replace_files(substitution_path, string, variant_number, problem_number, copy_file=True):
    '''
    Заменяет в переданной строке все названия файлов и пути к изображениям, использованным в данной подстановке.
    Также копирует датасеты и изображения в папку с вариантами.

    :param substitution_path: путь к tex файлу подстановки
    :param string: строка, в которой нужно произвести замену
    :param variant_number: номер варианта
    :param problem_number: номер вопроса
    :param copy_file: нужно ли копировать файлы
    :return: измененная строка
    '''
    # получаем названия файлов датасетов для данной подстановки
    # из файла "data/data.json" задачи
    # путь к папке задачи
    task_folder = os.path.dirname(os.path.dirname(os.path.dirname(substitution_path)))
    # номер подстановки
    substitution_index = int(
        os.path.basename(
            os.path.splitext(substitution_path)[0]
        ).replace('substitution_', '')
    ) - 1
    with open(os.path.join(task_folder, 'data', 'data.json'), 'r', encoding='utf-8') as file:
        task_data = json.load(file)
    substitution_data = task_data[substitution_index]

    file_cnt = 1
    for variable_data in substitution_data.values():
        if type(variable_data) is list and variable_data[0] == 'DataSet':
            new_file_name = f'ds.{variant_number}.{problem_number}.{file_cnt}{os.path.splitext(variable_data[1])[1]}'
            # заменяем названия файлов датасетов
            string = string.replace(
                os.path.basename(variable_data[1]),
                new_file_name
            )
            # копируем файлы датасетов с нужным названием
            if copy_file:
                src_fpath = os.path.join(task_folder, 'data', os.path.basename(variable_data[1]))
                dest_fpath = os.path.join(os.getcwd(), 'results', 'datasets', new_file_name)
                os.makedirs(os.path.dirname(dest_fpath), exist_ok=True)
                shutil.copy(src_fpath, dest_fpath)
            file_cnt += 1
    file_cnt = 1

    for variable_data in substitution_data.values():
        if type(variable_data) is list and variable_data[0] == 'Image':
            new_file_name = f'{variant_number}.{problem_number}.{file_cnt}'
            # заменяем пути к файлам изображений
            string = string.replace(
                os.path.basename(variable_data[1]),
                new_file_name + os.path.splitext(variable_data[1])[1]
            )
            string = string.replace(
                os.path.splitext(os.path.basename(variable_data[1]))[0] + '-.png',
                new_file_name + '-.png'
            )
            # копируем изображения с нужным названием
            if copy_file:
                src_fpath = os.path.join(task_folder, 'data', os.path.basename(variable_data[1]))
                dest_fpath = os.path.join(
                    os.getcwd(),
                    'results',
                    'tex',
                    new_file_name + os.path.splitext(variable_data[1])[1]
                )
                os.makedirs(os.path.dirname(dest_fpath), exist_ok=True)
                shutil.copy(src_fpath, dest_fpath)

                src_fpath = os.path.join(
                    task_folder,
                    'substitutions',
                    'html',
                    os.path.splitext(os.path.basename(variable_data[1]))[0] + '-.png'
                )
                dest_fpath = os.path.join(
                    os.getcwd(),
                    'results',
                    'html',
                    new_file_name + '-.png'
                )
                os.makedirs(os.path.dirname(dest_fpath), exist_ok=True)
                shutil.copy(src_fpath, dest_fpath)

            file_cnt += 1

    return string

def getFilePath(ext: str):
    '''
    Возвращает генератор (итерируемый объект) полных путей для сохранения файлов.
    '''
    cnt = 1
    while True:
        if os.path.basename(os.getcwd()) == 'data':
            yield os.path.join(os.getcwd(), str(cnt) + '.' + ext)
        else:
            directory = os.path.join(os.getcwd(), 'tmp')
            os.makedirs(directory, exist_ok=True)
            yield os.path.join(directory, str(cnt) + '.' + ext)
        cnt += 1

def round_n(x: float, n: int = 0) -> str:
    '''округление до n знаков после запятой для печати в TeX'''
    fmt = '{:.' + str(n) + 'f}'
    return fmt.format(x).replace('.', ',\!')
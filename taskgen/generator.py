import os
import glob
from pylatexenc.latexwalker import LatexWalker, LatexEnvironmentNode, LatexMacroNode, LatexGroupNode
import random
import subprocess as subp
from .html2pdf import html2pdf
import shlex
import shutil
from bs4 import BeautifulSoup
from datetime import datetime
import numpy as np
from tabulate import tabulate
import configparser
import json
import math
from taskgen.html2pdf import *
import logging
from multiprocessing import Pool
from IPython.display import HTML
import re
import binascii


def find_settings_folder(initial_path=os.getcwd()):
    '''
    Данная функция ищет папку "settings" в родительских папках относительно переданной до 5 уровней вложенности вверх.
    :param initial_path: начальная папка для поиска (по умолчанию - активная директория исполняемого файла)
    '''
    settings_folder = initial_path
    flag = False
    for i in range(6):
        directory_files = glob.glob(os.path.join(settings_folder, '*'))
        if len(list(filter(lambda path: os.path.basename(path) == 'settings', directory_files))) > 0:
            flag = True
            settings_folder = os.path.join(settings_folder, 'settings')
            break
        else:
            settings_folder = os.path.dirname(settings_folder)
    if flag:
        return settings_folder
    logging.error('Не удалось найти папку с настройками!')
    return False


__SETTINGS_FOLDER__ = find_settings_folder()

config = configparser.ConfigParser()
config['GENERAL'] = {
    # Название функции, которая возвращает словарь (ассоциативный массив) названий
    # подставляемых переменных и их соответствующие значения для новой параметризации
    'parameterizer_function_name': 'GET',

    # Количество потоков для выполнения параметризации
    'parameterizer_threads_count': '10',

    # Количество потоков для выполнения конвертации из TeX в HTML
    'converter_threads_count': '10',

    # Путь к банку задач
    'bank_folder': os.path.join(os.getcwd(), 'bank'),

    # Путь к папке с шаблонами
    'templates_folder': os.path.join(os.getcwd(), 'templates', 'default')
}
config.read(os.path.join(__SETTINGS_FOLDER__, 'config.ini'))


def gen_table(array, replace_tabular=True):
    '''
    Генерация таблицы latex на основе списка.
    :param array:
    :param replace_tabular:
    '''
    # n - кол-во строк, m - кол-во столбцов
    n, m = np.array(array).shape
    latex_table = tabulate(array, tablefmt='latex_raw')
    needle = latex_table[15:15 + m + 2]
    latex_table = latex_table.replace(needle, '{' + '|c' * (m + 1) + ('|' if replace_tabular else '') + '}').replace(
        r'\\', r'\\\hline', n - 1)
    if replace_tabular:
        latex_table = latex_table.replace('tabular', 'array')
    return latex_table


def latex_subs(from_file, to_file, params):
    '''
    Выполнить подстановку переменных в файл.
    '''
    # читаем файл
    with open(from_file, 'r', encoding='utf-8') as file:
        src = file.read()
    # заменяем переменные
    for key in params.keys():
        subs_value = str(params[key])
        if 'begin{array}' in subs_value:
            subs_value = '$' + subs_value + '$'
        src = src.replace('\subs{' + key + '}', subs_value)
    # сохраняем файл
    with open(to_file, 'w', encoding='utf-8') as file:
        file.write(src)


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


def gen_subs_data(task_folder, n):
    '''
    Генерирует данные для создания файлов с подстановками. Для этого в папке задачи в подпапке "data" ({task}/data)
    запускает ноутбук параметризации задачи и выполняет функцию генерации переменных для подстановки заданное число раз.
    В результате создается "data.json" файл, содержащий список словарей с переменными подстановками, а также
    в этой папке появляются динамически генерируемые файлы, такие как изображения, csv, xlsx, ..., если такая логика
    заложена в ноутбуке параметризации.
    '''
    # находим файл ноутбука
    path = get_parametrizator_path(task_folder)
    if not path:
        return False

    # читаем файл ноутбука
    with open(path, 'r', encoding='utf-8') as file:
        # распознаем json cтруктуру документа
        ipynb_src = json.load(file)

    # выбираем ячейки с исполняемым кодом
    cells = list(filter(lambda cell: cell['cell_type'] == 'code', ipynb_src['cells']))

    # объединяем строки в один исполняемый файл
    parametrizer_script = '\n'.join([''.join(cell['source']) for cell in cells])

    # создаем директорию для хранения подстановочных данных
    data_directory = os.path.join(task_folder, 'data')
    if os.path.exists(data_directory):
        shutil.rmtree(data_directory)
    os.makedirs(data_directory)

    # добавляем код, запукающий функцию GET нужное количество раз
    # и сохранящий папаметризацию в json
    parametrizer_script += '\n\nimport json\n'
    parametrizer_script += 'parametrizer_result = []\n'
    parametrizer_script += f"for i in range({n}):\n\tparametrizer_result.append({config.get('GENERAL', 'parameterizer_function_name')}())\n"
    parametrizer_script += "with open('data.json', 'w', encoding='utf-8') as file:\n\tjson.dump(parametrizer_result, file)\n"

    # сохраням код параметризации в отдельный .py файл
    with open(os.path.join(data_directory, 'parametrizator.py'), 'w', encoding='utf-8') as file:
        file.write(parametrizer_script + '\n')

    initial_path = os.getcwd()
    # переходим в папку для создания данных параметризации
    os.chdir(data_directory)
    # запускаем интерпретатор python и выполняем код ноутбука
    os.system('python parametrizator.py')
    # возвращаемся в исходную директорию
    os.chdir(initial_path)

    # проверяем наличие data.json файла
    if os.path.exists(os.path.join(data_directory, 'data.json')):
        logging.info('"' + task_folder + '" данные для подстановки в шаблон созданы')
    else:
        logging.error('"' + task_folder + '" не удалось сгенерировать данные для подстановки в шаблон!')


def get_tex_body(file):
    '''
    Возвращает содержимое TeX файла, т.е. все, что расположено между "'\begin{document}'" и "\end{document}".
    '''
    # cтрока для поиска начала теховского документа
    start_str = r'\begin{document}'
    # строка для поиска конца теховского документа
    end_str = r'\end{document}'
    with open(file, 'r', encoding='utf-8') as file:
        src = file.read()
        return src[src.find(start_str) + len(start_str):src.find(end_str)]


def merge_tex(files_list, header='taskgen', use_template=False):
    '''
    Объединяет переданный список TeX файлов в 1 файл.
    Возвращает исходный код объединенного файла.
    '''
    merged_file = r'\documentclass[11pt]{article}' + '\n'
    merged_file += r'\usepackage' + ('[not_use_template]' if not use_template else '') + '{' + header + '}' + '\n'
    merged_file += r'\begin{document}' + '\n'
    for path in files_list:
        merged_file += get_tex_body(path) + '\n'
    merged_file += r'\end{document}'
    return merged_file


def gen_data(n=1, folder=config.get('GENERAL', 'bank_folder'), multiprocessing=True):
    '''
    Запускает функцию "gen_subs_data" в многопоточном режиме для всех задач в указанной папке.
    '''
    lst = list(map(lambda ipynb_file: (os.path.dirname(ipynb_file), n), glob.glob(
        os.path.join(folder, '**', '*.ipynb'), recursive=True)))
    if multiprocessing:
        with Pool(int(config.get('GENERAL', 'parameterizer_threads_count'))) as p:
            p.starmap(gen_subs_data, lst)
    else:
        for param in lst:
            (task_folder, n) = param
            gen_subs_data(task_folder, n)

    logging.info('Функция генерации подстановочных данных завершила свою работу!')


def gen_subs(n=1, folder=config.get('GENERAL', 'bank_folder')):
    '''
    Создает заданное число подстановок каждой задачи в указанной папке.
    Данные для подстановок должны быть заранее сгенерированы посредством функции "gen_data".
    '''
    for ipynb_file in glob.glob(os.path.join(folder, '**', '*.ipynb'), recursive=True):
        task_folder = os.path.dirname(ipynb_file)
        # создаем директорию для хранения файлов подстановок
        substitutions_directory = os.path.join(task_folder, 'substitutions', 'tex')
        if os.path.exists(substitutions_directory):
            shutil.rmtree(substitutions_directory)
        os.makedirs(substitutions_directory)
        html_subs_folder = os.path.join(os.path.dirname(substitutions_directory), 'html');
        if os.path.exists(html_subs_folder):
            shutil.rmtree(html_subs_folder)
        # копируем taskgen.sty из настроек в данную директорию
        copy_taskgen_sty(folder=substitutions_directory, logging_enabled=False)
        # копируем taskgen.4ht из настроек в данную директорию
        copy_taskgen_sty(folder=substitutions_directory, logging_enabled=False)
        # читаем файл с данными для подстановок
        with open(os.path.join(task_folder, 'data', 'data.json'), 'r', encoding='utf-8') as file:
            data = json.load(file)
        # находим файл шаблона в папке задачи
        template_path = get_template_path(task_folder)
        if not template_path:
            return False
        # создаем подстановки
        for i in range(len(data)):
            # подставляем значения
            latex_subs(from_file=template_path,
                       to_file=os.path.join(substitutions_directory, f'substitution_{i + 1}.tex'), params=data[i])
        # список всех файлов с подстановками
        subs_files_list = glob.glob(os.path.join(substitutions_directory, 'substitution_*.tex'))
        merged_latex_file = merge_tex(subs_files_list)
        # сохраняем объединенный файл подстановок
        with open(os.path.join(substitutions_directory, 'substitutions_merged.tex'), 'w', encoding='utf-8') as file:
            file.write(merged_latex_file)
        logging.info(os.path.dirname(ipynb_file) + '" TeX файлы с подстановками созданы')
    logging.info('Генерация TeX файлов с подстановками завершена!')


def gen_bank(n=1, folder=config.get('GENERAL', 'bank_folder'), multiprocessing=True):
    '''
    Cоздает n подстановок для каждой задачи из папки folder.

    Сначала создаются файлы подстановок с названием в формате "substitution_i.tex".
    Они лежат каждый в папке со своей задачей в подпапке substitutions/tex.
    В той же папке лежит объединенный файл "substitutions_merged.tex".

    Затем tex файлы подстановок конвертируются в html. Конвертация происходит оптимизированным способом.
    Сначала конвертируется за 1 проход объединенный файл "substitutions_merged.tex".
    В подпапке "substitutions/html" появляется файл "substitutions_merged.html", который можно просматривать в браузере.
    После этого полученный файл разрезается на составляющие его задачи. В той же подпапке появляются по 2 файла
    для каждой задачи: "substitution_i_problem.html", "substitution_i_solution.html". Это чистый html для условия и
    решения. Он не содержит скрипты mathjax, поэтому не предполагается его просмотр через браузер. Это системные файлы,
    на основе которых потом будут собираться варианты.

    :param n: кол-во создаваемых подстановок для каждой задачи
    :param folder: папка, для задач которой будут генерироваться подстановки

    Результатом работы являются файлы подстановок в TeX, HTML и Moodle XML форматах.
    '''
    folder = os.path.abspath(folder)
    # параметризуем задачи, получаем параметры для подстановок
    gen_data(n, folder, multiprocessing)
    # подставляем параметры в tex шаблон
    gen_subs(n, folder)
    # конвертируем в html оптимизированным способом
    tex_substitutions2html_optimized(folder)


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


def get_choise_prob(folder):
    '''
    Функция выводит вероятность выбора данной папки в ее директории.
    '''
    omega_folders = get_omega_folders(os.path.dirname(folder))
    return omega_folders.count(folder) / len(omega_folders)


def save_structure(structure, filename):
    '''
    Сохраняет структуру вариантов в папке результатов.
    '''
    results_directory = os.path.join(os.getcwd(), 'results')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)

    dst_json_file = os.path.join(results_directory, filename + '.json')
    with open(dst_json_file, 'w', encoding='utf-8') as file:
        json.dump(structure, file)

    dst_txt_file = os.path.join(results_directory, filename + '.txt')
    txt_file_src = ''
    for variant_number, subs_lst in structure.items():
        txt_file_src += 'Вариант № ' + str(variant_number) + ':\n\t'
        txt_file_src += '\n\t'.join([str(i + 1) + '. ' + path for i, path in enumerate(subs_lst)]) + '\n\n'
    with open(dst_txt_file, 'w', encoding='utf-8') as file:
        file.write(txt_file_src)

    logging.info('Структура билетов cохранена!')


def make_variants_structure(folder=config.get('GENERAL', 'bank_folder'), size=1, start=1):
    '''
    Создает структуру вариантов, т.е. определяет из каких файлов подстановок будет состоять каждый вариант.

    Кол-во задач в варианте то же, что и кол-во папок в переданной директории folder.
    Порядок задач в варианте зависит от лексикографического порядка папок.

    Т.к. уровень вложенности папок не ограничен, генератор спускается вниз до тех пор, пока не обнаружит в директории
    файл *.ipynb, при этом папка на каждом уровне выбирается случайным образом с учетом весов, указанных в названии.
    После чего, дойдя до папки задачи, случайным образом выбирается подстановка.

    :param folder: Папка, в которой лежат задачи с подстановками.
    :param size: Количество создаваемых вариантов.
    :param start: Начало нумерации вариантов.
    :return: Машинное и человекочетаемое представления структуры вариантов.
    '''
    # генерируем варианты
    variants = {}
    for variant_number in range(start, start + size):
        logging.info('Создаем структуру билета № ' + str(variant_number) + '...')
        # проверяем наличие файла параметризации в директории
        is_task_folder = get_parametrizator_path(folder, logging_enabled=False) is not False
        if is_task_folder:
            # случайным образом выбираем подстановку
            substitutions_list = glob.glob(os.path.join(folder, 'substitutions', 'tex', 'substitution_*.tex'))
            substitution_file = random.choice(substitutions_list)
            # сохраняем выбор
            variants.update({variant_number: variants.get(variant_number, []) + [substitution_file]})
        else:
            # обходим каждый вопрос
            for question_folder in sorted(glob.glob(os.path.join(folder, '*'))):
                flag = True
                current_folder = question_folder
                while flag:
                    # проверяем наличие файла параметризации в директории
                    is_task_folder = get_parametrizator_path(current_folder, logging_enabled=False) is not False
                    if is_task_folder:
                        # случайным образом выбираем подстановку
                        substitutions_list = glob.glob(
                            os.path.join(current_folder, 'substitutions', 'tex', 'substitution_*.tex'))
                        substitution_file = random.choice(substitutions_list)
                        # сохраняем выбор
                        variants.update({variant_number: variants.get(variant_number, []) + [substitution_file]})
                        flag = False
                    else:
                        # случайным образом выбираем папку:
                        omega_folders = get_omega_folders(current_folder)
                        if len(omega_folders) == 0:
                            logging.warning('Директория "' + question_folder + '" не содержит папок!')
                            flag = False
                            continue
                        current_folder = random.choice(omega_folders)

    # сохраняем структуру в папке результатов
    save_structure(structure=variants, filename='structure')

    return variants


def make_tex_variant(variant_number, structure, print_bilet_number=True, prefix='variant-', another_bilet_title=''):
    '''
    На основе переданной структуры задач создает файл варианта в формате TeX
    :param variant_number: Номер варианта.
    :param structure: Список путей к файлам подстановок задач в формате TeX
    '''
    logging.info('Создаем билет № ' + str(variant_number) + ' в TeX формате...')
    # тело билета
    variant_src = r'\documentclass[11pt]{article}' + '\n'
    variant_src += r'\usepackage{taskgen}' + '\n'
    variant_src += r'\begin{document}' + '\n\n'
    if len(another_bilet_title) > 0:
        variant_src += r'\printbilettitle{' + another_bilet_title + '}\n'
    elif print_bilet_number:
        variant_src += r'\printbilettitle{Билет № ' + str(variant_number) + '}\n'
    # обходим каждый вопрос
    for substitution_file in structure:
        # добавляем задачу в тело билета
        substitution_body = get_tex_body(substitution_file)
        variant_src += substitution_body + '\n'
    variant_src += r'\end{document}'
    # сохраняем билет
    results_directory = os.path.join(os.getcwd(), 'results', 'tex')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)
    with open(os.path.join(results_directory, f'{prefix}{str(variant_number)}.tex'), 'w', encoding='utf-8') as file:
        file.write(variant_src)

    # копируем taskgen.sty из настроек в данную директорию
    copy_taskgen_sty(folder=results_directory, logging_enabled=False)
    # копируем taskgen.4ht из настроек в данную директорию
    copy_taskgen_4ht(folder=results_directory, logging_enabled=False)

    logging.info('Билет № ' + str(variant_number) + ' в TeX формате создан!')


def make_html_variant(variant_number, structure, with_solution=True):
    '''
    На основе переданной структуры задач создает файл варианта в формате HTML
    :param variant_number: Номер варианта.
    :param structure: Список путей к файлам подстановок задач в формате TeX
    '''
    logging.info('Создаем билет № ' + str(variant_number) +
                 ' в HTML формате' +
                 (' с решением' if with_solution else ' без решения') +
                 '...')

    # берем файл общего шаблона html файла с подключением стилей и скриптов
    template_folder = os.path.join(config.get('GENERAL', 'templates_folder'), 'html')
    general_template_file = os.path.join(template_folder, 'template.html')
    with open(general_template_file, 'r', encoding='utf-8') as file:
        variant = file.read()

    mathjaxcommands_file = os.path.join(__SETTINGS_FOLDER__, 'mathjaxcommands.tex')
    with open(mathjaxcommands_file, 'r', encoding='utf-8') as file:
        mathjaxcommands = file.read()
    variant = variant.replace('${mathjaxcommands}', mathjaxcommands)

    # берем файл шаблона варианта
    variant_template_file = os.path.join(template_folder, 'variant.html')
    with open(variant_template_file, 'r', encoding='utf-8') as file:
        variant = variant.replace('${body}', file.read())

    # подставляем номер билета
    variant = variant.replace('${variant_number}', str(variant_number))

    # формируем содержимое билета
    # берем шаблон задачи
    task_template_file = os.path.join(template_folder, 'task.html')
    with open(task_template_file, 'r', encoding='utf-8') as file:
        task_template = file.read()

    problem_template_file = os.path.join(template_folder, 'problem.html')
    with open(problem_template_file, 'r', encoding='utf-8') as file:
        task_template = task_template.replace('${problem}', file.read())

    # берем шаблон решения
    if with_solution:
        solution_template_file = os.path.join(template_folder, 'solution.html')
        with open(solution_template_file, 'r', encoding='utf-8') as file:
            task_template = task_template.replace('${solution}', file.read())

        answer_template_file = os.path.join(template_folder, 'answer.html')
        with open(answer_template_file, 'r', encoding='utf-8') as file:
            task_template = task_template.replace('${answer}', file.read())
    else:
        task_template = task_template.replace('${solution}', '')
        task_template = task_template.replace('${answer}', '')


    # обходим каждый вопрос
    variant_src = ''
    for problem_number, substitution_tex_file in enumerate(structure):
        # путь к соответствующем html файлу условия
        problem_html_file = os.path.join(os.path.dirname(os.path.dirname(substitution_tex_file)),
                                         'html',
                                         os.path.splitext(os.path.basename(substitution_tex_file))[0] + '_problem.html')
        with open(problem_html_file, 'r', encoding='utf-8') as file:
            problem_html_src = file.read()

        # путь к соответствующем html файлу решения
        if with_solution:
            solution_html_file = os.path.join(os.path.dirname(os.path.dirname(substitution_tex_file)),
                                              'html',
                                              os.path.splitext(os.path.basename(substitution_tex_file))[
                                                  0] + '_solution.html')
            with open(solution_html_file, 'r', encoding='utf-8') as file:
                solution_html_src = file.read()

            answer_html_file = os.path.join(os.path.dirname(os.path.dirname(substitution_tex_file)),
                                              'html',
                                              os.path.splitext(os.path.basename(substitution_tex_file))[
                                                  0] + '_answer.html')
            with open(answer_html_file, 'r', encoding='utf-8') as file:
                answer_html_src = file.read()

        # добавляем задачу в тело билета
        variant_src += task_template
        variant_src = variant_src.replace('${problem_number}', str(problem_number + 1))
        variant_src = variant_src.replace('${problem_max_score}', '10')
        variant_src = variant_src.replace('${problem_src}', problem_html_src)

        # добавляем решение к задаче
        if with_solution:
            variant_src = variant_src.replace('${solution_src}', solution_html_src)
            variant_src = variant_src.replace('${answer_src}', answer_html_src)

    # подставляем содержимое билета
    variant = variant.replace('${variant_src}', variant_src)

    # подставляем сегодняшнюю дату
    variant = variant.replace('${variant_date}', datetime.now().strftime('%d.%m.%Y'))

    # имя итого файла
    dst_file_name = 'variant-' + str(variant_number) + ("-with-solution" if with_solution else "-only-problem")

    # сохраняем билет
    results_directory = os.path.join(os.getcwd(), 'results', 'html')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)
    with open(os.path.join(results_directory, dst_file_name + '.html'), 'w', encoding='utf-8') as file:
        file.write(variant)

    # создаем копию css файла
    if not os.path.exists(os.path.join(results_directory, 'stylesheets.css')):
        shutil.copyfile(os.path.join(config.get('GENERAL', 'templates_folder'), 'html', 'stylesheets.css'),
                        os.path.join(results_directory, 'stylesheets.css'))

    # копируем изображения, лежащие в папке шаблона, если нужно
    images_files = glob.glob(os.path.join(template_folder, '*.png'))
    for imagepath in images_files:
        if not os.path.exists(os.path.join(results_directory, os.path.basename(imagepath))):
            shutil.copyfile(imagepath, os.path.join(results_directory, os.path.basename(imagepath)))

    logging.info('Билет № ' + str(variant_number) +
                 ' в HTML формате' +
                 (' с решением ' if with_solution else ' без решения ') +
                 'создан!')


def make_moodle_variant(variant_number, structure):
    '''
    На основе переданной структуры задач создает файл варианта в формате Moodle XML
    :param variant_number: Номер варианта.
    :param structure: Список путей к файлам подстановок задач в формате TeX
    '''
    logging.info('Создаем билет № ' + str(variant_number) + ' в формате Moodle XML...')

    # берем файл общего шаблона html файла с подключением стилей и скриптов
    template_folder = os.path.join(config.get('GENERAL', 'templates_folder'), 'moodle')
    general_template_file = os.path.join(template_folder, 'template.xml')
    with open(general_template_file, 'r', encoding='utf-8') as file:
        variant = file.read()

    mathjaxcommands_file = os.path.join(__SETTINGS_FOLDER__, 'mathjaxcommands.tex')
    with open(mathjaxcommands_file, 'r', encoding='utf-8') as file:
        mathjaxcommands = file.read()

    # берем файл шаблона варианта
    variant_template_file = os.path.join(template_folder, 'variant.xml')
    with open(variant_template_file, 'r', encoding='utf-8') as file:
        variant = variant.replace('${body}', file.read())
        variant = variant.replace('${mathjaxcommands}', mathjaxcommands)

    # подставляем номер билета
    variant = variant.replace('${variant_name}', 'Билет № ' + str(variant_number))

    # формируем содержимое билета
    # берем шаблон задачи
    problem_template_file = os.path.join(template_folder, 'problem.xml')
    with open(problem_template_file, 'r', encoding='utf-8') as file:
        problem_template = file.read()

    # берем шаблон ответов
    answer_template_file = os.path.join(template_folder, 'answer.xml')
    with open(answer_template_file, 'r', encoding='utf-8') as file:
        answer_template = file.read()

    # обходим каждый вопрос
    variant_src = ''
    answers_xml = ''
    last_answer_index = 0
    for problem_number, substitution_tex_file in enumerate(structure):
        # путь к соответствующем html файлу условия
        problem_html_file = os.path.join(os.path.dirname(os.path.dirname(substitution_tex_file)),
                                         'html',
                                         os.path.splitext(os.path.basename(substitution_tex_file))[
                                             0] + '_problem.html')
        with open(problem_html_file, 'r', encoding='utf-8') as file:
            problem_html_src = file.read()

        # путь к соответствующем html файлу ответов
        answer_html_file = os.path.join(os.path.dirname(os.path.dirname(substitution_tex_file)),
                                          'html',
                                          os.path.splitext(os.path.basename(substitution_tex_file))[
                                              0] + '_answer.html')
        with open(answer_html_file, 'r', encoding='utf-8') as file:
            answer_html_src = file.read()

        # добавляем задачу в тело билета
        variant_src += problem_template
        variant_src = variant_src.replace('${problem_number}', str(problem_number + 1))
        variant_src = variant_src.replace('${problem_max_score}', '10')

        # добавляем секцию для ввода ответов
        # получаем численные ответы
        # через регулярные выражения находим все значения по шаблону \answerfield {.*}\
        answers = list(
            map(lambda answer: answer.replace(r',\!', '.'), re.findall(r'\\answerfield {(.*?)}\\', answer_html_src)))
        if len(answers) == 0:
            logging.error('Не найдены ответы для задачи № ' + str(problem_number + 1) +
                          ' в варианте № ' + str(variant_number) + '!')
        # заменяем численные ответы на placeholder
        for answer in answers:
            answer_html_src = answer_html_src.replace(r'\(\answerfield {' +
                                                          answer.replace('.', r',\!') + '}\)',
                                                          '{#answer' + str(last_answer_index + 1) + '}')
            answers_xml += answer_template
            answers_xml = answers_xml.replace('${partindex}', str(last_answer_index))
            answers_xml = answers_xml.replace('${placeholder}', 'answer' + str(last_answer_index + 1))
            answers_xml = answers_xml.replace('${answermark}', str(1))
            answers_xml = answers_xml.replace('${answer}', answer)
            # рассчитываем, сколько указано знаков в ответе после запятой, что определить допустимую ошибку
            count_signs = len(str(answer).split('.')[1])
            answers_xml = answers_xml.replace('${correctness}',
                                              '0' + ('.' + abs(count_signs - 2) * '0' + '1' if count_signs > 0 else ''))
            last_answer_index += 1

        problem_html_src += '<div class="answer">' + answer_html_src + '</div>'

        variant_src = variant_src.replace('${problem_src}', problem_html_src)

    # подставляем содержимое билета
    variant = variant.replace('${variant_src}', variant_src)
    # подставляем ответы
    variant = variant.replace('${answers}', answers_xml)

    # имя итого файла
    dst_file_name = 'variant-' + str(variant_number)

    # сохраняем билет
    results_directory = os.path.join(os.getcwd(), 'results', 'moodle')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)
    with open(os.path.join(results_directory, dst_file_name + '.xml'), 'w', encoding='utf-8') as file:
        file.write(variant)

    logging.info('Билет № ' + str(variant_number) + ' в формате Moodle XML создан!')


def merge_tex_variants():
    '''
    Объединяет файлы вариантов в TeX формате в один "variants_merged.tex" файл.
    '''
    results_directory = os.path.join(os.getcwd(), 'results', 'tex')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)

    # список всех файлов вариантов
    variants_files_list = sorted(filter(lambda filename: 'merged' not in filename,
                                        glob.glob(os.path.join(results_directory, 'variant-*.tex'))),
                                 key=lambda filename: int(
                                     os.path.splitext(os.path.basename(filename))[0].replace('variant-', '')))
    merged_tex_file = merge_tex(variants_files_list, use_template=True)

    # сохраняем объединенный файл вариантов
    with open(os.path.join(results_directory, 'variants_merged.tex'), 'w', encoding='utf-8') as file:
        file.write(merged_tex_file)

    logging.info('Объединенный файл вариантов в TeX формате создан!')


def merge_html_variants(with_solution=True):
    '''
    Объединяет файлы вариантов в HTML формате в один "variants_merged.html" файл.
    '''
    results_directory = os.path.join(os.getcwd(), 'results', 'html')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)

    # список всех файлов вариантов
    if with_solution:
        variants_files_list = glob.glob(os.path.join(results_directory, 'variant-*-with-solution.html'))
    else:
        variants_files_list = glob.glob(os.path.join(results_directory, 'variant-*-only-problem.html'))

    variants_files_list = sorted(filter(lambda filename: 'merged' not in filename,
                                        variants_files_list),
                                 key=lambda filename: int(
                                     os.path.splitext(
                                         os.path.basename(filename))[0]
                                         .replace('variant-', '')
                                         .replace('-with-solution', '')
                                         .replace('-only-problem', '')
                                 )
                                 )

    # берем файл общего шаблона html файла с подключением стилей и скриптов
    template_folder = os.path.join(config.get('GENERAL', 'templates_folder'), 'html')
    general_template_file = os.path.join(template_folder, 'template.html')
    with open(general_template_file, 'r', encoding='utf-8') as file:
        merged_html_file = file.read()

    mathjaxcommands_file = os.path.join(__SETTINGS_FOLDER__, 'mathjaxcommands.tex')
    with open(mathjaxcommands_file, 'r', encoding='utf-8') as file:
        mathjaxcommands = file.read()
    merged_html_file = merged_html_file.replace('${mathjaxcommands}', mathjaxcommands)

    # получаем содержимое всех вариантов
    acc_html = ''
    # обходим каждый файл варианта
    for variant_file in variants_files_list:
        with open(variant_file, 'r', encoding='utf-8') as file:
            variant_html = file.read()
            # получаем содержимое данного варианта
            start_key = '<!-- begin_variant -->'
            start_pos = variant_html.find(start_key) + len(start_key)

            end_key = '<!-- end_variant -->'
            end_pos = variant_html.find(end_key)

            acc_html += variant_html[start_pos:end_pos] + '\n\n'
    # подставляем содержимое билета
    merged_html_file = merged_html_file.replace('${body}', acc_html)

    # сохраняем объединенный файл вариантов
    with open(os.path.join(results_directory,
                           'variants_merged_' +
                           ('with_solution' if with_solution else 'only_problem') +
                           '.html'), 'w', encoding='utf-8') as file:
        file.write(merged_html_file)

    logging.info('Объединенный файл вариантов в HTML формате ' +
                 ('с решениями' if with_solution else 'без решений') + ' создан!')


def merge_moodle_variants():
    '''
    Объединяет файлы вариантов в Moodle XML формате в один "variants_merged.xml" файл.
    '''
    results_directory = os.path.join(os.getcwd(), 'results', 'moodle')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)

    # список всех файлов вариантов
    variants_files_list = sorted(glob.glob(os.path.join(results_directory, 'variant-*.xml')),
                                 key=lambda filename: int(
                                     os.path.splitext(os.path.basename(filename))[0].replace('variant-', '')))

    # cортируем в порядке возрастания вариантов
    variants_files_list = sorted(variants_files_list)

    # берем файл общего шаблона html файла
    template_folder = os.path.join(config.get('GENERAL', 'templates_folder'), 'moodle')
    general_template_file = os.path.join(template_folder, 'template.xml')
    with open(general_template_file, 'r', encoding='utf-8') as file:
        merged_xml_file = file.read()

    # получаем содержимое всех вариантов
    acc_xml = ''
    # обходим каждый файл варианта
    for variant_file in variants_files_list:
        with open(variant_file, 'r', encoding='utf-8') as file:
            variant_html = file.read()
            # получаем содержимое данного варианта
            variant_html = variant_html.replace('<?xml version="1.0" encoding="UTF-8"?>', '')
            variant_html = variant_html.replace('<quiz>', '')
            variant_html = variant_html.replace('</quiz>', '')

            acc_xml += variant_html + '\n\n'
    # подставляем содержимое билета
    merged_xml_file = merged_xml_file.replace('${body}', acc_xml)

    # сохраняем объединенный файл вариантов
    with open(os.path.join(results_directory, 'variants_merged.xml'), 'w', encoding='utf-8') as file:
        file.write(merged_xml_file)

    logging.info('Объединенный файл вариантов в Moodle XML формате создан!')


def merge_all_substitutions(folder=config.get('GENERAL', 'bank_folder')):
    '''
    Объединяет все подстановки в TeX и HTML форматах.
    '''
    # создаем структуру
    structure = []
    # обходим каждый вопрос
    # для этого находим все файлы параметризации .ipynb
    for ipynb_file in glob.glob(os.path.join(folder, '**', '*.ipynb'), recursive=True):
        task_folder = os.path.dirname(ipynb_file)
        substitutions_list = sorted(
            glob.glob(
                os.path.join(
                    task_folder,
                    'substitutions',
                    'tex',
                    'substitution_*.tex'
                )
            )
        )
        structure += substitutions_list

    # сохраняем структуру объединенного варианта в папке результатов
    save_structure(structure={'all-substitutions-merged': structure}, filename='structure-all-substitutions-merged')

    make_tex_variant(variant_number='all-substitutions-merged', structure=structure, print_bilet_number=True,
                     prefix='', another_bilet_title='Объединенный файл всех подстановок')
    make_html_variant(variant_number='all-substitutions-merged', structure=structure)

    logging.info('Объединенные файлы всех подстановок в TeX и HTML форматах созданы!')


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


def make_variants(folder=config.get('GENERAL', 'bank_folder'), size=1, start=1):
    '''
    Собирает файлы вариантов на основе сгенерированных подстановок.
    :param folder: Папка, в которой лежат задачи с подстановками.
    :param size: Количество создаваемых вариантов.
    :param start: Начало нумерации вариантов.
    '''
    results_directory = os.path.join(os.getcwd(), 'results')
    if os.path.exists(results_directory):
        shutil.rmtree(results_directory)
    results_directory = os.path.join(results_directory, 'tex')
    os.makedirs(results_directory)

    # обновляем стилевой файл taskgen.sty
    copy_taskgen_sty(folder=results_directory, force=True, logging_enabled=False)
    # обновляем файл taskgen.4ht
    copy_taskgen_4ht(folder=results_directory, force=True, logging_enabled=False)

    # сначала создаем структуру вариантов, т.е. определяем из каких файлов подстановок будет состоять каждый вариант
    # сохраняем ее как в машинном виде, так и в человекочитаемом
    # по этому файлу можно будет легко определить, что детерминированная генерация вариантов работает корректно
    # на основе машинной версии файла можно будет легко собрать как tex, так и html, так и moodle версии вариантов
    structure = make_variants_structure(folder=folder, size=size, start=start)

    # на основе созданной структуры собираем tex файлы вариантов
    for variant_number, subs_lst in structure.items():
        make_tex_variant(variant_number, subs_lst)
        make_html_variant(variant_number, subs_lst, with_solution=True)
        make_html_variant(variant_number, subs_lst, with_solution=False)
        make_moodle_variant(variant_number, subs_lst)

    # создаем объединенный файл вариантов в формате TeX
    merge_tex_variants()

    # создаем объединенный файл вариантов в формате HTML
    merge_html_variants(with_solution=True)
    merge_html_variants(with_solution=False)

    # обновляем исходный код mathjax
    dst_mathjax_path = os.path.join(os.path.join(os.path.dirname(results_directory), 'html'), 'mathjax.js')
    shutil.copyfile(os.path.join(__SETTINGS_FOLDER__, 'mathjax.js'), dst_mathjax_path)

    # создаем объединенный файл вариантов в формате Moodle XML
    merge_moodle_variants()

    logging.info('Файлы вариантов сгенерированы!')


def variants2pdf():
    '''
    Конвертирует html файлы вариантов в pdf.
    '''
    html2pdf(os.path.join(os.getcwd(), 'results', 'html'), \
             os.path.join(os.getcwd(), 'results', 'pdf'), in_one_page=True)


def tex2html(sourcepath=config.get('GENERAL', 'bank_folder'), targetpath='', remove_tmp_folder=True):
    '''
    Конвертирует TeX файл в HTML. Использует make4ht.

    Если в качестве входного пути передана директория, то функция рекурсивно (с любым уровнем вложенности)
    находит все папки с задачами в этой директории и конвертирует их объединенные tex файлы в html с последующей
    нарезкой на отдельные подстановки.
    '''
    sourcepath = os.path.abspath(sourcepath)
    if os.path.isdir(sourcepath):
        is_task_folder = get_parametrizator_path(sourcepath, logging_enabled=False) is not False
        if is_task_folder:
            tex_substitutions2html_optimized(folder=sourcepath, remerge=True, remove_tmp_folder=remove_tmp_folder)
            return True
        else:
            for task_parametrizer_file in glob.glob(os.path.join(sourcepath, '**', '*.ipynb'), recursive=True):
                tex2html(os.path.dirname(task_parametrizer_file), remove_tmp_folder=remove_tmp_folder)
            return True
    targetpath = os.path.abspath(targetpath)

    initial_path = os.getcwd()

    # создаем временный каталог для этой задачи, копируем туда конфиги, а затем переходим в него
    tempdir = os.path.join(os.getcwd(), 'tmp', str(binascii.crc32(targetpath.encode('utf8'))))
    if os.path.exists(tempdir):
        shutil.rmtree(tempdir)
    os.makedirs(tempdir)
    shutil.copyfile(os.path.join(__SETTINGS_FOLDER__, 'ht5mjlatex.cfg'),
                    os.path.join(tempdir, 'ht5mjlatex.cfg'))
    shutil.copyfile(os.path.join(__SETTINGS_FOLDER__, 'mathjaxcommands.tex'),
                    os.path.join(tempdir, 'mathjaxcommands.tex'))
    shutil.copyfile(os.path.join(__SETTINGS_FOLDER__, 'taskgen.sty'),
                    os.path.join(tempdir, 'taskgen.sty'))
    shutil.copyfile(os.path.join(__SETTINGS_FOLDER__, 'taskgen.4ht'),
                    os.path.join(tempdir, 'taskgen.4ht'))
    # копируем нужный tex файл во временную директорию
    shutil.copyfile(sourcepath, os.path.join(tempdir, os.path.basename(sourcepath)))
    os.chdir(tempdir)

    logging.info('Конвертируем файл ' + sourcepath + '...')
    cmd = 'make4ht --utf8 --config ht5mjlatex.cfg --mode draft --output-dir "' + os.path.dirname(targetpath) \
          + '" --jobname "' + os.path.splitext(os.path.basename(targetpath))[0] + '" "' + os.path.basename(
        sourcepath) + '" "mathjax"'
    args = shlex.split(cmd)
    with subp.Popen(args, stdout=subp.PIPE) as proc:
        output = proc.stdout.read().decode('utf-8', 'ignore')
    print(output)

    os.chdir(initial_path)

    # копируем исходный код mathjax в папку назначения
    copy_mathjax_js(folder=os.path.dirname(targetpath), logging_enabled=False)

    if remove_tmp_folder:
        # очищаем текущую директорию от временных файлов
        logging.info('Удаляем временные файлы для ' + sourcepath + '...')
        # удаляем временную директорию
        shutil.rmtree(tempdir)
    else:
        logging.info('Временные файлы для "' + sourcepath + '" расположены в "' + tempdir + '"')


    return True


def tex_substitutions2html(multiprocessing=True):
    '''
    Конвертирует TeX файлы подстановок в HTML.
    '''
    src_lst = glob.glob(
        os.path.join(os.getcwd(), 'bank', '**', 'substitutions', 'tex', 'substitution*.tex'),
        recursive=True
    )
    trgt_lst = list(map(
        lambda path:
        os.path.splitext(path.replace(
            os.path.join('substitutions', 'tex'),
            os.path.join('substitutions', 'html')
        ))[0] + '.html',
        src_lst
    ))
    if multiprocessing:
        with Pool(int(config.get('GENERAL', 'converter_threads_count'))) as p:
            p.starmap(tex2html, zip(src_lst, trgt_lst))
    else:
        for sourcepath, targetpath in zip(src_lst, trgt_lst):
            tex2html(sourcepath, targetpath)
    logging.info('Файлы вариантов сконвертированы в HTML!')


def mergedTex2HtmlWithSlicing(merged_tex_file, remove_tmp_folder=True):
    '''
    Конвертирует объединенный TeX файл в HTML.
    После конвертации разбивает его на множество мелких html файлов, из которых он состоит.

    На вход ожидает путь к TeX файлу, содержащим множество задач.
    Одна задача определяется набором из 3 окружений "problem", "solution" и "answer", идущих друг за другом.
    Конвертирует этот файл в его html версию средствами make4ht (функция "tex2html").
    Затем синтаксически анализирует DOM, идентифицирует искомые задачи и создает для каждой задачи
    свой набор html для формулировки условия и решения.

    Ожидается, что merged файл лежит в директории с названием "tex".
    Результирующие файлы будут расположены в директории "html", лежащей рядом с "tex".
    '''
    html_directory = os.path.join(os.path.dirname(os.path.dirname(merged_tex_file)), 'html')
    if os.path.exists(html_directory):
        shutil.rmtree(html_directory)
    os.makedirs(html_directory)

    # конвертируем tex в html
    merged_html_file = os.path.join(html_directory, 'substitutions_merged.html')
    tex2html(
        sourcepath=merged_tex_file,
        targetpath=merged_html_file,
        remove_tmp_folder=remove_tmp_folder
    )

    # объединенный файл может содержать подстановки из нескольких задач
    # получаем содержимое всех div.problem, div.solution, div.answer
    # и сохраняем их в папку подстановок задачи

    with open(merged_html_file, 'r', encoding='utf-8') as file:
        source_html = file.read()
    soup = BeautifulSoup(source_html, 'html.parser')

    subs_cnt = 0
    # окружения problem
    problems = soup.find_all('div', class_='problem')
    for problem in problems:
        dst_file = os.path.join(html_directory, 'substitution_' + str(subs_cnt + 1) + '_problem.html')
        with open(dst_file, 'w', encoding='utf-8') as file:
            file.write(problem.prettify()[len('<div class="problem">'):-(len('</div>') + 1)])
        subs_cnt += 1

    subs_cnt = 0
    # окружения solution
    solutions = soup.find_all('div', class_='solution')
    for solution in solutions:
        dst_file = os.path.join(html_directory, 'substitution_' + str(subs_cnt + 1) + '_solution.html')
        with open(dst_file, 'w', encoding='utf-8') as file:
            file.write(solution.prettify()[len('<div class="solution">'):-(len('</div>') + 1)])
        subs_cnt += 1

    subs_cnt = 0
    # окружения answer
    answers = soup.find_all('div', class_='answer')
    for answer in answers:
        dst_file = os.path.join(html_directory, 'substitution_' + str(subs_cnt + 1) + '_answer.html')
        with open(dst_file, 'w', encoding='utf-8') as file:
            file.write(answer.prettify()[len('<div class="answer">'):-(len('</div>') + 1)])
        subs_cnt += 1


def tex_substitutions2html_optimized(folder=config.get('GENERAL', 'bank_folder'), remerge=False, remove_tmp_folder=True):
    '''
    Конвертирует TeX файлы подстановок в HTML оптимизированным способом за счет использования merged файла.
    Благодаря этому множество файлов подстановок данной задачи конвертируются в html за 1 проход.
    Параметр remerge указывает на то, нужно ли пересобирать объединенный файл подстановок перед конвертацией.
    '''
    folder = os.path.abspath(os.path.join(folder))
    src_lst = glob.glob(
        os.path.join(folder, '**', 'substitutions', 'tex', 'substitutions_merged.tex'),
        recursive=True
    )
    for file_path in src_lst:
        if remerge:
            substitutions_directory = os.path.dirname(file_path)
            # список всех файлов с подстановками
            subs_files_list = glob.glob(os.path.join(substitutions_directory, 'substitution_*.tex'))
            merged_latex_file = merge_tex(subs_files_list)
            # сохраняем объединенный файл подстановок
            with open(os.path.join(substitutions_directory, 'substitutions_merged.tex'), 'w', encoding='utf-8') as file:
                file.write(merged_latex_file)
        mergedTex2HtmlWithSlicing(file_path, remove_tmp_folder=remove_tmp_folder)
    logging.info('Файлы подстановок сконвертированы в HTML!')


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


def show(subs_data={}):
    '''
    Выводит задачу с подставленными значениями сконвертированную из TeX в HTML.
    '''
    # находим файл шаблона в папке задачи
    template_path = get_template_path(os.getcwd())
    if not template_path:
        return False
    # создаем директорию для хранения результатов
    results_directory = os.path.join(os.getcwd(), 'tmp')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)

    # обновляем стилевой файл taskgen.sty
    copy_taskgen_sty(folder=results_directory, logging_enabled=False)
    # обновляем файл taskgen.4ht
    copy_taskgen_4ht(folder=results_directory, logging_enabled=False)
    # обновляем файл mathjax.js
    copy_mathjax_js(folder=results_directory, logging_enabled=False)

    # подставляем переданные значения
    logging.info(f'Подставляем переданные значения в шаблон "{template_path}"...')
    subs_file_name = datetime.now().strftime("subs_%d.%m.%Y_%H-%M-%S.tex")
    targetpath_tex = os.path.join(results_directory, subs_file_name)
    latex_subs(template_path, targetpath_tex, subs_data)
    targetpath_html = os.path.splitext(targetpath_tex)[0] + '.html'
    # конвертируем в hmtl
    if tex2html(
            sourcepath=targetpath_tex,
            targetpath=targetpath_html
    ):
        # отдаем содержимое html
        with open(targetpath_html, 'r', encoding='utf-8') as file:
            src = file.read()
        return HTML('<base target="_self" href="./tmp/">' + src)


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


def copy_mathjax_js(folder=os.getcwd(), force=False, logging_enabled=True):
    '''
    Копирует файл "mathjax.js" из папки настроек в указанную (по умолчанию в текущую).
    Если в указанной папке уже есть "mathjax.js", то он его перезапишет в том случае,
    если дата изменения "mathjax.js" в папке настроек более поздняя.

    :param folder: путь к папке, в которую нужно скопировать файл "mathjax.js"
    :param force: нужно ли перезаписывать файл "mathjax.js", если он уже есть в указанной директории и у него более
    поздняя дата редактирования, чем у файла из папки настроек
    '''
    if os.path.basename(folder) == 'data':
        return None
    dst_taskgen_4ht_path = os.path.join(folder, 'mathjax.js')
    primary_taskgen_4ht_path = os.path.join(__SETTINGS_FOLDER__, 'mathjax.js')
    if force or not os.path.exists(dst_taskgen_4ht_path) or \
            os.path.getmtime(primary_taskgen_4ht_path) > os.path.getmtime(dst_taskgen_4ht_path):
        shutil.copyfile(primary_taskgen_4ht_path, dst_taskgen_4ht_path)
        if logging_enabled:
            logging.info(
                'Файл "mathjax.js" из папки настроек "' + __SETTINGS_FOLDER__ +
                '" скопирован в папку "' + folder + '"')
        return True
    else:
        if logging_enabled:
            logging.info(
                'Файл "mathjax.js" уже есть в указанной директории! Используйте функцию с параметром ' +
                '"force=True" для перезаписи файла!')
        return False
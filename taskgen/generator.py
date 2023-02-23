'''
Copyright (c) 2022 Артём Золотаревский

Отдельная благодарность научному руководителю, Павлу Евгеньевичу Рябова, за постановку задачи и постоянное внимание к работе.

Это свободная программа: вы можете перераспространять ее и/или изменять ее на условиях
Стандартной общественной лицензии GNU в том виде, в каком она была опубликована
Фондом свободного программного обеспечения; либо версии 3 лицензии, либо (по вашему выбору) любой более поздней версии.

Эта программа распространяется в надежде, что она будет полезной, но БЕЗО ВСЯКИХ ГАРАНТИЙ;
даже без неявной гарантии ТОВАРНОГО ВИДА или ПРИГОДНОСТИ ДЛЯ ОПРЕДЕЛЕННЫХ ЦЕЛЕЙ.
Подробнее см. в Стандартной общественной лицензии GNU.

Вы должны были получить копию Стандартной общественной лицензии GNU вместе с этой программой.
Если это не так, см. <https://www.gnu.org/licenses/>.
'''

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

config = configparser.ConfigParser()
config['GENERAL'] = {
    # Название файла шаблона задачи, в который будет
    # выполняться подстановка сгенерированных параметров
    'template_name': 'template.tex',

    # Название файла, содержащего код параметризация задачи
    'parametrizator_name': 'parametrizator.ipynb',

    # Шаблон строкового выражения для подстановки параметров в общий шаблон задачи.
    # Вместо двух символов процента (%%) в файле шаблона задачи должно располагаться
    # название подставляемой переменной. Обязательно, чтобы данная настройка
    # содержала какие-то символы до и после знака процента
    'substitution_template': '\subs{%%}',

    # Название функции, которая возвращает словарь (ассоциативный массив) названий
    # подставляемых переменных и их соответствующие значения для новой параметризации
    'parameterizer_function_name': 'GET',

    # Количество потоков для выполнения параметризации
    'parameterizer_threads_count': '10',

    # Количество потоков для выполнения конвертации из TeX в HTML
    'converter_threads_count': '10'
}
config.read(os.path.join(os.getcwd(), 'settings', 'config.ini'))


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
    :param from_file:
    :param to_file:
    :param params:
    :return:
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


def gen_subs_data(task_folder, n):
    '''
    Генерируем данные для подстановки.
    Эти данные в json формате будут располагаться в подпапке "data" папки задачи.
    '''
    # читаем файл ноутбука
    path = os.path.join(task_folder, config.get('GENERAL', 'parametrizator_name'))
    with open(path, 'r', encoding='utf-8') as file:
        # распознаем json cтруктуру документа
        ipynb_src = json.load(file)

    # выбираем ячейки с исполняемым кодом
    cells = list(filter(lambda cell: cell['cell_type'] == 'code', ipynb_src['cells']))

    # объединяем строки в один исполняемый файл
    parametrizer_script = '\n'.join([''.join(cell['source']) for cell in cells])

    # создаем директорию для хранения подстановочных данных
    data_directory = os.path.join(task_folder, 'data')
    if not os.path.exists(data_directory):
        os.makedirs(data_directory)

    # добавляем код, запукающий функцию GET нужное количество раз
    # и сохранящий папаметризацию в json
    parametrizer_script += 'import json\n'
    parametrizer_script += 'parametrizer_result = []\n'
    parametrizer_script += f"for i in range({n}):\n\tparametrizer_result.append({config.get('GENERAL', 'parameterizer_function_name')}())\n"
    parametrizer_script += "with open('" + os.path.join(data_directory,
        'data.json') + "', 'w', encoding='utf-8') as file:\n\tjson.dump(parametrizer_result, file)\n"

    # сохраням код параметризации в отдельный .py файл
    with open(os.path.join(data_directory, 'parametrizator.py'), 'w', encoding='utf-8') as file:
        file.write(parametrizer_script + '\n')

    # запускаем интерпретатор python и выполняем код ноутбука
    os.system('python "' + os.path.join(data_directory, 'parametrizator.py') + '"')

    logging.info('"' + task_folder + '" json файл с данными для подстановок создан')

    # читаем json с данными
    # with open(os.path.join(task_folder, 'data.json'), 'r', encoding='utf-8') as file:
    #    return json.load(file)


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
    merged_file += r'\usepackage' + ('[use_template]' if use_template else '') + '{' + header + '}' + '\n'
    merged_file += r'\begin{document}' + '\n'
    for path in files_list:
        merged_file += get_tex_body(path) + '\n'
    merged_file += r'\end{document}'
    return merged_file


def gen_data(n=1, folder='bank'):
    '''
    Генерирует данные для подстановки для каждой задачи в папке.
    Основан на функции "gen_subs_data".
    '''
    with Pool(int(config.get('GENERAL', 'parameterizer_threads_count'))) as p:
        p.starmap(gen_subs_data, list(map(lambda ipynb_file: (os.path.dirname(ipynb_file), n), glob.glob(
            os.path.join(folder, '**', config.get('GENERAL', 'parametrizator_name')), recursive=True))))
    logging.info('Генерация подстановочных данных завершена!')


def gen_subs(n=1, folder='bank'):
    '''
    Создает заданное число подстановок каждой задачи в указанной папке.
    Данные для подстановок должны быть заранее сгенерированы посредством функции "gen_data".
    '''
    for ipynb_file in glob.glob(os.path.join(folder, '**', config.get('GENERAL', 'parametrizator_name')),
                                recursive=True):
        task_folder = os.path.dirname(ipynb_file)
        # создаем директорию для хранения файлов подстановок
        substitutions_directory = os.path.join(task_folder, 'substitutions', 'tex')
        if not os.path.exists(substitutions_directory):
            os.makedirs(substitutions_directory)
        # очищаем прошлые подстановки
        for file in glob.glob(os.path.join(substitutions_directory, 'substitution_*.*')):
            os.remove(file)
        # читаем файл с данными для подстановок
        with open(os.path.join(task_folder, 'data', 'data.json'), 'r', encoding='utf-8') as file:
            data = json.load(file)
        # создаем подстановки
        for i in range(len(data)):
            # подставляем значения
            latex_subs(from_file=os.path.join(task_folder, config.get('GENERAL', 'template_name')),
                       to_file=os.path.join(substitutions_directory, f'substitution_{i + 1}.tex'), params=data[i])
        # список всех файлов с подстановками
        subs_files_list = glob.glob(os.path.join(substitutions_directory, 'substitution_*.tex'))
        merged_latex_file = merge_tex(subs_files_list)
        # сохраняем объединенный файл подстановок
        with open(os.path.join(substitutions_directory, 'substitutions_merged.tex'), 'w', encoding='utf-8') as file:
            file.write(merged_latex_file)
        logging.info(os.path.dirname(ipynb_file) + '" TeX файлы с подстановками созданы')
    logging.info('Генерация TeX файлов с подстановками завершена!')


def gen_bank(n=1, folder='bank'):
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
    :return: файлы подстановок в tex и html форматах.
    '''
    # параметризуем задачи, получаем параметры для подстановок
    gen_data(n, folder)
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


def make_variants_structure(folder='./bank', size=1, start=1):
    '''
    Создает структуру вариантов, т.е. определяет из каких файлов подстановок будет состоять каждый вариант.

    Кол-во задач в варианте то же, что и кол-во папок в переданной директории folder.
    Порядок задач в варианте зависит от лексикографического порядка папок.

    Сначала случайным образом выбирается тема, затем случайным образом выбирается задача, после этого случайным
    образом выбирается i-я подстановка.

    :param folder: Папка, в которой лежат задачи с подстановками.
    :param size: Количество создаваемых вариантов.
    :param start: Начало нумерации вариантов.
    :return: Машинное и человекочетаемое представления структуры вариантов.
    '''
    # генерируем варианты
    variants = {}
    for variant_number in range(start, start + size):
        logging.info('Создаем структуру билета № ' + str(variant_number) + '...')
        # обходим каждый вопрос
        for question_folder in sorted(glob.glob(os.path.join(folder, '*'))):
            # случайным образом выбираем тему):
            omega_themes = get_omega_folders(question_folder)
            if len(omega_themes) == 0:
                logging.warning('Директория ' + question_folder + ' не содержит папок с темами!')
                continue
            theme_folder = random.choice(omega_themes)
            # случайным образом выбираем задачу
            omega_tasks = get_omega_folders(theme_folder)
            if len(omega_tasks) == 0:
                logging.warning('Директория ' + theme_folder + ' не содержит папок с задачами!')
                continue
            task_folder = random.choice(omega_tasks)
            # случайным образом выбираем подстановку
            substitutions_list = glob.glob(os.path.join(task_folder, 'substitutions', 'tex', 'substitution_*.tex'))
            substitution_file = random.choice(substitutions_list)
            # сохраняем выбор
            variants.update({variant_number: variants.get(variant_number, []) + [substitution_file]})

    # сохраняем структуру в файл
    results_directory = os.path.join(os.getcwd(), 'results')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)

    dst_json_file = os.path.join(results_directory, 'structure.json')
    with open(dst_json_file, 'w', encoding='utf-8') as file:
        json.dump(variants, file)

    dst_txt_file = os.path.join(results_directory, 'structure.txt')
    txt_file_src = ''
    for variant_number, subs_lst in variants.items():
        txt_file_src += 'Вариант № ' + str(variant_number) + ':\n\t'
        txt_file_src += '\n\t'.join(subs_lst) + '\n\n'
    with open(dst_txt_file, 'w', encoding='utf-8') as file:
        file.write(txt_file_src)

    logging.info('Структура вариантов создана!')

    return variants

def make_tex_variant(variant_number, structure):
    '''
    На основе переданной структуры задач создает файл варианта в формате TeX
    :param variant_number: Номер варианта.
    :param structure: Список путей к файлам подстановок задач в формате TeX
    '''
    logging.info('Создаем билет № ' + str(variant_number) + ' в TeX формате...')
    # тело билета
    variant_src = r'\documentclass[11pt]{article}' + '\n'
    variant_src += r'\usepackage{taskgen}' + '\n' # [use_template]
    variant_src += r'\begin{document}' + '\n'
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
    with open(os.path.join(results_directory, f'variant-{str(variant_number)}.tex'), 'w', encoding='utf-8') as file:
        file.write(variant_src)
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
    template_folder = os.path.join(os.getcwd(), 'templates', 'html')
    general_template_file = os.path.join(template_folder, 'template.html')
    with open(general_template_file, 'r', encoding='utf-8') as file:
        variant = file.read()

    # берем файл шаблона варианта
    variant_template_file = os.path.join(template_folder, 'variant.html')
    with open(variant_template_file, 'r', encoding='utf-8') as file:
        variant = variant.replace('${body}', file.read())

    # подставляем номер билета
    variant = variant.replace('${variant_number}', str(variant_number))

    # формируем содержимое билета
    # берем шаблон задачи
    problem_template_file = os.path.join(template_folder, 'problem.html')
    with open(problem_template_file, 'r', encoding='utf-8') as file:
        problem_template = file.read()

    # берем шаблон решения
    if with_solution:
        solution_template_file = os.path.join(template_folder, 'solution.html')
        with open(solution_template_file, 'r', encoding='utf-8') as file:
            solution_template = file.read()

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
                                             os.path.splitext(os.path.basename(substitution_tex_file))[0] + '_solution.html')
            with open(solution_html_file, 'r', encoding='utf-8') as file:
                solution_html_src = file.read()

        # добавляем задачу в тело билета
        variant_src += problem_template
        variant_src = variant_src.replace('${problem_number}', str(problem_number + 1))
        variant_src = variant_src.replace('${problem_max_score}', '10')
        variant_src = variant_src.replace('${problem_src}', problem_html_src)

        # добавляем решение к задаче
        if with_solution:
            variant_src += solution_template
            variant_src = variant_src.replace('${solution_src}', solution_html_src)
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
        shutil.copyfile(os.path.join(os.getcwd(), 'templates', 'html', 'stylesheets.css'),
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
    template_folder = os.path.join(os.getcwd(), 'templates', 'moodle')
    general_template_file = os.path.join(template_folder, 'template.xml')
    with open(general_template_file, 'r', encoding='utf-8') as file:
        variant = file.read()

    # берем файл шаблона варианта
    variant_template_file = os.path.join(template_folder, 'variant.xml')
    with open(variant_template_file, 'r', encoding='utf-8') as file:
        variant = variant.replace('${body}', file.read())

    # подставляем номер билета
    variant = variant.replace('${variant_number}', str(variant_number))

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
    for problem_number, substitution_tex_file in enumerate(structure):
        # путь к соответствующем html файлу условия
        problem_html_file = os.path.join(os.path.dirname(os.path.dirname(substitution_tex_file)),
                                         'html',
                                         os.path.splitext(os.path.basename(substitution_tex_file))[
                                             0] + '_problem.html')
        with open(problem_html_file, 'r', encoding='utf-8') as file:
            problem_html_src = file.read()

        # путь к соответствующем html файлу решения
        solution_html_file = os.path.join(os.path.dirname(os.path.dirname(substitution_tex_file)),
                                          'html',
                                          os.path.splitext(os.path.basename(substitution_tex_file))[
                                              0] + '_solution.html')
        with open(solution_html_file, 'r', encoding='utf-8') as file:
            solution_html_src = file.read()

        # добавляем задачу в тело билета
        variant_src += problem_template
        variant_src = variant_src.replace('${problem_number}', str(problem_number + 1))
        variant_src = variant_src.replace('${problem_max_score}', '10')
        variant_src = variant_src.replace('${problem_src}', problem_html_src)

        # добавляем решение к задаче
        variant_src += answer_template
        variant_src = variant_src.replace('${solution_src}', solution_html_src)
    # подставляем содержимое билета
    variant = variant.replace('${variant_src}', variant_src)

    # подставляем сегодняшнюю дату
    variant = variant.replace('${variant_date}', datetime.now().strftime('%d.%m.%Y'))

    # имя итого файла
    dst_file_name = 'variant-' + str(variant_number)

    # сохраняем билет
    results_directory = os.path.join(os.getcwd(), 'results', 'moodle')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)
    with open(os.path.join(results_directory, dst_file_name + '.xml'), 'w', encoding='utf-8') as file:
        file.write(variant)

    logging.info('Билет № ' + str(variant_number) +' в формате Moodle XML создан!')

def merge_tex_variants():
    '''
    Объединяет файлы вариантов в TeX формате в один "variants_merged.tex" файл.
    '''
    results_directory = os.path.join(os.getcwd(), 'results', 'tex')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)

    # список всех файлов вариантов
    variants_files_list = glob.glob(os.path.join(results_directory, 'variant-*.tex'))
    merged_tex_file = merge_tex(variants_files_list, use_template=False)

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

    # cортируем в порядке возрастания вариантов
    variants_files_list = sorted(variants_files_list)

    # берем файл общего шаблона html файла с подключением стилей и скриптов
    template_folder = os.path.join(os.getcwd(), 'templates', 'html')
    general_template_file = os.path.join(template_folder, 'template.html')
    with open(general_template_file, 'r', encoding='utf-8') as file:
        merged_html_file = file.read()

    # получаем содержимое всех вариантов
    acc_html = ''
    # обходим каждый файл варианта
    for variant_file in variants_files_list:
        with open(variant_file, 'r', encoding='utf-8') as file:
            variant_html = file.read()
            # получаем содержимое данного варианта
            start_key = '<!-- begin -->'
            start_pos = variant_html.find(start_key) + len(start_key)

            end_key = '<!-- end -->'
            end_pos = variant_html.find(end_key)

            acc_html += variant_html[start_pos:end_pos] + '\n\n'
    # подставляем содержимое билета
    merged_html_file = merged_html_file.replace('${body}', acc_html)

    # сохраняем объединенный файл вариантов
    if with_solution:
        variants_files_list = glob.glob(os.path.join(results_directory, 'variant-*-with-solution.html'))
    else:
        variants_files_list = glob.glob(os.path.join(results_directory, 'variant-*-only-problem.html'))

    with open(os.path.join(results_directory,
                           'variants_merged_' +
                           ('with_solution' if with_solution else 'only_problem') +
                           '.html'), 'w', encoding='utf-8') as file:
        file.write(merged_html_file)

    logging.info('Объединенный файл вариантов в HTML формате ' +
                 ('с решениями' if with_solution else 'без решений') + ' создан!')


def merge_all_substitutions(folder='./bank'):
    '''
    Объединяет все подстановки в TeX и HTML форматах.
    '''
    # создаем структуру
    structure = []
    # обходим каждый вопрос
    for question_folder in sorted(glob.glob(os.path.join(folder, '*'))):
        omega_themes = get_omega_folders(question_folder)
        # обходим каждую тему
        for theme_folder in omega_themes:
            omega_tasks = get_omega_folders(theme_folder)
            # обходим каждую тему
            for task_folder in omega_tasks:
                substitutions_list = sorted(glob.glob(os.path.join(task_folder,
                                                                   'substitutions',
                                                                   'tex',
                                                                   'substitution_*.tex')))
                structure += substitutions_list

    make_tex_variant(variant_number='all-substitutions', structure=structure)
    make_html_variant(variant_number='all-substitutions', structure=structure)

    logging.info('Объединенные файлы всех подстановок в TeX и HTML форматах созданы!')


def remove_substitutions(folder='./bank'):
    '''
    Удаляет все подстановки.
    '''
    tasks_folders_list = map(lambda path: os.path.dirname(path),
                             glob.glob(os.path.join(folder, '**', 'parametrizator.ipynb'), recursive=True))
    for task_folder in tasks_folders_list:
        shutil.rmtree(os.path.join(task_folder, 'substitutions'))
        shutil.rmtree(os.path.join(task_folder, 'data'))
        shutil.rmtree(os.path.join(task_folder, 'tmp'))

    logging.info('Папки "substitutions", "data" и "tmp" удалены для всех задач!')


def make_variants(folder='./bank', size=1, start=1):
    '''
    Собирает файлы вариантов на основе сгенерированных подстановок.
    :param folder: Папка, в которой лежат задачи с подстановками.
    :param size: Количество создаваемых вариантов.
    :param start: Начало нумерации вариантов.
    '''
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

    # создаем объединенный файл вариантов в формате TeX
    merge_tex_variants()

    # создаем объединенный файл вариантов в формате HTML
    merge_html_variants(with_solution=True)
    merge_html_variants(with_solution=False)

    logging.info('Файлы вариантов сгенерированы!')

def variants2pdf():
    '''
    Конвертирует html файлы вариантов в pdf.
    '''
    html2pdf(os.path.join(os.getcwd(), 'results', 'html'), \
             os.path.join(os.getcwd(), 'results', 'pdf'), in_one_page=True)


# конвертируем html файлы вариантов в moodle_xml
def variants2moodle():
    '''
    Конвертирует файлы вариантов в формат Moodle XML.
    '''
    # заменить ответы на знаки подстановок
    # распарсить ответы из latex файла
    # изображения включать как base64
    # сделать версии html вариантов без ответов


    pass

def tex2html(sourcepath, targetpath):
    '''
    Конвертирует TeX файл в HTML. Использует make4ht.
    make4ht - build system for TeX4ht
    Usage:
    make4ht [options] filename ["tex4ht.sty op." "tex4ht op."
         "t4ht op" "latex op"]
    -a,--loglevel (default status) Set log level.
                possible values: debug, info, status, warning, error, fatal
    -b,--backend (default tex4ht) Backend used for xml generation.
         possible values: tex4ht or lua4ht
    -c,--config (default xhtml) Custom config file
    -d,--output-dir (default "")  Output directory
    -e,--build-file (default nil)  If the build filename is different
         than `filename`.mk4
    -f,--format  (default nil)  Output file format
    -j,--jobname (default nil)  Set the jobname
    -l,--lua  Use lualatex for document compilation
    -m,--mode (default default) Switch which can be used in the makefile
    -n,--no-tex4ht  Disable DVI file processing with tex4ht command
    -s,--shell-escape Enables running external programs from LaTeX
    -u,--utf8  For output documents in utf8 encoding
    -x,--xetex Use xelatex for document compilation
    -v,--version  Print version number
    <filename> (string) Input filename
    '''
    sourcepath = os.path.abspath(sourcepath)
    targetpath = os.path.abspath(targetpath)

    # заходим в корневой каталог
    os.chdir(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

    # создаем временный каталог для этой задачи, копируем туда конфиги, а затем переходим в него
    tempdir = os.path.join(os.getcwd(), 'tmp', str(binascii.crc32(targetpath.encode('utf8'))))
    if not os.path.exists(tempdir):
        os.makedirs(tempdir)
    shutil.copyfile(os.path.join(os.getcwd(), 'settings', 'ht5mjlatex.cfg'),
                    os.path.join(tempdir, 'ht5mjlatex.cfg'))
    shutil.copyfile(os.path.join(os.getcwd(), 'settings', 'mathjaxcommands.tex'),
                    os.path.join(tempdir, 'mathjaxcommands.tex'))
    os.chdir(tempdir)

    logging.info('Конвертируем файл ' + sourcepath + '...')
    cmd = 'make4ht --utf8 --config ht5mjlatex.cfg --mode draft --output-dir "' + os.path.dirname(targetpath) \
        + '" --jobname "' + os.path.splitext(os.path.basename(targetpath))[0] + '" "' + sourcepath + '" "mathjax"'
    args = shlex.split(cmd)
    with subp.Popen(args, stdout=subp.PIPE) as proc:
        output = proc.stdout.read().decode('utf-8', 'ignore')
    print(output)

    # добавляем в html файл параметры для красивого отображения скобочек
    with open(targetpath, 'r', encoding='utf-8') as file:
        html = file.read()
        html = html.replace('class="MathClass-open">', 'class="MathClass-open" stretchy="false">')
        html = html.replace('class="MathClass-close">', 'class="MathClass-close" stretchy="false">')
    with open(targetpath, 'w', encoding='utf-8') as file:
        file.write(html)

    # очищаем текущую директорию от временных файлов
    logging.info('Удаляем временные файлы для ' + sourcepath + '...')
    # удаляем временную директорию
    shutil.rmtree(tempdir)

def tex_substitutions2html():
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
    with Pool(int(config.get('GENERAL', 'converter_threads_count'))) as p:
        print(p.starmap(tex2html, zip(src_lst, trgt_lst)))
    logging.info('Файлы вариантов сконвертированы в HTML!')

def mergedTex2HtmlWithSlicing(merged_tex_file):
    '''
    Конвертирует объединенный TeX файл в HTML.
    После конвертации разбивает его на множество мелких html файлов, из которых он состоит.

    На вход ожидает путь к TeX файлу, содержащим множество задач.
    Одна задача определяется набором из 2 окружений "problem" и "answer", идущих друг за другом.
    Конвертирует этот файл в его html версию средствами make4ht (функция "tex2html").
    Затем синтаксически анализирует DOM, идентифицирует искомые задачи и создает для каждой задачи
    свой набор html для формулировки условия и решения.

    Ожидается, что merged файл лежит в директории с названием "tex".
    Результирующие файлы будут расположены в директории "html", лежащей рядом с "tex".
    '''
    # В результирующем html файле есть комментарии, показывающие соответствие строчки в исходном tex файле.
    # Благодаря этому достаточно проанализировать teх файл и определить номера строчек,
    # соответствующие началам окружений. Дальше мы просто вырезаем из html нужные куски.

    html_directory = os.path.join(os.path.dirname(os.path.dirname(merged_tex_file)), 'html')
    if not os.path.exists(html_directory):
        os.makedirs(html_directory)

    # конвертируем tex в html
    merged_html_file = os.path.join(html_directory, 'substitutions_merged.html')
    tex2html(
        sourcepath=merged_tex_file,
        targetpath=merged_html_file
    )

    with open(merged_tex_file, 'r', encoding='utf-8') as file:
        source_tex = file.read()

    w = LatexWalker(source_tex)
    (nodelist, pos, len_) = w.get_latex_nodes(pos=0)

    problems_pos = []
    solutions_pos = []

    for node in nodelist:
        if node.isNodeType(LatexEnvironmentNode) and node.environmentname == 'document':
            for node in node.nodelist:
                if node.isNodeType(LatexEnvironmentNode):
                    if node.environmentname == 'problem':
                        problems_pos.append(node.pos)
                    elif node.environmentname == 'solution':
                        solutions_pos.append(node.pos)

    # количество символов в каждой строке
    size_lines = [len(line) for line in source_tex.split('\n')]

    acc = 0
    lines_pos = []
    for size in size_lines:
        lines_pos.append(acc)
        acc += size + 1

    def find_line(pos, line_start=0):
        for cur_line, cur_pos in enumerate(lines_pos[line_start:]):
            if cur_pos == pos:
                return cur_line + line_start + 1
            elif cur_pos > pos:
                break
        return cur_line + line_start + 1

    # получить из HTML код, соответствующий промежутку между 2-мя заданными
    # строчкам исходного TeX файла
    with open(merged_html_file, 'r', encoding='utf-8') as file:
        source_html = file.read()

    # список строк, отраженных в html файле
    html_lines = list(map(int, re.findall('<!-- l. (.*?) -->', source_html)))
    if len(html_lines) == 0:
        print(merged_html_file + ' - не найдено html данных задач!')
        return

    def find_right_closest_line_in_html(line_number, start_line=0):
        for i, cur_line in enumerate(html_lines[start_line:]):
            if cur_line >= line_number:
                return cur_line
            else:
                continue
        #if start_line < len(html_lines):
        return cur_line
        #else:
        #    return html_lines[-1]

    def extract_html(first_env_startline, second_env_startline=None):
        if first_env_startline is None:
            start_pos = 0
        else:
            # стартовая позиция - это ближайшая справа строка в html
            start_key = '<!-- l. ' + str(find_right_closest_line_in_html(first_env_startline)) + ' -->'
            start_pos = source_html.find(start_key) + len(start_key)
        if second_env_startline is None:
            end_key = '</body>'
            end_pos = source_html.find(end_key)
            return source_html[start_pos:end_pos]
        else:
            end_key = '<!-- l. ' + str(find_right_closest_line_in_html(second_env_startline)) + ' -->'
            end_pos = source_html.find(end_key) + len(end_key)
            return source_html[start_pos:end_pos - len(end_key)]

    solution_line = 0
    tasks = list(zip(problems_pos, solutions_pos))
    problems_html = []
    solutions_html = []
    for number, task_pos in enumerate(tasks):
        (problem_pos, solution_pos) = task_pos
        problem_line = find_line(pos=problem_pos, line_start=solution_line)
        solution_line = find_line(pos=solution_pos, line_start=problem_line - 1)

        problem_html = extract_html(problem_line, solution_line)
        problems_html.append(problem_html)

        if number < len(tasks) - 1:
            solution_html = extract_html(solution_line,
                                         find_line(pos=tasks[number + 1][0], line_start=solution_line))
        else:
            solution_html = extract_html(solution_line, None)
        solutions_html.append(solution_html)

    # сохраняем разбиение merged файла
    for i, task in enumerate(zip(problems_html, solutions_html)):
        (problem, solution) = task

        # cохраняем файл без решения
        dst_file = os.path.join(html_directory, 'substitution_' + str(i + 1) + '_problem.html')
        with open(dst_file, 'w', encoding='utf-8') as file:
            file.write(problem)

        # сохраняем файл с решением
        dst_file = os.path.join(html_directory, 'substitution_' + str(i + 1) + '_solution.html')
        with open(dst_file, 'w', encoding='utf-8') as file:
            file.write(solution)


def tex_substitutions2html_optimized(folder='bank'):
    '''
    Конвертирует TeX файлы подстановок в HTML оптимизированным способом за счет использования merged файла.
    Благодаря этому множество файлов подстановок данной задачи конвертируются в html за 1 проход.
    '''
    folder = os.path.abspath(os.path.join(folder))
    src_lst = glob.glob(
        os.path.join(folder, '**', 'substitutions', 'tex', 'substitutions_merged.tex'),
        recursive=True
    )
    with Pool(int(config.get('GENERAL', 'converter_threads_count'))) as p:
        print(p.map(mergedTex2HtmlWithSlicing, src_lst))
    logging.info('Файлы подстановок сконвертированы в HTML!')


def count_tasks(folder='bank'):
    '''
    Считает количество задач, находящихся в данной папке.
    Уровень вложенности папок не ограничен.
    '''
    return len(glob.glob(os.path.join(folder, '**', 'parametrizator.ipynb'), recursive=True))


def count_tex_substitutions(folder='bank'):
    '''
    Считает количество tex файлов подстановок, находящихся в данной папке.
    Уровень вложенности папок не ограничен.
    '''
    return len(glob.glob(os.path.join(folder, '**', 'substitutions', 'tex', 'substitution_*.tex'), recursive=True))


def count_html_substitutions(folder='bank'):
    '''
    Считает количество html файлов подстановок, находящихся в данной папке.
    Уровень вложенности папок не ограничен.
    '''
    return len(glob.glob(os.path.join(folder, '**', 'substitutions', 'html', 'substitution_*_problem.html'),
                         recursive=True))

def show(subs_data={}, template_name='template.tex'):
    '''
    Выводит задачу с подставленными значениями сконвертированную из TeX в HTML.
    '''
    # директория, в которой располагается данный ноутбук
    # если файл шаблона не найден
    if not os.path.exists(template_name):
        return 'Шаблон задачи не найден!'
    # создаем директорию для хранения результатов
    results_directory = os.path.join(os.getcwd(), 'tmp')
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)
    # подставляем переданные значения
    logging.info(f'Подставляем переданные значения в шаблон "{template_name}"...')
    subs_file_name = datetime.now().strftime("subs_%d.%m.%Y_%H-%M-%S.tex")
    targetpath_tex = os.path.join(results_directory, subs_file_name)
    latex_subs(template_name, targetpath_tex, subs_data)
    targetpath_html = os.path.splitext(targetpath_tex)[0] + '.html'
    # конвертируем в hmtl
    tex2html(
        sourcepath=targetpath_tex,
        targetpath=targetpath_html
    )

    # отдаем содержимое html
    with open(targetpath_html, 'r', encoding='utf-8') as file:
        src = file.read()
    return HTML(src)
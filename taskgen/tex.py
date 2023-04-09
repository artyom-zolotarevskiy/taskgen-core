import os.path
import glob
import numpy as np
import logging
import json
import shutil
from tabulate import tabulate
from taskgen.functions import copy_taskgen_sty, copy_taskgen_4ht, replace_files


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
        if type(params[key]) is list:
            if params[key][0] == 'DataSet':
                subs_value = os.path.basename(params[key][1])
            elif params[key][0] == 'Image':
                subs_value = r'''\begin{figure}[h!]
    \centering
    \includegraphics[width=''' + params[key][3] + ''']{''' + os.path.basename(params[key][1]) + '''}'''
                if params[key][2] != '':
                    subs_value += '''
    \caption{''' + params[key][2] + '''}'''
                subs_value += '''
\end{figure}'''
                src_path = params[key][1]
                dst_path = os.path.join(
                        os.path.dirname(to_file),
                        os.path.basename(params[key][1])
                    )
                try:
                    shutil.copy(src_path, dst_path)
                except shutil.SameFileError:
                    pass
            else:
                subs_value = str(params[key][1])
        else:
            subs_value = str(params[key])
        if 'begin{array}' in subs_value:
            subs_value = '$' + subs_value + '$'
        src = src.replace('\subs{' + key + '}', subs_value)
    # сохраняем файл
    with open(to_file, 'w', encoding='utf-8') as file:
        file.write(src)


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
    problem_cnt = 1
    for substitution_file in structure:
        # добавляем задачу в тело билета
        substitution_body = get_tex_body(substitution_file)

        substitution_body = replace_files(
            substitution_path=substitution_file,
            string=substitution_body,
            variant_number=variant_number,
            problem_number=problem_cnt,
            copy_file=True)

        variant_src += substitution_body + '\n'

        problem_cnt += 1
    variant_src += r'\end{document}'
    # сохраняем билет
    results_directory = os.path.join(os.getcwd(), 'results', 'tex')
    os.makedirs(results_directory, exist_ok=True)
    with open(os.path.join(results_directory, f'{prefix}{str(variant_number)}.tex'), 'w', encoding='utf-8') as file:
        file.write(variant_src)

    # копируем taskgen.sty из настроек в данную директорию
    copy_taskgen_sty(folder=results_directory, logging_enabled=False)
    # копируем taskgen.4ht из настроек в данную директорию
    copy_taskgen_4ht(folder=results_directory, logging_enabled=False)

    logging.info('Билет № ' + str(variant_number) + ' в TeX формате создан!')

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
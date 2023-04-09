import os.path
import glob
import logging
import shutil
import json
from datetime import datetime
from taskgen.config import config, __SETTINGS_FOLDER__
from taskgen.functions import copy_template_files, replace_files

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

        problem_html_src = replace_files(
            substitution_path=substitution_tex_file,
            string=problem_html_src,
            variant_number=variant_number,
            problem_number=problem_number + 1,
            copy_file=False)

        # добавляем задачу в тело билета
        variant_src += task_template
        variant_src = variant_src.replace('${problem_number}', str(problem_number + 1))
        variant_src = variant_src.replace('${problem_max_score}', '10')
        variant_src = variant_src.replace('${problem_src}', problem_html_src)

        # добавляем решение к задаче
        if with_solution:
            solution_html_src = replace_files(
                substitution_path=substitution_tex_file,
                string=solution_html_src,
                variant_number=variant_number,
                problem_number=problem_number + 1,
                copy_file=False)
            variant_src = variant_src.replace('${solution_src}', solution_html_src)

            answer_html_src = replace_files(
                substitution_path=substitution_tex_file,
                string=answer_html_src,
                variant_number=variant_number,
                problem_number=problem_number + 1,
                copy_file=False)
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

    # копируем файлы шаблона
    copy_template_files(results_directory)

    logging.info('Билет № ' + str(variant_number) +
                 ' в HTML формате' +
                 (' с решением ' if with_solution else ' без решения ') +
                 'создан!')


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
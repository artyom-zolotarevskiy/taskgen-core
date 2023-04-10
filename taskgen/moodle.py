import os.path
import glob
import logging
import re
from taskgen.config import config, __SETTINGS_FOLDER__

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
        # путь к соответствующему html файлу условия
        problem_html_file = os.path.join(os.path.dirname(os.path.dirname(substitution_tex_file)),
                                         'html',
                                         os.path.splitext(os.path.basename(substitution_tex_file))[
                                             0] + '_problem.html')
        with open(problem_html_file, 'r', encoding='utf-8') as file:
            problem_html_src = file.read()

        # заменяем названия датасетов
        # встраиваем изображения
        # встраиваем датасеты

        # путь к соответствующему html файлу ответов
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
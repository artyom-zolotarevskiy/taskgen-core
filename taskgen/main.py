import os.path
import glob
import random
from shutil import rmtree
import logging
from datetime import datetime
from multiprocessing import Pool
from IPython.display import HTML
from taskgen.config import config, __SETTINGS_FOLDER__
from taskgen.converters import *
from taskgen.functions import *
from taskgen.tex import *
from taskgen.html import *
from taskgen.moodle import *

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
        rmtree(data_directory)
    os.makedirs(data_directory)

    # добавляем код, запукающий функцию GET нужное количество раз
    # и сохранящий папаметризацию в json
    parametrizer_script += '\n\nimport json\n'
    parametrizer_script += 'class NpEncoder(json.JSONEncoder):\n    def default(self, obj):\n        if isinstance(obj, np.integer):\n            return int(obj)\n        if isinstance(obj, np.floating):\n            return float(obj)\n        if isinstance(obj, np.ndarray):\n            return obj.tolist()\n        return super(NpEncoder, self).default(obj)\n'
    parametrizer_script += 'parametrizer_result = []\n'
    parametrizer_script += f"for i in range({n}):\n\tparametrizer_result.append({config.get('GENERAL', 'parameterizer_function_name')}())\n"
    parametrizer_script += "with open('data.json', 'w', encoding='utf-8') as file:\n\tjson.dump(parametrizer_result, file, cls=NpEncoder)\n"

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
    folder = os.path.abspath(folder)
    for ipynb_file in glob.glob(os.path.join(folder, '**', '*.ipynb'), recursive=True):
        task_folder = os.path.dirname(ipynb_file)
        # создаем директорию для хранения файлов подстановок
        substitutions_directory = os.path.join(task_folder, 'substitutions', 'tex')
        if os.path.exists(substitutions_directory):
            rmtree(substitutions_directory)
        os.makedirs(substitutions_directory)
        html_subs_folder = os.path.join(os.path.dirname(substitutions_directory), 'html');
        if os.path.exists(html_subs_folder):
            rmtree(html_subs_folder)
        # копируем taskgen.sty из настроек в данную директорию
        copy_taskgen_sty(folder=substitutions_directory, logging_enabled=False)
        # копируем taskgen.4ht из настроек в данную директорию
        copy_taskgen_4ht(folder=substitutions_directory, logging_enabled=False)
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


def make_variants(folder=config.get('GENERAL', 'bank_folder'), size=1, start=1):
    '''
    Собирает файлы вариантов на основе сгенерированных подстановок.
    :param folder: Папка, в которой лежат задачи с подстановками.
    :param size: Количество создаваемых вариантов.
    :param start: Начало нумерации вариантов.
    '''
    results_directory = os.path.join(os.getcwd(), 'results')
    if os.path.exists(results_directory):
        rmtree(results_directory)
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

    # копируем ресурсы шаблона
    copy_template_files(folder=os.path.join(os.path.dirname(results_directory), 'html'))

    # создаем объединенный файл вариантов в формате Moodle XML
    merge_moodle_variants()

    logging.info('Файлы вариантов сгенерированы!')


def show(subs_data={}, remove_tmp_folder=True):
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
    # копируем js файлы шаблона
    copy_template_files(folder=results_directory, extensions=['js'])

    # подставляем переданные значения
    logging.info(f'Подставляем переданные значения в шаблон "{template_path}"...')
    subs_file_name = datetime.now().strftime("subs_%d.%m.%Y_%H-%M-%S.tex")
    targetpath_tex = os.path.join(results_directory, subs_file_name)
    latex_subs(template_path, targetpath_tex, subs_data)
    targetpath_html = os.path.splitext(targetpath_tex)[0] + '.html'
    # конвертируем в hmtl
    if tex2html(
            sourcepath=targetpath_tex,
            targetpath=targetpath_html,
            remove_tmp_folder=remove_tmp_folder
    ):
        # отдаем содержимое html
        with open(targetpath_html, 'r', encoding='utf-8') as file:
            src = file.read()
        return HTML('<base target="_self" href="./tmp/">' + src)


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
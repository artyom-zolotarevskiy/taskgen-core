import io
import os
import json
import base64
import shutil
import logging
import shlex
import subprocess as subp
import time
from binascii import crc32
from PyPDF2 import PdfFileMerger, PdfFileReader
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from webdriver_manager.chrome import ChromeDriverManager
from taskgen.config import config, __SETTINGS_FOLDER__
from taskgen.functions import *
from taskgen.tex import merge_tex
from bs4 import BeautifulSoup

def __send_devtools(driver, cmd, params={}):
    resource = "/session/%s/chromium/send_command_and_get_result" % driver.session_id
    url = driver.command_executor._url + resource
    body = json.dumps({'cmd': cmd, 'params': params})
    response = driver.command_executor._request('POST', url, body)
    if response.get('status'):
        raise Exception(response.get('value'))
    return response.get('value')


def __latex_is_loaded(driver):
    state = driver.execute_script('return window.mathjax_loaded;')
    return state == True

def html2pdf(source=os.path.join(os.getcwd(), 'html'),
             output=os.path.join(os.getcwd(), 'pdf'),
             in_one_page=False,
             scale_step=0.025):
    '''
    :param source: путь к папке с html файлами
    :param output: путь к папке для сохранения результатов
    :param in_one_page:
    :param scale_step: шаг, с которым мы подбираем масштаб страницы
    :return:
    '''
    # создаем папку для сохранения результатов, если нужно
    if not os.path.exists(output):
        os.makedirs(output)

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    for filename in sorted(
        filter(
            lambda filename:
                filename.endswith('.html') and 'merged' not in filename and any(map(str.isdigit, filename)),
            os.listdir(source)
        ),
        key=lambda filename: int(''.join(symbol for symbol in filename if symbol.isdigit()))
    ):
        # открываем html файл
        print('Открываем файл:', filename)
        driver.get(f'file://{os.path.join(source, filename)}')

        print('Дожидаемся полной инициализации...')

        # дожидаемся загрузки страницы
        element = WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.TAG_NAME, 'body')))

        # дожидаемся полной инициализации LaTex на странице
        WebDriverWait(driver, 10).until(__latex_is_loaded)
        time.sleep(0.5)

        # получаем pdf
        print_options = {
            'scale': 1,
        }

        if in_one_page and 'with-solution' not in filename:
            print('Подбираем коэффициент масштабирования...')
            while 0.125 <= print_options['scale'] <= 1.975:
                result = __send_devtools(driver, "Page.printToPDF", print_options)
                result = base64.b64decode(result['data'])

                pdf_file = io.BytesIO(result)
                pdf_reader = PdfFileReader(pdf_file)
                num_pages = pdf_reader.numPages
                # print('При масштабировании {} кол-во страниц: {}'.format(print_options['scale'], num_pages))

                if num_pages == 1:
                    break
                else:
                    print_options['scale'] -= scale_step
        else:
            result = __send_devtools(driver, "Page.printToPDF", print_options)
            result = base64.b64decode(result['data'])

        # сохраняем pdf
        print('Сохраняем файл...', '\n')
        with open(os.path.join(output, os.path.splitext(filename)[0] + '.pdf'), 'wb') as file:
            file.write(result)

    driver.close()
    print('Все html файлы в директории', source, 'сконвертированы в pdf!')

    # объединяем полученные файлы вариантов с решениями в один
    mergedObject = PdfFileMerger()
    for filename in sorted(
            filter(
                lambda filename: filename.endswith('.pdf') and
                                 not filename.endswith('merged.pdf') and
                                 not filename.endswith('-only-problem.pdf'),
                os.listdir(output)
            ),
            key=lambda filename: int(''.join(symbol for symbol in filename if symbol.isdigit()))
    ):
        mergedObject.append(PdfFileReader(os.path.join(output, filename)))
    mergedObject.write(os.path.join(output, 'variants_with_solution_merged.pdf'))

    # объединяем полученные файлы вариантов без решений в один
    mergedObject = PdfFileMerger()
    for filename in sorted(
            filter(
                lambda filename: filename.endswith('.pdf') and
                                 not filename.endswith('merged.pdf') and
                                 not filename.endswith('-with-solution.pdf'),
                os.listdir(output)
            ),
            key=lambda filename: int(''.join(symbol for symbol in filename if symbol.isdigit()))
    ):
        mergedObject.append(PdfFileReader(os.path.join(output, filename)))
    mergedObject.write(os.path.join(output, 'variants_only_problem_merged.pdf'))

    print('Все pdf файлы из директории', output, 'объединены!')


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
    tempdir = os.path.join(os.getcwd(), 'tmp', str(crc32(targetpath.encode('utf8'))))
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
    # копируем изображения во временную директорию
    for image_path in glob.glob(
            os.path.join(
                os.path.dirname(sourcepath),
                '*.pdf'
            )
    ):
        shutil.copyfile(
            image_path,
            os.path.join(
                tempdir,
                os.path.basename(image_path)
            )
        )
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

    # копируем js файлы шаблона в папку назначения
    copy_template_files(folder=os.path.dirname(targetpath), extensions=['js'])

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

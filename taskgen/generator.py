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
from pylatexenc.latexwalker import LatexWalker, LatexEnvironmentNode
import random
import subprocess as subp
from .html2pdf import html2pdf
import shlex
import shutil

def printlog(output = '', filename = 'log', onlyfile=False):
    if onlyfile == False:
        print(output)
    with open(filename + '_taskgen.log', 'a', encoding='utf-8') as logfile:
        logfile.write(output)
        logfile.write('\n')

# компилируем tex файл
def compile_file(filename, folder='./RESULTS/tex/'):
    filename = str(filename)
    basename_filename = os.path.basename(filename).replace('.tex', '').replace('_template', '')
    os.chdir(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
    try:
        # меняем активный каталог
        os.chdir(folder)

        # очищаем файл лога
        with open(basename_filename + '.log', 'w', encoding='utf-8') as logfile:
            logfile.write('')

        # очищаем директорию от прошлой компиляции
        files = glob.glob('./pythontex-files-' + basename_filename + '/*.*')
        for f in files:
            os.remove(f)

        # компилируем исходный файл
        printlog(f'Компилируем файл {os.path.join(folder, filename)}...', basename_filename)

        with open(os.path.basename(filename).replace('.tex', '') + '.tex', 'r', encoding='utf-8') as file:
            assert r'\usepackage[depythontex]{pythontex}' in str(file.read()), \
                    'Тех файл должен содержать в преамбуле след. строку: ' + r'\usepackage[depythontex]{pythontex}'

        with subp.Popen(['latexmk', filename], stdout=subp.PIPE) as proc:
            output = proc.stdout.read().decode('utf-8', 'ignore')
            printlog(output, basename_filename, True)
            assert 'Emergency stop' not in output

        # выполняем код python из файла
        printlog('Выполняем python код...', basename_filename)
        with subp.Popen(['pythontex', filename], stdout=subp.PIPE) as proc:
            output = proc.stdout.read().decode('utf-8', 'ignore')
            printlog(output, basename_filename, True)
            assert '0 error(s), 0 warning(s)' in output, 'Не удалось выполнить python код.'
            #if debug:
            #print(output)

        printlog('Еще раз компилируем...\n', basename_filename)
        with subp.Popen(['latexmk', filename], stdout=subp.PIPE) as proc:
            output = proc.stdout.read().decode('utf-8', 'ignore')
            printlog(output, basename_filename, True)
            assert 'Emergency stop' not in output
            #if debug:
            #print(output)

        # с помощью depythontex получаем тех файл без кода, но с результатом его выполнения (со вставленными переменными)
        printlog('Получаем версию файла без python...', basename_filename)
        cmd = ['depythontex', filename]
        with subp.Popen(cmd, stdout=subp.PIPE) as proc:
            output = proc.stdout.read().decode('utf-8', 'ignore')
            printlog(output, basename_filename, True)
            #if debug:
            #print(output)

        # сохраняем полученный файл варианта
        printlog('Сохраняем версию файла без python...\n', basename_filename)
        with open(basename_filename + '_data.tex', 'w', encoding='utf-8') as file:
            file.write(output)

        # создаем промежуточный tex файл в котором определяем номер билета
        printlog('Создаем промежуточный tex файл для передачи параметров в оригинальный документ...', basename_filename)
        with open(basename_filename + '_answer.tex', 'w', encoding='utf-8') as file:
            template = r'\newcommand\biletnumber{' + basename_filename + r'}\input{' + basename_filename + r'_data}'
            file.write(template)

        # создаем итоговый html файл с решением
        printlog('Создаем html файл с решением...', basename_filename)
        cmd = 'htlatex ' + basename_filename + '_answer.tex "../../taskgen/ht5mjlatex.cfg, charset=utf-8" " -cunihtf -utf8"'
        args = shlex.split(cmd)
        with subp.Popen(args, stdout=subp.PIPE) as proc:
            output = proc.stdout.read().decode('utf-8', 'ignore')
            printlog(output, basename_filename, True)

        # добавляем в html файл параметры для красивого отображения скобочек
        with open(basename_filename + '_answer.html', 'r', encoding='utf-8') as file:
            html = file.read()
            html = html.replace('class="MathClass-open">', 'class="MathClass-open" stretchy="false">')
            html = html.replace('class="MathClass-close">', 'class="MathClass-close" stretchy="false">')
        with open(basename_filename + '_answer.html', 'w', encoding='utf-8') as file:
            file.write(html)

        # создаем выходную папку, если нужно
        problem_with_answer_directory = os.path.join('..', '..', 'RESULTS', 'html', 'problems_with_answers')
        if not os.path.exists(problem_with_answer_directory):
            os.makedirs(problem_with_answer_directory)

        # переносим полученный html файл в нужную папку
        printlog('Переносим html файл в нужную папку...', basename_filename)
        os.rename(basename_filename + '_answer.html', \
                  os.path.join(problem_with_answer_directory, basename_filename) + '_answer.html')

        # переносим файл со стилями
        printlog('Переносим файл со стилями в нужную папку...', basename_filename)
        os.rename(basename_filename + '_answer.css', \
                  os.path.join(problem_with_answer_directory, basename_filename) + '_answer.css')

        printlog(f'Файл {os.path.join(folder, filename)} с блоками решений скомпилирован!\n', basename_filename)

        # создаем промежуточный tex файл в котором определяем номер билета и указывем, что решение выводить не нужно
        printlog('Создаем промежуточный tex файл для передачи параметров в оригинальный документ...', basename_filename)
        with open(basename_filename + '_problem.tex', 'w', encoding='utf-8') as file:
            template =  r'\newcommand\biletnumber{' + basename_filename + \
                        r'}\def\hidesolution{}\input{' + basename_filename + '_data}'
            file.write(template)

        # создаем итоговый файл без решения
        printlog('Создаем html файл без решения...', basename_filename)
        cmd = 'htlatex ' + basename_filename + '_problem.tex "../../taskgen/ht5mjlatex.cfg, charset=utf-8" " -cunihtf -utf8"'
        args = shlex.split(cmd)
        with subp.Popen(args, stdout=subp.PIPE) as proc:
            output = proc.stdout.read().decode('utf-8', 'ignore')
            printlog(output, basename_filename, True)

        # добавляем в html файл параметры для красивого отображения скобочек
        with open(basename_filename + '_problem.html', 'r', encoding='utf-8') as file:
            html = file.read()
            html = html.replace('class="MathClass-open">', 'class="MathClass-open" stretchy="false">')
            html = html.replace('class="MathClass-close">', 'class="MathClass-close" stretchy="false">')
        with open(basename_filename + '_problem.html', 'w', encoding='utf-8') as file:
            file.write(html)

        # переносим полученный html файл в нужную папку
        printlog('Переносим html файл в нужную папку...', basename_filename)
        os.rename(basename_filename + '_problem.html',
                  os.path.join('..', '..', 'RESULTS', 'html', \
                               'only_problems', basename_filename + '_problem.html'))

        # переносим файл со стилями
        printlog('Переносим файл со стилями в нужную папку...', basename_filename)
        os.rename(basename_filename + '_problem.css',
                  os.path.join('..', '..', 'RESULTS', 'html', \
                               'only_problems', basename_filename + '_problem.css'))

        printlog(f'Файл {os.path.join(folder, filename)} без блоков решений скомпилирован!\n', basename_filename)

        # создаем выходную папку, если нужно
        only_problems_directory = os.path.join('..', '..', 'RESULTS', 'html', 'only_problems')
        if not os.path.exists(only_problems_directory):
            os.makedirs(only_problems_directory)

        # переносим картинки в нужную папочку
        printlog('Копируем изображения (если есть) в нужные папки...\n', basename_filename)
        images_files = glob.glob('*.png')
        for imagepath in images_files:
            shutil.copyfile(imagepath, os.path.join(only_problems_directory, imagepath))
            shutil.copyfile(imagepath, os.path.join(only_problems_directory, imagepath))
    except BaseException as e:
        # сохраняем посление 50 строк файла лога
        with open(basename_filename + '_taskgen.log', 'r', encoding='utf-8') as logfile:
            last_log_string = ''.join(logfile.readlines()[-50:])

        if str(e) != '':
            printlog('', basename_filename)
            printlog(str(e), basename_filename)
        printlog('', basename_filename)
        printlog(f'Ошибка компиляции! Скорее всего файл {os.path.join(folder, filename)} содержит ошибки!', basename_filename)
        printlog(f'Вывод терминальных команд смотри в {os.path.join(folder, basename_filename)}_taskgen.log', basename_filename)
        print('\nПоследние 50 строк файла лога:\n')
        print('=' * 25)
        print(last_log_string)
        print('=' * 25)

    # меняем активный каталог
    os.chdir(os.path.join('..', '..'))

    print('Конец блока компиляции!')

# парсит tex файл с задачками
def parse_problems(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            source = file.read()

        w = LatexWalker(source)
        (nodelist, pos, len_) = w.get_latex_nodes(pos=0)

        # список со спарсенными задачами, каждая ячейка будет содержать код, задачу и решение
        problems_list = []

        i = -1
        # просто обходим все ноды
        for node in nodelist:
            if node.isNodeType(LatexEnvironmentNode) and node.environmentname == 'document':
                for node in node.nodelist:
                    if node.isNodeType(LatexEnvironmentNode):
                        if node.environmentname == 'pycode':
                            problems_list.append(node.latex_verbatim());
                            i += 1
                        elif node.environmentname == 'problem':
                            problems_list[i] = [problems_list[i], node.latex_verbatim()]
                        elif node.environmentname == 'solution':
                            problems_list[i] = [*problems_list[i], node.latex_verbatim()]
        return problems_list

# генерирует исходный файл нового варианта на основе папок с задачами
def gen_variant(variant_number=1, deterministic=False, task_number_for_deterministic=0):
    # создаем выходную папку, если нужно
    directory = './RESULTS/tex/'
    if not os.path.exists(directory):
        os.makedirs(directory)

    print('Создаем шаблон билета № ' + str(variant_number) + '...')
    # генерируем тело билета
    body = '';
    # обходим каждый вопрос
    for question_folder in sorted(glob.glob('./QUESTIONS/Q*'), key=lambda x: int(os.path.basename(x)[1:])):
        question_number = int(os.path.basename(question_folder)[1:])
        # список всех задач по данному вопросу
        question_problems_list = []
        # парсим все темы
        for problems_file in glob.glob(os.path.join(question_folder, '*.tex')):
            if problems_file.endswith('_problem.tex') or problems_file.endswith('_answer.tex') or problems_file.endswith('_data.tex'):
                continue
            question_problems_list.extend(parse_problems(problems_file))

        if len(question_problems_list) == 0:
            continue

        # выбираем случайно одну задачку
        if deterministic == False:
            problem = random.choice(question_problems_list)
        else:
            task_index_in_file = task_number_for_deterministic % len(question_problems_list)
            problem = question_problems_list[task_index_in_file]

        # обновляем номер задачи для корректной генерации обоих файлов
        problem[0] = problem[0].replace("task_id = '1'", "task_id = '" + str(variant_number) + '-' + str(question_number) + "'")
        # добавляем номер задачи в текст согласно нумерации нового файла
        problem[1] = problem[1][:16] + r'\textbf{' + str(question_number) + '. (10)}' + '\n' + problem[1][16:]
        # вставляем данные задачи в шаблон варианта
        body += '\n\n'.join(problem) + '\n\n'

    # читаем шаблон
    with open('./taskgen/variant_template.tex', 'r', encoding='utf-8') as file:
        template = file.read()

    # вставляем в шаблон сгенерированное тело
    template = template.replace('%<body>', body)

    # сохраняем шаблон задачи
    with open(directory + str(variant_number) + '_template.tex', 'w', encoding='utf-8') as file:
        file.write(template)

    print('Шаблон билета № ' + str(variant_number) + ' сохранен!')

def generate_exam(start_numeration=1, variant_count=1, deterministic=False):
    # очищаем выходные директории от лишних файлов
    for files in [glob.glob('./RESULTS/**/**/*'), glob.glob('./RESULTS/tex/*'), glob.glob('./RESULTS/DataSets/*')]:
        for f in files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.listdir(f) == []:
                os.rmdir(f)
    # генерируем варианты
    for variant_number in range(start_numeration, start_numeration + variant_count):
        if deterministic:
            gen_variant(variant_number, True, start_numeration - variant_number)
        else:
            gen_variant(variant_number)
        compile_file(str(variant_number) + '_template.tex', folder='./RESULTS/tex/')

    # сохраняем сгенерированные html в pdf
    print('Сохраняем сгенерированные html файлы в pdf...')
    html2pdf(os.path.join(os.getcwd(), 'RESULTS', 'html', 'only_problems'), \
             os.path.join(os.getcwd(), 'RESULTS', 'pdf', 'only_problems'), in_one_page=True)
    # объединяем все pdf в один файл
    html2pdf(os.path.join(os.getcwd(), 'RESULTS', 'html', 'problems_with_answers'), \
             os.path.join(os.getcwd(), 'RESULTS', 'pdf', 'problems_with_answers'), in_one_page=False)

    # очищаем текущую директорию от временных файлов
    with subp.Popen(['latexmk', '-C'], stdout=subp.PIPE) as proc:
        output = proc.stdout.read()

    # {"aux", "xref", "tmp", "4tc", "4ct", "idv", "lg","dvi", "log"}

    print('\nГотово!')
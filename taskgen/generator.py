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

def printlog(output = '', filename = 'log', onlyfile=False):
    if onlyfile == False:
        print(output)
    with open(filename + '_taskgen.log', 'a', encoding='utf-8') as logfile:
        logfile.write(output)
        logfile.write('\n')

def printerror(filename, folder, e):
    basename_filename = os.path.basename(filename).replace('.tex', '')
    # сохраняем последние 50 строк файла лога
    with open(basename_filename + '_taskgen.log', 'r', encoding='utf-8') as logfile:
        last_log_string = ''.join(logfile.readlines()[-50:])

    if str(e) != '':
        printlog('', basename_filename)
        printlog(str(e), basename_filename)
    printlog('', basename_filename)
    printlog(f'Ошибка компиляции! Скорее всего файл {os.path.join(folder, basename_filename)}.tex содержит ошибки!', basename_filename)
    printlog(f'Вывод терминальных команд смотри в {os.path.join(folder, basename_filename)}_taskgen.log', basename_filename)
    print('\nПоследние 50 строк файла лога:\n')
    print('=' * 25)
    print(last_log_string)
    print('=' * 25)

# компилируем tex файл
def compile_tex(filename, folder='./results/tex/'):
    # имя файла без расширения
    basename_filename = os.path.basename(filename).replace('.tex', '')
    # заходим в корневой каталог
    os.chdir(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
    try:
        # заходим в папку с файлом
        os.chdir(folder)

        # очищаем файл лога
        with open(basename_filename + '.log', 'w', encoding='utf-8') as logfile:
            logfile.write('')

        # очищаем директорию от прошлой компиляции
        files = glob.glob('./pythontex-files-' + basename_filename + '/*.*')
        for f in files:
            os.remove(f)

        # компилируем исходный файл
        printlog(f'Компилируем файл "{os.path.join(folder, filename)}"...', basename_filename)

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

        printlog('Еще раз компилируем...', basename_filename)
        with subp.Popen(['latexmk', filename], stdout=subp.PIPE) as proc:
            output = proc.stdout.read().decode('utf-8', 'ignore')
            printlog(output, basename_filename, True)
            assert 'Emergency stop' not in output

        print('Исходный  TeX файл скомпилирован!')
    except BaseException as e:
        printerror(filename, folder, e)

def remove_python(filename, folder='./results/tex/'):
    # имя файла без расширения
    basename_filename = os.path.basename(filename).replace('.tex', '')
    # с помощью depythontex получаем тех файл без кода, но с результатом его выполнения (со вставленными переменными)
    printlog('Получаем версию файла без python...', basename_filename)
    cmd = ['depythontex', filename]
    with subp.Popen(cmd, stdout=subp.PIPE) as proc:
        output = proc.stdout.read().decode('utf-8', 'ignore')
        printlog(output, basename_filename, True)

    # сохраняем полученный файл варианта
    printlog('Сохраняем версию файла без python...', basename_filename)
    path = basename_filename + '_data.tex'
    with open(path, 'w', encoding='utf-8') as file:
        file.write(output)

    print(f'Успешно создана версия TeX файл не содержащая код python - "{path}"!')

    return os.getcwd() + '/' + path

def convert_tex_to_moodle_xml(path_to_file):
    with open(path_to_file, 'r', encoding='utf-8') as file:
        source = file.read()

    w = LatexWalker(source)
    (nodelist, pos, len_) = w.get_latex_nodes(pos=0)

    # список со спарсенными задачами, каждая ячейка будет содержать код, задачу, решение и ответы
    problems_list = []

    i = -1
    # просто обходим все ноды
    for node in nodelist:
        if node.isNodeType(LatexEnvironmentNode) and node.environmentname == 'document':
            for node in node.nodelist:
                if node.isNodeType(LatexEnvironmentNode):
                    if node.environmentname == 'problem':
                        print('Получаем название задачи...')
                        name = node.nodelist[0].chars
                        left_separator = '[name="';
                        right_separator = '"]';
                        name = name[name.find(left_separator) + len(left_separator): name.find(right_separator)]
                        if (len(name) == 0):
                            print('Необходимо указать название задачи!')
                            return False
                        print('Название задачи: "' + name + '"')
                        problems_list.append([name, node.latex_verbatim()])
                        i += 1
                    elif node.environmentname == 'solution':
                        print('Получаем ответы...')
                        # обходим всех детей, ищем LatexMacroNode с macroname=answer
                        # и получаем параметры ответов
                        answers = []
                        flag = False
                        j = -1
                        for subnode in node.nodelist:
                            if subnode.isNodeType(LatexMacroNode) and subnode.macroname == 'answer':
                                flag = True
                                answers.append([])
                                j += 1
                            elif subnode.isNodeType(LatexGroupNode) and flag:
                                answers[j].append(subnode.nodelist[0].chars)
                            else:
                                flag = False

                        # проверяем, что для ответов указаны все параметры
                        for answer in answers:
                            if len(answer) != 4:
                                print("Необходимо указать все обязательные параметры для ответов!")
                                return False

                        problems_list[i] = [*problems_list[i], node.latex_verbatim(), answers]

    # имя файла без расширения
    basename_filename = os.path.basename(path_to_file).replace('.tex', '')

    # заходим в директорию файла
    if (not os.path.isabs(os.path.dirname(path_to_file))):
        os.chdir(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
    os.chdir(os.path.dirname(path_to_file))

    # создаем версию tex файла, не содержащую ответов
    print('Создаем версию tex файла, содержащую подстановки для будущих полей ввода ответов...')
    with open(basename_filename + '_placeholders.tex', 'w', encoding='utf-8') as file:
        template = r'\newcommand\setplaceholders{}\input{' + basename_filename + '}'
        file.write(template)

    placeholder_path = os.getcwd() + '/' + basename_filename + '_placeholders.tex'

    print("Конвертируем TeX файл в HTML на базе MathJax...")
    cmd = 'make4ht "' + placeholder_path + '" "mathjax"'
    args = shlex.split(cmd)
    with subp.Popen(args, stdout=subp.PIPE) as proc:
        output = proc.stdout.read().decode('utf-8', 'ignore')
        printlog(output, basename_filename, True)

    print("Получаем тело HTML документа...")
    with open(basename_filename + '_placeholders.html', 'r', encoding='utf-8') as file:
        html = file.read()
        soup = BeautifulSoup(html, features="html.parser")
        body = str(soup.body).replace('<body>', '').replace('</body>', '')

    print("Получаем стили документа...")
    with open(basename_filename + '_placeholders.css', 'r', encoding='utf-8') as file:
        css = file.read()
        body = f'''
        <script>
            const style = document.createElement("style");
            style.textContent = `
            ''' + '''
            .que.formulas .formulas_number {
                width: 70px;
            }
            ''' + f'''
            {css}`;
            document.head.appendChild(style);
        </script>\n\n''' + body

    print("Добавляем JavaScript код для поддержки запятой в качестве дробного разделителя...")
    body += '''
        <script src="https://code.jquery.com/jquery-3.6.1.min.js" integrity="sha256-o88AwQnZB+VDvE9tvIXrMQaPlFFSUTR+nldQm1LuPXQ=" crossorigin="anonymous"></script>
        <script>
            $(window).on("load", function() {
                formula_types = ["formulas_number", "formulas_numeric"]; //This script only works for these types of formula questions
                var nb_types = formula_types.length;
                // HIDE INVALID SYNTAX RED TRIANGLE
                $("span.formulas_input_warning_outer").css("display", "none");
                setTimeout(() => {
                    $("span.formulas_input_warning_outer").css("display", "none");
                }, 1000);
    
                // DISPLAY VARIABLES IN THE TEXT
                //To use this, just enclose your variables in a <span class="variablestocomma">...</span>
                //There is no need to do this for TeX variables since it will be done automatically (and properly).
                var i;
                var n = $(".variablestocomma").length;
                for (i = 0; i < n; i++) {
                    i = i.toString();
                    var strp = $(".variablestocomma:eq(" + i + ")").text();
                    var strc = strp.replace(/\./g, ',');
                    $(".variablestocomma:eq(" + i + ")").css("color", "#000");
                    $(".variablestocomma:eq(" + i + ")").text(strc);
                }
    
                // CLICKING THE CHECK BUTTON 			
                $('input[type="submit"]').on('click', function() {
                    var i;
                    for (type = 0; type < nb_types; type++) {
                        var n = $("input." + formula_types[type]).length;
                        for (i = 0; i < n; i++) {
                            i = i.toString();
                            var strc = $("input." + formula_types[type] + ":eq(" + i + ")").val();
                            var strp = strc.replace(/\,/g, '.');
                            $("input." + formula_types[type] + ":eq(" + i + ")").css("color", "#FFF");
                            $("input." + formula_types[type] + ":eq(" + i + ")").val(strp);
                        }
                    }
                });		
                
                $('input').on('keyup', function() {
                    $("span.formulas_input_warning_outer").css("display", "none");
                    // проверка на разделитель
                    // проверка на количество знаков после разделителя
                    // проверка на посторонние символы
                    var i;
                    for (type = 0; type < nb_types; type++) {
                        var n = $("input." + formula_types[type]).length;
                        for (i = 0; i < n; i++) {
                            i = i.toString();
                            var strc = $("input." + formula_types[type] + ":eq(" + i + ")").val();
                            var strp = strc.replace(/\./g, ',');
                            $("input." + formula_types[type] + ":eq(" + i + ")").val(strp);
                        }
                    }
                });
    
                // DISPLAY NUMBERS IN THE ANSWER BOXES
                var i;
                for (type = 0; type < nb_types; type++) {
                    var n = $("input." + formula_types[type]).length;
                    for (i = 0; i < n; i++) {
                        i = i.toString();
                        var strp = $("input." + formula_types[type] + ":eq(" + i + ")").val();
                        var strc = strp.replace(/\./g, ',');
                        $("input." + formula_types[type] + ":eq(" + i + ")").css("color", "#000");
                        $("input." + formula_types[type] + ":eq(" + i + ")").val(strc);
                    }
                }
                    
                // DISPLAY THE CORRECT ANSWERS
                var i;
                var n = $("div.formulaspartcorrectanswer").length;
                for (i = 0; i < n; i++) {
                    i = i.toString();
                    var strp = $("div.formulaspartcorrectanswer:eq(" + i + ")").text();
                    var strc = strp.replace(/\./g, ',');
                    $("div.formulaspartcorrectanswer:eq(" + i + ")").text(strc);
                }
    
            });
    
            $(document).ready(function() {
                // HIDE INVALID SYNTAX RED TRIANGLE
                $("span.formulas_input_warning_outer").css("display", "none");
                // DISPLAY TeX formulas with comma instead of dot - if in formula question only and if in the /\d\.\d/ regex only
                // This will touch separators surrounded by decimals to avoid breaking LaTeX with e.g. the <\ right.> command
                if ($('.formulaspart').length > 0) {
                    var i;
                    var n = $(".nolink").length;
                    for (i = 0; i < n; i++) {
                        i = i.toString();
                        var strp = $(".nolink:eq(" + i + ")").text();
                        var strc = strp.replace(/\d\.\d/g, function(x) {
                            return x.replace(".", ",");
                        });
                        $(".nolink:eq(" + i + ")").css("color", "#000");
                        $(".nolink:eq(" + i + ")").text(strc);
                    }
                }
            });
        </script>
    '''

    print("Генерируем файл задачи в формате Moodle XML...")
    moodle_xml_template = f'''
        <?xml version="1.0" encoding="UTF-8"?>
        <quiz>'''
    for problem in problems_list:
        name = problem[0]
        question = problem[1]
        solution = problem[2]
        answers = problem[3]
        moodle_xml_template += f'''
                <question type="formulas">
                    <name>
                        <text>{name + ' ' + str(random.randint(10000, 99999))}</text>
                    </name>
                    <questiontext format="html">
                        <text>
                            <![CDATA[{body}]]>
                        </text>
                    </questiontext>
                    <generalfeedback format="html">
                        <text></text>
                    </generalfeedback>
                    <defaultgrade>1.0000000</defaultgrade>
                    <penalty>0.3333333</penalty>
                    <hidden>0</hidden>
                    <idnumber></idnumber>
                    <correctfeedback format="html">
                        <text>Ваш ответ верный.</text>
                    </correctfeedback>
                    <partiallycorrectfeedback format="html">
                        <text>Ваш ответ частично правильный.</text>
                    </partiallycorrectfeedback>
                    <incorrectfeedback format="html">
                        <text>Ваш ответ неправильный.</text>
                    </incorrectfeedback>
                    <shownumcorrect/>
                    <varsrandom>
                        <text></text>
                    </varsrandom>
                    <varsglobal>
                        <text></text>
                    </varsglobal>
                    <answernumbering>
                        <text>abc</text>
                    </answernumbering>'''
        for index, answer in enumerate(answers):
            moodle_xml_template += f'''
                        <answers>
                            <partindex>
                                <text>{index}</text>
                            </partindex>
                            <placeholder>
                                <text>#{index + 1}</text>
                            </placeholder>
                            <answermark>
                                <text>{answer[1]}</text>
                            </answermark>
                            <answertype>
                                <text>0</text>
                            </answertype>
                            <numbox>
                                <text>1</text>
                            </numbox>
                            <vars1>
                                <text></text>
                            </vars1>
                            <answer>
                                <text>{answer[0]}</text>
                            </answer>
                            <vars2>
                                <text></text>
                            </vars2>
                            <correctness>
                                <text>
                                    <![CDATA[_relerr < {answer[3]}]]>
                                </text>
                            </correctness>
                            <unitpenalty>
                                <text>1</text>
                            </unitpenalty>
                            <postunit>
                                <text></text>
                            </postunit>
                            <ruleid>
                                <text>1</text>
                            </ruleid>
                            <otherrule>
                                <text></text>
                            </otherrule>
                            <subqtext format="html">
                                <text></text>
                            </subqtext>
                            <feedback format="html">
                                <text></text>
                            </feedback>
                            <correctfeedback format="html">
                                <text></text>
                            </correctfeedback>
                            <partiallycorrectfeedback format="html">
                                <text></text>
                            </partiallycorrectfeedback>
                            <incorrectfeedback format="html">
                                <text></text>
                            </incorrectfeedback>
                        </answers>'''
        moodle_xml_template += '''
                </question>'''
    moodle_xml_template += '''
        </quiz>    
    '''
    path = basename_filename + '_moodle.xml'
    with open(path, 'w', encoding='utf-8') as file:
        file.write(moodle_xml_template)
    print(f"Конвертация TeX в Moodle XML прошла успешно - \"{path}\"!")
    return os.getcwd() + '/' + path

# сгенерировать n штук указанных вариантов
def moodle_sample(path, n = 1, start_number = 1):
    # итоговый xml файл будет располагаться в папке results/moodle/<дата и время запуска>/<дата и время запуска>_moodle.xml
    # в этой же директории будет папка temp в которой будут сохраняться все временные файлы
    basename = os.path.basename(path).replace('.tex', '')
    folder = os.path.dirname(path)
    # заходим в корневой каталог
    os.chdir(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
    # создаем выходную папку, если нужно
    current_datetime = datetime.now().strftime("%d.%m.%Y %H-%M-%S") + f' (n={n})'
    results_directory = os.path.join(os.getcwd(), 'results', 'moodle', current_datetime)
    if not os.path.exists(results_directory):
        os.makedirs(results_directory)
    # создаем папку для временных файлов, если нужно
    temp_directory = os.path.join(results_directory, 'temp')
    if not os.path.exists(temp_directory):
        os.makedirs(temp_directory)
    try:
        xml_list = []
        for i in range(start_number, n + start_number):
            # берем указанный файл и копируем его во временную директорию
            # остальные манипуляции уже будут происходить с новым файлом
            os.chdir(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
            print(f'Создаем копию № {i} указанного файла {path}...')
            shutil.copyfile(path, os.path.join(temp_directory, f'task{i}.tex'))
            compile_tex(filename=f'task{i}', folder=temp_directory)
            path_to_tex_file_without_python = remove_python(filename=f'task{i}', folder=temp_directory)
            path_to_moodle_xml = convert_tex_to_moodle_xml(path_to_tex_file_without_python)
            xml_list.append(path_to_moodle_xml)
        print('Объединяем все файлы в единый Moodle XML...')
        with open(os.path.join(results_directory, current_datetime + '_moodle.xml'), 'w', encoding='utf-8') as file:
            file.write('<?xml version="1.0" encoding="UTF-8"?>\n<quiz>\n')
            for xml_path in xml_list:
                print('xml_path', xml_path)
                with open(xml_path, 'r', encoding='utf-8') as subfile:
                    source = subfile.read()
                    source = source.replace('<?xml version="1.0" encoding="UTF-8"?>', '')
                    source = source.replace('<quiz>', '')
                    source = source.replace('</quiz>', '')
                    file.write(source)
            file.write('</quiz>')
        print('Готово!')
    except BaseException as e:
        printerror(f'task{i + 1}.tex', temp_directory, e)
    pass

# компилируем tex файл
def compile_file(filename, folder='./results/tex/'):
    filename = str(filename)
    basename_filename = os.path.basename(filename).replace('.tex', '').replace('_template', '')
    os.chdir(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
    try:
        compile_tex(filename, folder)

        remove_python(filename, folder)

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
        problem_with_answer_directory = os.path.join('..', '..', 'results', 'html', 'problems_with_answers')
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
                  os.path.join('..', '..', 'results', 'html', \
                               'only_problems', basename_filename + '_problem.html'))

        # переносим файл со стилями
        printlog('Переносим файл со стилями в нужную папку...', basename_filename)
        os.rename(basename_filename + '_problem.css',
                  os.path.join('..', '..', 'results', 'html', \
                               'only_problems', basename_filename + '_problem.css'))

        printlog(f'Файл {os.path.join(folder, filename)} без блоков решений скомпилирован!\n', basename_filename)

        # создаем выходную папку, если нужно
        only_problems_directory = os.path.join('..', '..', 'results', 'html', 'only_problems')
        if not os.path.exists(only_problems_directory):
            os.makedirs(only_problems_directory)

        # переносим картинки в нужную папочку
        printlog('Копируем изображения (если есть) в нужные папки...\n', basename_filename)
        images_files = glob.glob('*.png')
        for imagepath in images_files:
            shutil.copyfile(imagepath, os.path.join(only_problems_directory, imagepath))
            shutil.copyfile(imagepath, os.path.join(only_problems_directory, imagepath))
    except BaseException as e:
        printerror(filename, folder, e)

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
    directory = './results/tex/'
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
    for files in [glob.glob('./results/**/**/*'), glob.glob('./results/tex/*'), glob.glob('./results/DataSets/*')]:
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

    # компилируем варианты и создаем их html версии
    for variant_number in range(start_numeration, start_numeration + variant_count):
        compile_file(str(variant_number) + '_template.tex', folder='./results/tex/')

    # сначала генерируем все варианты и только потом все компилириуем
    # разделение на 2 этапа нужно для обеспечения многопоточной компиляции вариантов
    # на основе html файлов генерируем ipynb
    # на основе html файлов генерируем gift
    # ipynb и gifts файлы можно генерировать как на основе hmtl, так и latex

    # сохраняем сгенерированные html в pdf
    print('Сохраняем сгенерированные html файлы в pdf...')
    html2pdf(os.path.join(os.getcwd(), 'results', 'html', 'only_problems'), \
             os.path.join(os.getcwd(), 'results', 'pdf', 'only_problems'), in_one_page=True)
    # объединяем все pdf в один файл
    html2pdf(os.path.join(os.getcwd(), 'results', 'html', 'problems_with_answers'), \
             os.path.join(os.getcwd(), 'results', 'pdf', 'problems_with_answers'), in_one_page=False)

    # очищаем текущую директорию от временных файлов
    with subp.Popen(['latexmk', '-C'], stdout=subp.PIPE) as proc:
        output = proc.stdout.read()

    # {"aux", "xref", "tmp", "4tc", "4ct", "idv", "lg","dvi", "log"}

    print('\nГотово!')
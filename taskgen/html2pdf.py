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
import json
import time
import base64
import io
from PyPDF2 import PdfFileMerger, PdfFileReader
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from webdriver_manager.chrome import ChromeDriverManager

def send_devtools(driver, cmd, params={}):
    resource = "/session/%s/chromium/send_command_and_get_result" % driver.session_id
    url = driver.command_executor._url + resource
    body = json.dumps({'cmd': cmd, 'params': params})
    response = driver.command_executor._request('POST', url, body)
    if response.get('status'):
        raise Exception(response.get('value'))
    return response.get('value')

def latex_is_loaded(driver):
    #print(arg)
    state = driver.execute_script('return window.latexIsLoaded;')
    #print('latex_state=%s' % state)
    return state == True

# source - путь к папке с html файлами
# output - путь к папке для сохранения результатов
# scale_step - шаг, с которым мы подбираем масштаб страницы
def html2pdf(source=os.path.join(os.getcwd(), 'html'), output = os.path.join(os.getcwd(), 'pdf'), in_one_page=False, scale_step = 0.025):
    # создаем папку для сохранения результатов, если нужно
    if not os.path.exists(output):
        os.makedirs(output)

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    for filename in sorted(os.listdir(source),
                           key=lambda filename: int(''.join(filter(str.isdigit, filename))) if filename.endswith(
                                   '.html') else False):
        if not filename.endswith('.html'):
            continue

        # открываем html файл
        print('Открываем файл:', filename)
        driver.get(f'file://{os.path.join(source, filename)}')

        print('Дожидаемся полной инициализации...')

        # дожидаемся загрузки страницы
        element = WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.TAG_NAME, 'body')))

        # дожидаемся полной инициализации LaTex на странице
        driver.execute_script('window.latexIsLoaded = false;')
        driver.execute_script('window.MathJax.Hub.Register.StartupHook("End",function () { window.latexIsLoaded = true; });')
        WebDriverWait(driver, 10).until(latex_is_loaded)

        # получаем pdf

        last_num_pages = -1
        last_pdf_file = None

        print_options = {
            'scale': 1,
        }

        if in_one_page:
            print('Подбираем коэффициент масштабирования...')
            while 0 < print_options['scale'] < 2:
                result = send_devtools(driver, "Page.printToPDF", print_options)
                result = base64.b64decode(result['data'])

                pdf_file = io.BytesIO(result)
                pdf_reader = PdfFileReader(pdf_file)
                num_pages = pdf_reader.numPages
                # print('При масштабировании {} кол-во страниц: {}'.format(print_options['scale'], num_pages))

                if last_num_pages > 1 and num_pages == 1:
                    break
                elif last_num_pages == 1 and num_pages == 2:
                    result = last_pdf_file
                    break
                elif num_pages == 1:
                    print_options['scale'] += scale_step
                else:
                    print_options['scale'] -= scale_step

                last_num_pages = num_pages
                last_pdf_file = result
        else:
            result = send_devtools(driver, "Page.printToPDF", print_options)
            result = base64.b64decode(result['data'])


        # сохраняем pdf
        print('Сохраняем файл...', '\n')
        with open(os.path.join(output, os.path.splitext(filename)[0] + '.pdf'), 'wb') as file:
            file.write(result)

    driver.close()
    print('Все html файлы в директории', source, 'сконвертированы в pdf!')

    # объединяем полученные файлы в один
    mergedObject = PdfFileMerger()
    for filename in sorted(os.listdir(output),
                           key=lambda filename: int(''.join(filter(str.isdigit, filename))) if filename.endswith(
                                   '.pdf') else False):
        if not filename.endswith('.pdf'):
            continue
        mergedObject.append(PdfFileReader(os.path.join(output, filename)))
    mergedObject.write(os.path.join(os.path.dirname(output), os.path.basename(output) + '_merged.pdf'))
    print('Все pdf файлы из директории', output, 'объединены в единый файл!')
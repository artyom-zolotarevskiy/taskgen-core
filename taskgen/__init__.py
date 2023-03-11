'''Ядро генератора банка задач на базе Jupyter Notebook и MiKTeX.

Для работы с ядром необходимо использовать панель управления, которая размещена
здесь - https://github.com/artyom-zolotarevskiy/taskgen.

Возможности
----------
Ядро в связке с панелью управления решают задачу генерации параметризованного банка задач
для методического сопровождения различных математических дисциплин в ВУЗе.

В качестве языка разметки используется TeX на базе дистрибутива MiKTeX, а за параметризацию отвечает Python на базе
Jupyter Notebook, входящий в Anaconda.

Результатом работы является уникальный банк задач в форматах TeX, HTML, PDF и Moodle XML. В скором времени планируется
добавить создание параметризированных интерактивных блокнотов Jupyter для учебного процесса.

Лицензия
-------
Copyright (c) 2023 Артём Золотаревский
Связь с автором: artyom@zolotarevskiy.ru

Благодарности
-------
Отдельная благодарность научному руководителю, Павлу Евгеньевичу Рябову,
за постановку задачи и постоянное внимание к работе.
'''
from taskgen.generator import *
from taskgen.html2pdf import *

format = "%(asctime)s: %(message)s"
logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")

__title__ = 'artyom-zolotarevskiy'
__version__ = '0.3.7'
__url__ = 'https://github.com/artyom-zolotarevskiy/taskgen-core'
__author__ = 'Артём Золотаревский'
__author_email__ = 'artyom@zolotarevskiy.ru'

__all__ = ["generator", "html2pdf"]

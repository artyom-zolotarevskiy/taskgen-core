Task Generator
===========

Генератор экзаменационных билетов на базе MikTex и Python.

Возможности
----------
- Написание вопросов, используя среду MikTex.
- Генерация PDF и HTML версий экзаменационных билетов.
- Генерация ответов.
- Параметризация вопросов и ответов.
- Генерация множества рандомизированных вариантов билетов.

Установка
----------

Впервую очередь нужно установить MikTex и PythonTex. Затем:

```python
pip install taskgen
```

Использование
----------
Автор рекомендуюет использовать Jupyter Notebook.

```python
from taskgen import *
from taskgen.generator import *
from taskgen.html2pdf import *

# начало нумерации билетов
start_numeration = 100
# кол-во генерируемых вариантов
variant_count = 1
# детерминированная генерация билетов
deterministic = True

%%time
generate_exam(start_numeration, variant_count, deterministic)
```

Другие команды
----------
```python
# создать один вариант в формате .tex
gen_variant(variant_number = 1, deterministic = True, task_number_for_deterministic=0)
```
```python
# cкомпилировать шаблон на базе PythonTex из формата tex в html
compile_file(filename = 'Q3', folder = './QUESTIONS/Q3/')
```
```python
# конвертировать все html файлы из папки в pdf
html2pdf(os.path.join(os.getcwd(), 'RESULTS', 'html', 'only_problems'), \
             os.path.join(os.getcwd(), 'RESULTS', 'pdf', 'only_problems'), in_one_page=True)
```

TODO
----------
[] Создать файл requirements.txt для легкой установки необходимых python зависимостей.

Лицензия
-------

Copyright (c) 2022 Артём Золотаревский.

**Task Generator** это свободное программное обеспечение, доступное по лицензии GNU GPLV3. Дополнительные
сведения см. в файле LICENSE.

[![License GPLV3](http://img.shields.io/badge/license-GPLV3-green.svg?style=flat)](https://github.com/metrazlot/taskgen/blob/main/LICENSE)

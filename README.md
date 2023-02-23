Task Generator
===========

Генератор экзаменационных билетов на базе MikTex и Python.

Последнее обновление кодовой базы: 23.02.2023.

По всем вопросам: artyom@zolotarevskiy.ru.

Особенности
----------
- Верстка задач осуществляется на языке LaTeX, а параметризация на Python в Jupyter Notebook.
- Результатом работы являются экзаменационные билеты в форматах TeX, HTML и Moodle XML.

Установка
----------

На компьютере должен быть установлен MiKTeX и Jupyter Notebook. 

### 1. Скачать данный репозиторий
В виде zip архива или посредством git'а:

```
git clone git@github.com:artyom-zolotarevskiy/taskgen.git
```

### 2. Установить пакет Python

```
cd taskgen
pip install -r requirements.txt
pip install -e .
```

### 3. Установить пакет TeX в систему MiKTex
Пакет для установки расположен по пути: "./settings/taskgen.sty"

Пример терминальных команд для установки в MacOS:
```
sudo -i
cp ./settings/taskgen.sty /usr/local/texlive/texmf-local/tex/latex/taskgen.sty
texhash
```



Использование
----------
Смотри файл "control_panel.ipynb".



Лицензия
-------

Copyright (c) 2023 Артём Золотаревский.

Связь с автором: artyom@zolotarevskiy.ru

**Task Generator** это свободное программное обеспечение, доступное по лицензии GNU GPLV3. Дополнительные
сведения см. в файле LICENSE.

[![License GPLV3](http://img.shields.io/badge/license-GPLV3-green.svg?style=flat)](https://github.com/metrazlot/taskgen/blob/main/LICENSE)

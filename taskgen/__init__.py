'''Генератор экзаменационных билетов на базе MikTex'''
from taskgen.generator import *
from taskgen.html2pdf import *

format = "%(asctime)s: %(message)s"
logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")

__title__ = 'artyom-zolotarevskiy'
__version__ = '0.3.1'
__url__ = 'https://github.com/artyom-zolotarevskiy/taskgen'
__author__ = 'Артём Золотаревский'
__author_email__ = 'artyom@zolotarevskiy.ru'
__license__ = 'GPLV3'

__all__ = ["generator", "html2pdf"]

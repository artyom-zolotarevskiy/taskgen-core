import os
import glob
import logging
import configparser

def find_settings_folder(initial_path=os.getcwd()):
    '''
    Данная функция ищет папку "settings" в родительских папках относительно переданной до 5 уровней вложенности вверх.
    :param initial_path: начальная папка для поиска (по умолчанию - активная директория исполняемого файла)
    '''
    settings_folder = initial_path
    flag = False
    for i in range(6):
        directory_files = glob.glob(os.path.join(settings_folder, '*'))
        if len(list(filter(lambda path: os.path.basename(path) == 'settings', directory_files))) > 0:
            flag = True
            settings_folder = os.path.join(settings_folder, 'settings')
            break
        else:
            settings_folder = os.path.dirname(settings_folder)
    if flag:
        return settings_folder
    logging.error('Не удалось найти папку с настройками!')
    return False

__SETTINGS_FOLDER__ = find_settings_folder()

config = configparser.ConfigParser()
config['GENERAL'] = {
    # Название функции, которая возвращает словарь (ассоциативный массив) названий
    # подставляемых переменных и их соответствующие значения для новой параметризации
    'parameterizer_function_name': 'GET',

    # Количество потоков для выполнения параметризации
    'parameterizer_threads_count': '10',

    # Количество потоков для выполнения конвертации из TeX в HTML
    'converter_threads_count': '10',

    # Путь к банку задач
    'bank_folder': os.path.join(os.getcwd(), 'bank'),

    # Путь к папке с шаблонами
    'templates_folder': os.path.join(os.getcwd(), 'templates', 'default')
}
config.read(os.path.join(__SETTINGS_FOLDER__, 'config.ini'))

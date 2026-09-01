import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# НАСТРОЙКА OZON
# Номер телефона для входа
OZON_PHONE = os.getenv('OZON_PHONE', 'xxx') # Ввести свой номер для входа

# URL для авторизации и парсинга
OZON_DATA_URL = os.getenv('OZON_DATA_URL', 'https://data.ozon.ru/')
OZON_PRODUCT_URL = os.getenv('OZON_PRODUCT_URL', 'https://www.ozon.ru/product/')

# НАСТРОЙКА GMAIL
# Файлы для Gmail API
GMAIL_CREDENTIALS_FILE = os.getenv('GMAIL_CREDENTIALS_FILE', 'credentials.json')
GMAIL_TOKEN_FILE = os.getenv('GMAIL_TOKEN_FILE', 'token.json')

# НАСТРОЙКИ ПАРСИНГА
# Количество попыток при ошибке
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))

# Таймаут запросов в секундах
TIMEOUT = int(os.getenv('TIMEOUT', 30))

# User-Agent для имитации браузера
USER_AGENT = os.getenv(
    'USER_AGENT',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' 
    '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
)

# ФАЙЛЫ СОХРАНЕНИЯ
# Файл для хранения cookies
COOKIES_FILE = 'cookies.json'

# Файл для результатов CSV
CSV_FILE = 'data/products.csv'
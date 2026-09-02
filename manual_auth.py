import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Ручная авторизация на data.ozon.ru с сохранением cookies

# Настройка браузера
options = Options()
# Отключаем признаки автоматизации
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument("--disable-blink-features=AutomationControlled")

# Путь к Chrome на Mac
chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
options.binary_location = chrome_path

# Создаем драйвер
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# Открываем страницу
driver.get('https://data.ozon.ru/')

# Ждем, пока пользователь войдет
input("\n После входа в аккаунт нажмите Enter...")

# Получаем cookies
cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}

# Сохраняем
with open('cookies.json', 'w') as f:
    json.dump(cookies, f, indent=2)

print(f"\n Сохранено {len(cookies)} cookies в cookies.json")

# Закрываем браузер
driver.quit()
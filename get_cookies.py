import os
import json
import time
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

import config

# Универсальный сбор cookies
# Сначало пробуем войти через Gmail API, если появляется qr-код 
# или подтверждение звонком или код не пришел, 
# то автоматическое переключение на ручной ввод через минуту
# На экране ручного сбора необходимо ввести номер телефона и нажать войти 
# - после того как вошли нажать в консоли enter, чтобы собрать cookie

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Универсальный сборщик cookies
class OzonCookieCollector:
    def __init__(self):
        self.driver = None
        self.cookies = {}
        self.gmail = None
    
    # Ожидание загрузки страницы, что появились все объекты на странице
    def wait_for_page_load(self, 
                           driver, 
                           timeout: int = 30) -> bool:
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            logger.error("Таймаут загрузки страницы")
            return False

    # Поиск и нажатие кнопки перейти к аналитике, чтобы сразу перейти на страницу входа
    def click_analytics_button(self, 
                                driver
                                ) -> bool:
        # Ждем появления кнопки
        time.sleep(2)
        
        # Поиск по точному тексту - как это сделано на html странице
        try:
            xpath = "//button[contains(text(), 'Перейти к аналитике')]"
            btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            if btn.is_displayed() and btn.is_enabled():
                btn.click()
                logger.info("Нажата кнопка по тексту: 'Перейти к аналитике'")
                time.sleep(2)
                return True
        except Exception as e:
            logger.debug(f"Поиск по тексту не удался: {e}")
        
        logger.info("Пропускаем этот шаг и продолжаем...")
        return True

    # Поиск и нажатие кнопки войти
    def find_login_button(self, 
                          driver
                          ) -> bool:
        # Прямой поиск по html
        try:
            xpath = "//button[@type='submit'][contains(., 'Войти')]"
            btn = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            if btn.is_displayed() and btn.is_enabled():
                btn.click()
                logger.info("Нажата кнопка 'Войти' (button[type='submit'])")
                time.sleep(1)
                return True
        except Exception as e:
            logger.debug(f"Прямой поиск не удался: {e}")
        
        logger.warning("Кнопка 'Войти' не найдена")
        return False

    # Ввод номера телефона
    def enter_phone(self, 
                    driver, 
                    phone: str
                    ) -> bool:
        try:
            time.sleep(2)
            
            selectors = [
                "input[type='tel']",
                "input[type='text']",
                "input[name='phone']",
                "input[placeholder*='телефон']",
                "input[placeholder*='phone']",
                "input[inputmode='numeric']",
                "input"
            ]
            
            phone_input = None
            for selector in selectors:
                try:
                    phone_input = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if phone_input.is_displayed() and phone_input.is_enabled():
                        logger.info(f"Найдено поле ввода: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Поиск по селектору {selector} не удался: {e}")
                    continue
            
            if not phone_input:
                logger.error("Не найдено поле для ввода телефона")
                return False
            
            phone_input.clear()
            time.sleep(0.3)
            for char in phone:
                phone_input.send_keys(char)
                time.sleep(0.05)
            
            logger.info(f"Номер {phone} введен")
            time.sleep(1)
            
            if self._find_login_button(driver):
                return True
            
            phone_input.send_keys("\n")
            logger.info("Нажата клавиша Enter")
            return True
                
        except Exception as e:
            logger.error(f"Ошибка ввода номера: {e}")
            return False

    # Метод ввода кода подтверждения если у нас не ручной вход
    def enter_code(self, 
                   driver, 
                   code: str
                   ) -> bool:
        try:
            time.sleep(3)
            
            code_input = None
            selectors = [
                "input[type='text'][maxlength='6']",
                "input[inputmode='numeric']",
                "input[name='code']",
                "input[placeholder*='код']",
                "input"
            ]
            
            for selector in selectors:
                try:
                    code_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if code_input.is_displayed():
                        logger.info(f"Найдено поле для кода: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Поиск по селектору {selector} не удался: {e}")
                    continue
            
            if not code_input:
                logger.error("Не найдено поле для ввода кода")
                return False
            
            code_input.clear()
            time.sleep(0.3)
            for char in str(code):
                code_input.send_keys(char)
                time.sleep(0.1)
            
            logger.info(f"Код введен")
            time.sleep(2)
            
            self.find_login_button(driver)
            time.sleep(3)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка ввода кода: {e}")
            return False

    # Метод для получения кода из gmail API
    def get_code_from_gmail(self) -> str:
        try:
            if not os.path.exists(config.GMAIL_CREDENTIALS_FILE):
                logger.warning(f"Файл {config.GMAIL_CREDENTIALS_FILE} не найден")
                return None
            
            from gmail_api import GmailCodeExtractor
            
            self.gmail = GmailCodeExtractor(
                config.GMAIL_CREDENTIALS_FILE,
                config.GMAIL_TOKEN_FILE
            )
            
            code = self.gmail.get_verification_code(
                sender_email='noreply@ozon.ru',
                timeout=60,
                interval=3
            )
            
            if code:
                logger.info(f"Код успешно получен через Gmail: {code}")
                return code
            else:
                logger.warning("Не удалось получить код через Gmail")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при работе с Gmail API: {e}")
            return None
    
    # Автоматический режим
    # Инициализация undetected-chromedriver для автоматического режима, 
    # чтобы обойти антибот защиту
    def init_driver_auto(self) -> None:
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            if os.path.exists(chrome_path):
                options.binary_location = chrome_path
            
            self.driver = uc.Chrome(
                options=options,
                version_main=None,
                headless=False,
                use_subprocess=True
            )
            
            self.driver.implicitly_wait(10)
            logger.info("WebDriver (undetected) успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации драйвера: {e}")
            raise

    # Метод запуска автоматического парсинга с Gmail API
    def auto_mode(self, 
                  phone: str
                  ) -> dict:
        logger.info("Автоматический режим")
        
        self.init_driver_auto()
        driver = self.driver
        
        logger.info(f"Переход на {config.OZON_DATA_URL}")
        driver.get(config.OZON_DATA_URL)
        
        if not self.wait_for_page_load(driver):
            raise Exception("Страница не загрузилась")
        
        time.sleep(2)
        
        self.click_analytics_button(driver)
        
        if not self.enter_phone(driver, phone):
            raise Exception("Не удалось ввести номер телефона")
        
        code = self.get_code_from_gmail()
        
        if code:
            if self.enter_code(driver, code):
                logger.info("Автоматический вход выполнен успешно!")
                time.sleep(5)
                
                cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
                logger.info(f"Получено {len(cookies)} cookies (автоматический режим)")
                return cookies
            else:
                raise Exception("Ошибка ввода кода")
        else:
            logger.warning("Не удалось получить код через Gmail")
            return None
    
    # Ручной режим входа, если автоматический не удался по каким-либо причинам
    def manual_mode(self) -> dict:
        try:
            options = Options()
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            if os.path.exists(chrome_path):
                options.binary_location = chrome_path
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Открываем страницу
            logger.info(f"Переход на {config.OZON_DATA_URL}")
            driver.get('https://data.ozon.ru/')
            
            # Ждем загрузки страницы
            if not self.wait_for_page_load(driver):
                logger.warning("Страница загрузилась не полностью")
            
            time.sleep(2)
            
            logger.info("Пробуем автоматически нажать 'Перейти к аналитике'")
            self.click_analytics_button(driver)
            
            input("\nПосле входа в аккаунт нажмите Enter...")
            
            # Получаем cookies
            cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
            
            driver.quit()
            
            logger.info(f"Получено {len(cookies)} cookies (ручной режим)")
            return cookies
            
        except Exception as e:
            logger.error(f"Ошибка в ручном режиме: {e}")
            raise
    
    # Основной метод - Сбор cookies с автоматическим переключением на ручной режим
    def collect_cookies(self, 
                        phone: str
                        ) -> dict:
        try:
            # Пытаемся автоматический режим
            cookies = self.auto_mode(phone)
            
            if cookies:
                return cookies
            
            # Если автоматика не сработала - ручной режим
            logger.warning("Автоматический режим не удался")
            
            if self.driver:
                self.driver.quit()
                self.driver = None
            
            return self.manual_mode()
            
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            
            if self.driver:
                self.driver.quit()
                self.driver = None
            
            return self.manual_mode()

    # Сохранение cookies в json
    def save_cookies(self, 
                     filename: str = config.COOKIES_FILE
                     ) -> None:
        try:
            with open(filename, 'w') as f:
                json.dump(self.cookies, f, indent=2)
            logger.info(f"Cookies сохранены в {filename}")
        except Exception as e:
            logger.error(f"Ошибка сохранения cookies: {e}")
            raise


def main():
    collector = OzonCookieCollector()
    
    try:
        cookies = collector.collect_cookies(config.OZON_PHONE)
        collector.cookies = cookies
        collector.save_cookies()
        
    except Exception as e:
        logger.error(f"Не удалось получить cookies: {e}")

if __name__ == '__main__':
    main()
import os
import json
import time
import logging
import csv
import re
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import config

# Парсер Ozon с использованием undetected-chromedriver для обхода антибот системы Ozon

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Парсер Ozon с обходом защиты
class OzonParserUndetected:
    # Инициализация парсера
    def __init__(self):
        self.driver = None
        self.results = []

    # Инициализация драйвера
    def _init_driver(self) -> None:
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Указываем путь к Chrome (для Mac)
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            if os.path.exists(chrome_path):
                options.binary_location = chrome_path
            
            # Создаем драйвер с обходом защиты
            self.driver = uc.Chrome(
                options=options,
                version_main=None,  # Автоматически определяет версию
                headless=False,     # Можно включить для сервера
                use_subprocess=True
            )
            
            self.driver.implicitly_wait(10)
            logger.info("WebDriver успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации драйвера: {e}")
            raise

    # Инициализация загрузки страницы - возвращает true, если загружена
    def _wait_for_page_load(self, timeout: int = 30) -> bool:
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script(
                    "return document.readyState"
                ) == "complete"
            )
            return True
        except TimeoutException:
            logger.error("Таймаут загрузки страницы")
            return False

    # Загрузка страницы товара и получение HTML
    def _get_page_html(self, sku: str) -> str:
        url = f"https://www.ozon.ru/product/{sku}/"
        logger.info(f"Загрузка: {url}")
        
        try:
            self.driver.get(url)
            
            if not self._wait_for_page_load():
                raise Exception("Страница не загрузилась")
            
            # Дополнительная задержка для рендеринга JavaScript
            time.sleep(2)
            
            html = self.driver.page_source
            logger.info(f"Страница загружена, размер: {len(html)} символов")
            
            # Проверяем наличие блокировки
            if "Access denied" in html or "403" in html or "Please verify" in html:
                logger.warning("Обнаружена блокировка, пробуем перезагрузить...")
                time.sleep(3)
                self.driver.refresh()
                time.sleep(2)
                html = self.driver.page_source
            
            return html
            
        except Exception as e:
            logger.error(f"Ошибка загрузки страницы {sku}: {e}")
            return ""

    # Извлечение json из html - в случае успеха возращает словарь с данными
    def _extract_json_data(self, html: str) -> dict:
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Ищем скрипты с JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if data.get('@type') == 'Product':
                        return data
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка извлечения JSON: {e}")
            return None

    # Парсинг данных из html - в случае успеха возвращает словарь с данными товара
    def _parse_from_html(self, html: str, sku: str) -> dict:
        product = {
            'sku': sku,
            'title': '',
            'price': 0.0,
            'rating': 0.0,
            'reviews_total': 0,
            'cover_image': '',
            'photos_seller': 0,
            'videos_seller': 0,
            'color': '',
            'material': '',
            'art_set': '',
            'has_rich_content': False
        }
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 1. Пробуем извлечь из JSON-LD
            json_data = self._extract_json_data(html)
            if json_data:
                product['title'] = json_data.get('name', '')
                
                # Изображение
                image = json_data.get('image', '')
                if isinstance(image, list) and image:
                    product['cover_image'] = image[0]
                elif isinstance(image, str):
                    product['cover_image'] = image
                
                # Цена
                offers = json_data.get('offers', {})
                if isinstance(offers, dict):
                    product['price'] = float(offers.get('price', 0))
                elif isinstance(offers, list) and offers:
                    product['price'] = float(offers[0].get('price', 0))
                
                # Рейтинг
                rating = json_data.get('aggregateRating', {})
                if rating:
                    product['rating'] = float(rating.get('ratingValue', 0))
                    product['reviews_total'] = int(rating.get('reviewCount', 0))
            
            # 2. Если JSON не помог, парсим HTML напрямую
            if not product['title']:
                title_elem = soup.select_one('h1, [data-testid="product-title"]')
                if title_elem:
                    product['title'] = title_elem.text.strip()
            
            if product['price'] == 0:
                price_elem = soup.select_one('[data-testid="price"], .product-price, .price')
                if price_elem:
                    price_text = re.sub(r'[^\d,.]', '', price_elem.text)
                    try:
                        product['price'] = float(price_text.replace(',', '.'))
                    except:
                        pass
            
            if product['rating'] == 0:
                rating_elem = soup.select_one('[data-testid="rating"], .rating')
                if rating_elem:
                    rating_text = rating_elem.text.strip()
                    match = re.search(r'([\d.]+)', rating_text)
                    if match:
                        try:
                            product['rating'] = float(match.group(1))
                        except:
                            pass
            
            # 3. Характеристики
            specs = soup.select('[data-testid="characteristics"], .product-attributes')
            if specs:
                spec_text = specs[0].text.lower()
                
                color_match = re.search(r'цвет[:\s]+([^,\n]+)', spec_text, re.IGNORECASE)
                if color_match:
                    product['color'] = color_match.group(1).strip()
                
                material_match = re.search(r'материал[:\s]+([^,\n]+)', spec_text, re.IGNORECASE)
                if material_match:
                    product['material'] = material_match.group(1).strip()
            
            # 4. Количество фото и видео
            gallery_items = soup.select('[data-testid="gallery-item"], .gallery-item')
            product['photos_seller'] = len(gallery_items)
            
            video_elements = soup.select('video, [data-testid="video-preview"]')
            product['videos_seller'] = len(video_elements)
            
            # 5. Rich Content (изображения, таблицы, списки в описании)
            description = soup.select('.product-description, [data-testid="description"]')
            if description:
                desc_html = str(description[0])
                product['has_rich_content'] = bool(
                    re.search(r'<img\b', desc_html) or 
                    re.search(r'<table\b', desc_html) or 
                    re.search(r'<(ul|ol)\b', desc_html)
                )
            
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
        
        return product

    # Парсинг одного товара по SKU
    def parse_product(self, sku: str) -> dict:
        logger.info(f"Парсинг SKU: {sku}")
        
        html = self._get_page_html(sku)
        if not html:
            logger.error(f"Не удалось получить HTML для SKU {sku}")
            return None
        
        product = self._parse_from_html(html, sku)
        
        if product and product['title']:
            logger.info(
                f"SKU {sku}: {product['title'][:50]}... - {product['price']} руб."
            )
            return product
        else:
            logger.warning(f"⚠️ Не удалось спарсить SKU {sku}")
            return None

    # Парсинг списка товаров - в случае успеха возвращаем список словарей с товарами
    def parse_products(self, sku_list: list) -> list:
        self.results = []
        total = len(sku_list)
        
        for i, sku in enumerate(sku_list, 1):
            logger.info(f"Прогресс: {i}/{total}")
            
            product = self.parse_product(sku)
            if product:
                self.results.append(product)
            
            # Задержка между запросами (чтобы не перегружать сервер)
            time.sleep(2)
        
        return self.results

    # Сохранение в csv
    def save_to_csv(self, filename: str = 'data/products_undetected.csv'):
        if not self.results:
            logger.warning("Нет данных для сохранения")
            return
        
        fields = [
            'sku', 'title', 'price', 'rating', 'reviews_total',
            'cover_image', 'photos_seller', 'videos_seller',
            'color', 'material', 'art_set', 'has_rich_content'
        ]
        
        try:
            os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fields, delimiter=';')
                writer.writeheader()
                writer.writerows(self.results)
            logger.info(f"Данные сохранены в {filename}")
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")

    # Закрытие драйвера
    def close(self):
        if self.driver:
            self.driver.quit()


def main():
    # Список SKU для парсинга
    sku_list = ['2359066702', '2829800382']
    
    parser = OzonParserUndetected()
    
    try:
        # Инициализация драйвера
        parser._init_driver()
        
        # Парсинг
        products = parser.parse_products(sku_list)
        
        # Сохранение результатов
        parser.save_to_csv()
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        parser.close()


if __name__ == '__main__':
    main()
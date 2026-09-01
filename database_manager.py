import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
import config
import time

logger = logging.getLogger(__name__)

# Модуль для работы с Postgres

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self._connect()

    # Соединение с бд
    def _connect(self):
        try:
            self.connection = psycopg2.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD
            )
            logger.info(f"Подключение к PostgreSQL успешно: {config.DB_NAME}")
        except Exception as e:
            logger.error(f"Ошибка подключения к PostgreSQL: {e}")
            raise

    # Создание таблицы для хранения товаров
    def create_table(self, table_name: str = None):
        if table_name is None:
            table_name = config.DB_TABLE
        
        try:
            cursor = self.connection.cursor()
            
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) UNIQUE NOT NULL,
                title TEXT,
                price DECIMAL(10, 2),
                rating DECIMAL(3, 2),
                reviews_total INTEGER,
                cover_image TEXT,
                photos_seller INTEGER,
                videos_seller INTEGER,
                color VARCHAR(100),
                material VARCHAR(100),
                art_set VARCHAR(100),
                has_rich_content BOOLEAN,
                parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_products_sku ON {table_name}(sku);
            CREATE INDEX IF NOT EXISTS idx_products_price ON {table_name}(price);
            CREATE INDEX IF NOT EXISTS idx_products_rating ON {table_name}(rating);
            """
            
            cursor.execute(create_table_query)
            self.connection.commit()
            cursor.close()
            
            logger.info(f"Таблица '{table_name}' создана/существует")
            
        except Exception as e:
            logger.error(f"Ошибка создания таблицы: {e}")
            raise

    # Сохранение списка товаров в бд
    def save_products(self, products: List[Dict[str, Any]], table_name: str = None) -> int:
        if not products:
            logger.warning("Нет данных для сохранения")
            return 0
        
        if table_name is None:
            table_name = config.DB_TABLE
        
        try:
            cursor = self.connection.cursor()
            saved_count = 0
            
            for product in products:
                insert_query = f"""
                INSERT INTO {table_name} (
                    sku, title, price, rating, reviews_total,
                    cover_image, photos_seller, videos_seller,
                    color, material, art_set, has_rich_content,
                    parsed_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (sku) DO UPDATE SET
                    title = EXCLUDED.title,
                    price = EXCLUDED.price,
                    rating = EXCLUDED.rating,
                    reviews_total = EXCLUDED.reviews_total,
                    cover_image = EXCLUDED.cover_image,
                    photos_seller = EXCLUDED.photos_seller,
                    videos_seller = EXCLUDED.videos_seller,
                    color = EXCLUDED.color,
                    material = EXCLUDED.material,
                    art_set = EXCLUDED.art_set,
                    has_rich_content = EXCLUDED.has_rich_content,
                    parsed_at = CURRENT_TIMESTAMP
                RETURNING id;
                """
                
                cursor.execute(insert_query, (
                    product['sku'],
                    product['title'],
                    product['price'],
                    product['rating'],
                    product['reviews_total'],
                    product['cover_image'],
                    product['photos_seller'],
                    product['videos_seller'],
                    product['color'],
                    product['material'],
                    product['art_set'],
                    product['has_rich_content']
                ))
                
                result = cursor.fetchone()
                if result:
                    saved_count += 1
            
            self.connection.commit()
            cursor.close()
            
            logger.info(f"Сохранено {saved_count} товаров в PostgreSQL")
            return saved_count
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в PostgreSQL: {e}")
            self.connection.rollback()
            raise

    # Получение списка товаров из бд
    def get_products(self, limit: int = 100, table_name: str = None) -> List[Dict[str, Any]]:
        if table_name is None:
            table_name = config.DB_TABLE
        
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(f"""
                SELECT * FROM {table_name}
                ORDER BY parsed_at DESC
                LIMIT %s
            """, (limit,))
            
            results = cursor.fetchall()
            cursor.close()
            
            products = [dict(row) for row in results]
            logger.info(f"Загружено {len(products)} товаров из PostgreSQL")
            return products
            
        except Exception as e:
            logger.error(f"Ошибка загрузки из PostgreSQL: {e}")
            return []

    # Получение товара по SKU
    def get_product_by_sku(self, 
                           sku: str, 
                           table_name: str = None
                           ) -> Optional[Dict[str, Any]]:

        if table_name is None:
            table_name = config.DB_TABLE
        
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(f"""
                SELECT * FROM {table_name}
                WHERE sku = %s
            """, (sku,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return dict(result)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска SKU {sku}: {e}")
            return None

    # Удаление товара по SKU
    def delete_product(self, sku: str, table_name: str = None) -> bool:
        if table_name is None:
            table_name = config.DB_TABLE
        
        try:
            cursor = self.connection.cursor()
            
            cursor.execute(f"""
                DELETE FROM {table_name}
                WHERE sku = %s
                RETURNING id
            """, (sku,))
            
            result = cursor.fetchone()
            self.connection.commit()
            cursor.close()
            
            if result:
                logger.info(f"Товар SKU {sku} удален")
                return True
            else:
                logger.warning(f"Товар SKU {sku} не найден")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка удаления SKU {sku}: {e}")
            self.connection.rollback()
            return False

    # Очистка таблицы
    def clear_table(self, table_name: str = None) -> bool:
        if table_name is None:
            table_name = config.DB_TABLE
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY")
            self.connection.commit()
            cursor.close()
            
            logger.info(f"Таблица '{table_name}' очищена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка очистки таблицы: {e}")
            self.connection.rollback()
            return False

    # Закрытие соединения
    def close(self):
        if self.connection:
            self.connection.close()
            logger.info("Соединение с PostgreSQL закрыто")

# Проверка подлючения
def check_connection() -> bool:
    try:
        db = DatabaseManager()
        db.close()
        return True
    except:
        return False

# Получение всех товаров
def get_all_products(limit: int = 100) -> List[Dict[str, Any]]:
    try:
        db = DatabaseManager()
        products = db.get_products(limit)
        db.close()
        return products
    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        return []
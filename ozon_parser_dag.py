from datetime import datetime, timedelta
import sys
import os

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator

PROJECT_PATH = '/Users/a1234/Documents/ozon_parser'
sys.path.append(PROJECT_PATH)
os.chdir(PROJECT_PATH)

SKU_LIST = ['2359066702', '2829800382']

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 9, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Функция запуска парсера
def run_ozon_parser(**context):
    try:
        # Импортируем парсер
        from parse_ozon import OzonParser
        
        # Создаем экземпляр и запускаем
        parser = OzonParser()
        products = []
        
        try:
            parser._init_driver()
            products = parser.parse_products(SKU_LIST)
            
            if not products:
                return "No data"
            
            # Сохраняем в БД
            result = parser.save_products_to_db(products)
            
            if result['success']:
                return f"Saved {result['saved_count']} products"
            else:
                return f"Error: {result['error']}"
            
        except Exception as e:
            raise
        
        finally:
            parser.close()
            
    except Exception as e:
        raise

dag = DAG(
    'ozon_parser_daily',
    default_args=default_args,
    description='Ежедневный парсинг товаров Ozon',
    schedule_interval='0 8 * * *', 
    catchup=False,
    tags=['ozon', 'parser', 'daily'],
)

start_task = DummyOperator(
    task_id='start',
    dag=dag,
)

run_parser_task = PythonOperator(
    task_id='run_parser',
    python_callable=run_ozon_parser,
    dag=dag,
)

send_notification_task = PythonOperator(
    task_id='send_notification',
    python_callable=send_notification,
    dag=dag,
)

end_task = DummyOperator(
    task_id='end',
    dag=dag,
)
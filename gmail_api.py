import base64
import time
import re
import logging
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Модуль для работы с Gmail API, если код приходит на почту, если нет - тогда только ручное получение cookies

# Класс для извлечения кода подтверждения из gmail
class GmailCodeExtractor:
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    # Инициализация gmail клиента
    def __init__(self, 
                 credentials_file: str, 
                 token_file: str
                 ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.authenticate()

    # Аутентификация в gmail API
    def authenticate(self) -> None:
        creds = None
        
        # Загружаем сохраненный токен
        try:
            import os
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(
                    self.token_file, self.SCOPES
                )
        except Exception as e:
            logger.warning(f"Не удалось загрузить токен: {e}")
        
        # Если токена нет или он недействителен - запрашиваем новый
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Сохраняем токен для следующего использования
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Успешная аутентификация в Gmail")

    # Получение кода потверждения из письма - возвращает код подтверждения
    def get_verification_code(self, 
                              sender_email: str = 'noreply@ozon.ru', # email отправителя
                              timeout: int = 120,                    # максимальное время ожидания в секундах
                              interval: int = 5                      # интервал проверки в секундах
                              ) -> Optional[str]:
        
        start_time = time.time()
        last_check_time = start_time
        attempts = 0
        
        while time.time() - start_time < timeout:
            try:
                attempts += 1
                
                # Ищем письма от отправителя за последнюю минуту
                query = f'from:{sender_email} after:{int(last_check_time - 60)}'
                result = self.service.users().messages().list(
                    userId='me', q=query
                ).execute()
                
                messages = result.get('messages', [])
                if messages:
                    logger.info(f"Найдено {len(messages)} писем от {sender_email}")
                    
                    # Берем последнее письмо
                    msg = self.service.users().messages().get(
                        userId='me', id=messages[0]['id']
                    ).execute()
                    
                    # Получаем тело письма
                    payload = msg.get('payload', {})
                    parts = payload.get('parts', [])
                    body_text = ''
                    
                    if parts:
                        for part in parts:
                            if part.get('mimeType') == 'text/plain':
                                data = part.get('body', {}).get('data')
                                if data:
                                    body_text = base64.urlsafe_b64decode(
                                        data
                                    ).decode('utf-8')
                                    break
                    else:
                        data = payload.get('body', {}).get('data')
                        if data:
                            body_text = base64.urlsafe_b64decode(data).decode('utf-8')
                    
                    # Ищем 6-значный код в тексте письма
                    code_match = re.search(r'\b(\d{6})\b', body_text)
                    if code_match:
                        code = code_match.group(1)
                        logger.info(f" Найден код подтверждения: {code}")
                        return code
                    else:
                        logger.warning("Код не найден в письме, пробуем дальше...")
                
                last_check_time = time.time()
                
                # Каждые 30 секунд предлагаем ввести код вручную
                if attempts % 5 == 0:
                    print(f"\n Ждем письмо... ({int(time.time() - start_time)} сек.)")
                    print("Если код уже пришел, введите его вручную:")
                    print("(или нажмите Enter, чтобы продолжить ожидание)")
                    
                    manual_code = input("Код (6 цифр): ").strip()
                    if manual_code and len(manual_code) == 6 and manual_code.isdigit():
                        logger.info(f"Код введен вручную: {manual_code}")
                        return manual_code
                
                time.sleep(interval)
                
            except HttpError as error:
                logger.error(f"Ошибка Gmail API: {error}")
            except Exception as e:
                logger.error(f"Неизвестная ошибка: {e}")
                time.sleep(interval)
        
        # Если время вышло - просим ввести код вручную
        print("Введите код из письма вручную:")
        manual_code = input("Код (6 цифр): ").strip()
        
        if manual_code and len(manual_code) == 6 and manual_code.isdigit():
            logger.info(f"Код введен вручную: {manual_code}")
            return manual_code
        
        logger.error("Код подтверждения не найден")
        return None
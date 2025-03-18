import os
import time
import json
import tls_client
import requests
import logging
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PAGE_URL = "https://visa.vfsglobal.com/blr/ru/pol/login"
LOGIN_URL = "https://lift-api.vfsglobal.com/user/login"

HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://visa.vfsglobal.com',
    'referer': PAGE_URL,
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/133.0.0.0'
}

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

TELEGRAM_BOT_TOKEN = "6111909478:AAHw4LngDMHZSxAQ8w_guKvYMFusDE9boU8"
TELEGRAM_CHAT_ID = "-1001702592627"

def escape_markdown(text: str) -> str:
    return re.sub(r'([*_`\[\]()~>#+\-=|{}.!])', r'\\\1', text)

def send_cookies_to_telegram(cookies_dict):
    """ Отправляет куки в Telegram """
    try:
        for cookie_name, cookie_value in cookies_dict.items():
            escaped_cookie_name = escape_markdown(cookie_name)
            escaped_cookie_value = escape_markdown(cookie_value)
            message = f"**{escaped_cookie_name}:** `{escaped_cookie_value}`"

            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            response = requests.post(url, json=data)

            if response.status_code == 200:
                logging.info(f"✅ Куки '{cookie_name}' отправлены в Telegram")
            else:
                logging.error(f"❌ Ошибка отправки куки '{cookie_name}' в Telegram: {response.text}")
    except Exception as e:
        logging.error(f"Ошибка отправки куки в Telegram: {str(e)}")

def create_session():
    return tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)

def wait_for_cfwaitingroom(session):
    """ Ожидание появления куки __cfwaitingroom__cf_wr """
    logging.info("⏳ Ожидание прохождения комнаты ожидания... Проверяем каждую минуту.")

    while True:
        response = session.get(PAGE_URL, headers=HEADERS)
        session_cookies = session.cookies.get_dict()

        logging.info(f"🔍 Текущие куки: {json.dumps(session_cookies, indent=4, ensure_ascii=False)}")

        if "__cfwaitingroom__cf_wr" in session_cookies:
            logging.info("✅ Комната ожидания пройдена!")
            send_cookies_to_telegram({"__cfwaitingroom__cf_wr": session_cookies["__cfwaitingroom__cf_wr"]})
            return session_cookies  # Вернём куки после успешного прохождения

        logging.info("⌛ Комната ожидания не пройдена. Ждём ещё минуту...")
        time.sleep(60)

def fetch_cookies(session):
    """ Загружает страницу и получает куки """
    try:
        logging.info("🔄 Загружаем страницу...")
        response = session.get(PAGE_URL, headers=HEADERS)
        session_cookies = session.cookies.get_dict()

        logging.info(f"🔍 Текущие куки: {json.dumps(session_cookies, indent=4, ensure_ascii=False)}")

        if "__cfwaitingroom__cf_wr" not in session_cookies:
            logging.warning("⚠️ Не найден куки __cfwaitingroom__cf_wr. Ждём, пока пройдет комнату ожидания.")
            session_cookies = wait_for_cfwaitingroom(session)  # Ожидаем прохождение

        # Небольшая задержка перед продолжением, чтобы Cloudflare точно пропустил
        time.sleep(15)

        send_cookies_to_telegram(session_cookies)

        return True
    except Exception as e:
        logging.error(f"Ошибка загрузки страницы: {str(e)}")
        return False

def login(session):
    """ Авторизация с отправкой логина и пароля """
    payload = {
        'username': EMAIL,
        'password': PASSWORD
    }

    try:
        response = session.post(LOGIN_URL, json=payload, headers=HEADERS)
        if response.status_code == 200:
            auth_data = response.json()
            logging.info("✅ Успешная авторизация!")
            send_cookies_to_telegram({"auth_data": json.dumps(auth_data, indent=4, ensure_ascii=False)})
        elif response.status_code == 403:
            logging.warning("⚠️ Ошибка 403. Доступ запрещен.")
        else:
            logging.error(f"❌ Ошибка авторизации: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Ошибка при логине: {str(e)}")

def start_periodic_update():
    """ Основной цикл работы """
    session = create_session()

    while True:
        if not fetch_cookies(session):
            logging.warning("🔄 Пересоздаём сессию...")
            session = create_session()

        login(session)

        logging.info("⏳ Ожидание 25 минут перед следующим обновлением...")
        time.sleep(1500)

if __name__ == "__main__":
    start_periodic_update()
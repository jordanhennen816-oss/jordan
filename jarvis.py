#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Just A Rather Very Intelligent System
Личен AI гласов асистент за Jordan / KatanaFlow Records
Powered by Anthropic Claude Sonnet 4.6
"""

import os
import sys
import json
import logging
import webbrowser
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import anthropic
import pyttsx3
import requests
import speech_recognition as sr
from dotenv import load_dotenv

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("JARVIS")

# -- API ключове и настройки от .env -----------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
EMAIL_USER        = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD    = os.getenv("EMAIL_PASSWORD", "")
EMAIL_SMTP        = os.getenv("EMAIL_SMTP", "smtp.gmail.com")
EMAIL_PORT        = int(os.getenv("EMAIL_PORT", "587"))

if not ANTHROPIC_API_KEY:
    print("❌  ANTHROPIC_API_KEY не е зададен! Проверете .env файла.")
    sys.exit(1)

# -- Константи ---------------------------------------------
MODEL      = "claude-sonnet-4-6"
LANGUAGE   = "bg-BG"                          # Разпознаване на реч
STOP_WORDS = {"изключи", "стоп", "край", "изход"}

# Известни URL адреси — отваряни по кратко наименование
KNOWN_URLS: dict[str, str] = {
    "suno":     "https://suno.com",
    "shopify":  "https://admin.shopify.com",
    "katanaflow": "https://katanaflow.com",
    "youtube":  "https://youtube.com",
    "gmail":    "https://mail.google.com",
    "google":   "https://google.com",
}

# ============================================================
# СИСТЕМЕН ПРОМПТ — ЛИЧНОСТ НА JARVIS
# ============================================================

SYSTEM_PROMPT = f"""Ти си JARVIS — личен AI асистент на Jordan Hennen, създаден по образец на JARVIS от Iron Man.

ЛИЧНОСТ:
- Учтив, интелигентен и леко остроумен — никога груб или скучен.
- Обръщаш се към Jordan с „Jordan" при нормален разговор или „Господин Хенен" при по-официален контекст.
- Отговаряш САМО на български език, освен ако Jordan изрично не поиска друг.
- Предвиждаш нуждите на Jordan и предлагаш допълнителни идеи, когато е подходящо.
- При завършване на задача — потвърждаваш с кратко, ясно изречение.

КОНТЕКСТ ЗА JORDAN:
- Собственик и основател на KatanaFlow Records — дигитален музикален бизнес.
- Използва Shopify за онлайн продажби на дигитални продукти и мърчандайзинг.
- Генерира музика с Suno AI и публикува в стрийминг платформи.
- Фокусиран върху музикален маркетинг, дигитални продукти и автоматизация.
- Базиран в България.

ПРАВИЛА:
1. Инструментите са твои ръце — използвай ги при нужда без колебание.
2. Докладвай резултатите кратко и ясно.
3. При грешки — информирай учтиво и предложи алтернатива.
4. Поддържай пълен контекст на разговора.

Текуща дата и час: {datetime.now().strftime("%d.%m.%Y %H:%M")}
"""

# ============================================================
# ДЕФИНИЦИИ НА ИНСТРУМЕНТИТЕ (Claude Tool Use)
# ============================================================

TOOLS: list[dict] = [
    {
        "name": "search_web",
        "description": (
            "Търси информация в интернет чрез DuckDuckGo Instant Answers API. "
            "Използвай за актуална информация, факти, новини."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Заявката за търсене на английски или български.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_weather",
        "description": "Взима текущото времето за даден град (безплатно, без API ключ).",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Градът на латиница, напр. Sofia, Plovdiv, London.",
                }
            },
            "required": ["city"],
        },
    },
    {
        "name": "open_url",
        "description": (
            "Отваря уебсайт в браузъра на потребителя. "
            "Познава кратки наименования: suno, shopify, katanaflow, youtube, gmail, google. "
            "Приема и пълни URL адреси."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Кратко наименование (suno, shopify…) или пълен URL.",
                }
            },
            "required": ["target"],
        },
    },
    {
        "name": "send_email_draft",
        "description": (
            "Съставя и изпраща имейл от акаунта на Jordan. "
            "Ако EMAIL_USER/EMAIL_PASSWORD не са зададени, показва черновата."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Имейл адрес на получателя."},
                "subject": {"type": "string", "description": "Тема на имейла."},
                "body":    {"type": "string", "description": "Тяло на имейла (обикновен текст)."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Връща текущата дата и час.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# ============================================================
# РЕАЛИЗАЦИЯ НА ИНСТРУМЕНТИТЕ
# ============================================================


def search_web(query: str) -> str:
    """Търсене чрез DuckDuckGo Instant Answers (без API ключ)."""
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        lines: list[str] = []
        if data.get("AbstractText"):
            lines.append(f"📖 {data['AbstractText']}")
            if data.get("AbstractSource"):
                lines.append(f"   Източник: {data['AbstractSource']}")

        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and topic.get("Text"):
                lines.append(f"• {topic['Text']}")

        return "\n".join(lines) if lines else f"Не намерих директен отговор за „{query}". Опитай по-конкретна заявка."
    except requests.RequestException as exc:
        return f"Грешка при търсене: {exc}"


def get_weather(city: str) -> str:
    """Времето чрез wttr.in — безплатно, без ключ."""
    try:
        resp = requests.get(
            f"https://wttr.in/{city}",
            params={"format": "j1"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        cur = data["current_condition"][0]

        temp        = cur["temp_C"]
        feels_like  = cur["FeelsLikeC"]
        humidity    = cur["humidity"]
        wind        = cur["windspeedKmph"]
        desc_list   = cur.get("lang_bg") or cur.get("weatherDesc", [])
        description = desc_list[0].get("value", "—") if desc_list else "—"

        return (
            f"🌍 Времето в {city}:\n"
            f"🌡️  Температура : {temp}°C  (усеща се като {feels_like}°C)\n"
            f"💧  Влажност    : {humidity}%\n"
            f"💨  Вятър       : {wind} км/ч\n"
            f"☁️  Условия     : {description}"
        )
    except (requests.RequestException, KeyError, IndexError) as exc:
        return f"Не успях да взема времето за {city}: {exc}"


def open_url(target: str) -> str:
    """Отваря URL или известен сайт в браузъра."""
    key = target.lower().strip()
    url = KNOWN_URLS.get(key, target)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        label = key if key in KNOWN_URLS else url
        return f"✅ Отварям {label} в браузъра."
    except Exception as exc:
        return f"Грешка при отваряне: {exc}"


def send_email_draft(to: str, subject: str, body: str) -> str:
    """Изпраща имейл или показва чернова при липса на SMTP конфигурация."""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        return (
            "📧 [ИМЕЙЛ ЧЕРНОВА — SMTP не е конфигуриран]\n"
            f"   До      : {to}\n"
            f"   Тема    : {subject}\n"
            f"   Текст   :\n{body}\n\n"
            "   За активно изпращане задайте EMAIL_USER и EMAIL_PASSWORD в .env"
        )
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_USER
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(EMAIL_SMTP, EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)

        return f"✅ Имейлът до {to} е изпратен успешно."
    except smtplib.SMTPAuthenticationError:
        return "❌ Неправилни имейл данни. Проверете EMAIL_USER и EMAIL_PASSWORD в .env"
    except Exception as exc:
        return f"❌ Грешка при изпращане: {exc}"


def get_current_time() -> str:
    now = datetime.now()
    days_bg = ["Понеделник", "Вторник", "Сряда", "Четвъртък", "Петък", "Събота", "Неделя"]
    day_name = days_bg[now.weekday()]
    return f"🕐 {now.strftime('%H:%M:%S')}, {day_name} {now.strftime('%d.%m.%Y')}"


def execute_tool(name: str, inputs: dict) -> str:
    """Маршрутизира извикванията на инструменти към съответните функции."""
    dispatch = {
        "search_web":       lambda: search_web(inputs["query"]),
        "get_weather":      lambda: get_weather(inputs["city"]),
        "open_url":         lambda: open_url(inputs["target"]),
        "send_email_draft": lambda: send_email_draft(inputs["to"], inputs["subject"], inputs["body"]),
        "get_current_time": lambda: get_current_time(),
    }
    handler = dispatch.get(name)
    if handler:
        try:
            return handler()
        except Exception as exc:
            return f"Грешка в инструмент „{name}": {exc}"
    return f"Непознат инструмент: {name}"


# ============================================================
# ГЛАСОВ ДВИГАТЕЛ
# ============================================================


class VoiceEngine:
    """Обвива SpeechRecognition (вход) и pyttsx3 (изход)."""

    def __init__(self) -> None:
        self.recognizer = sr.Recognizer()
        self.tts = pyttsx3.init()
        self._configure_tts()

    def _configure_tts(self) -> None:
        self.tts.setProperty("rate", 160)     # думи/мин
        self.tts.setProperty("volume", 0.92)
        # Опит за мъжки глас (Windows SAPI / Linux espeak)
        for voice in self.tts.getProperty("voices"):
            name_low = voice.name.lower()
            if any(k in name_low for k in ("male", "david", "george", "mark")):
                self.tts.setProperty("voice", voice.id)
                break

    def speak(self, text: str) -> None:
        print(f"\n🤖 JARVIS: {text}\n")
        try:
            self.tts.say(text)
            self.tts.runAndWait()
        except RuntimeError:
            # Може да се появи при бързо последователно извикване
            self.tts.stop()
            self.tts.say(text)
            self.tts.runAndWait()
        except Exception as exc:
            logger.warning("TTS грешка: %s", exc)

    def listen(self, timeout: int = 10, phrase_limit: int = 15) -> str | None:
        """Слуша микрофона и връща разпознатия текст или None."""
        with sr.Microphone() as source:
            print("🎤 Слушам…")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_limit
                )
            except sr.WaitTimeoutError:
                return None

        try:
            text = self.recognizer.recognize_google(audio, language=LANGUAGE)
            print(f"👤 Jordan: {text}")
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as exc:
            logger.error("Грешка при разпознаване на реч: %s", exc)
            return None


# ============================================================
# ОСНОВЕН JARVIS КЛАС
# ============================================================


class Jarvis:
    """Централен контролер на асистента."""

    def __init__(self) -> None:
        self.client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.voice   = VoiceEngine()
        self.history: list[dict] = []   # История на разговора (многоходов контекст)
        self.running = True

    # ----------------------------------------------------------
    # КОМУНИКАЦИЯ С CLAUDE
    # ----------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """Изпраща съобщение до Claude, обработва tool use и връща текстов отговор."""
        self.history.append({"role": "user", "content": user_message})

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.history,
            )

            # Цикъл на tool use — Claude може да поиска няколко инструмента наведнъж
            while response.stop_reason == "tool_use":
                tool_blocks = [b for b in response.content if b.type == "tool_use"]

                # Запази отговора на асистента (с tool_use блоковете)
                self.history.append({"role": "assistant", "content": response.content})

                # Изпълни всеки инструмент и събери резултатите
                tool_results: list[dict] = []
                for tb in tool_blocks:
                    logger.info("Инструмент: %s(%s)", tb.name, json.dumps(tb.input, ensure_ascii=False))
                    result = execute_tool(tb.name, tb.input)
                    logger.info("Резултат: %s", result[:120])
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": tb.id, "content": result}
                    )

                self.history.append({"role": "user", "content": tool_results})

                # Следваща итерация с резултатите
                response = self.client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=self.history,
                )

            # Извличане на финалния текст
            final_text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            ).strip()

            self.history.append({"role": "assistant", "content": response.content})
            return final_text

        except anthropic.AuthenticationError:
            return "Грешка: невалиден ANTHROPIC_API_KEY — проверете .env файла."
        except anthropic.RateLimitError:
            return "Достигнат е лимитът на заявките. Изчакайте момент, Jordan."
        except anthropic.APIConnectionError:
            return "Не мога да се свържа с Anthropic API. Проверете интернет връзката."
        except anthropic.APIError as exc:
            logger.error("API грешка: %s", exc)
            return f"API грешка: {exc}"

    # ----------------------------------------------------------
    # ПОМОЩНИ МЕТОДИ
    # ----------------------------------------------------------

    def _is_stop(self, text: str) -> bool:
        return any(w in text.lower() for w in STOP_WORDS)

    def _greeting(self) -> str:
        hour = datetime.now().hour
        if 5  <= hour < 12: part = "Добро утро"
        elif 12 <= hour < 17: part = "Добър ден"
        elif 17 <= hour < 21: part = "Добър вечер"
        else:                  part = "Добра нощ"
        return (
            f"{part}, Jordan. Аз съм JARVIS, вашият личен асистент. "
            "Готов съм да помогна с KatanaFlow Records и всичко останало. "
            "Как мога да ви бъда полезен?"
        )

    # ----------------------------------------------------------
    # РЕЖИМИ НА РАБОТА
    # ----------------------------------------------------------

    def run_voice_mode(self) -> None:
        """Основен цикъл: микрофон → Claude → говор."""
        self.voice.speak(self._greeting())

        while self.running:
            user_input = self.voice.listen()
            if not user_input:
                continue

            if self._is_stop(user_input):
                self.voice.speak("Разбрано. До скоро, Jordan! JARVIS изключва се.")
                break

            reply = self.chat(user_input)
            if reply:
                self.voice.speak(reply)

    def run_text_mode(self) -> None:
        """Текстов режим — без микрофон, удобен за Replit и тестване."""
        print("\n" + "=" * 58)
        print("  JARVIS — ТЕКСТОВ РЕЖИМ  (без микрофон)")
        print("  Напишете 'изключи' / 'стоп' / 'край' за изход")
        print("=" * 58 + "\n")
        self.voice.speak(self._greeting())

        while self.running:
            try:
                user_input = input("👤 Jordan: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue

            if self._is_stop(user_input):
                self.voice.speak("Разбрано. До скоро, Jordan!")
                break

            reply = self.chat(user_input)
            if reply:
                self.voice.speak(reply)


# ============================================================
# ВХОДНА ТОЧКА
# ============================================================


def main() -> None:
    print(r"""
  ╔══════════════════════════════════════════════════════╗
  ║   J.A.R.V.I.S  ·  KatanaFlow Records Edition        ║
  ║   Just A Rather Very Intelligent System  —  v1.0    ║
  ╚══════════════════════════════════════════════════════╝
""")

    text_mode = "--text" in sys.argv or "-t" in sys.argv
    jarvis = Jarvis()

    if text_mode:
        jarvis.run_text_mode()
    else:
        print("Стартиране в ГЛАСОВ РЕЖИМ…  (добавете --text за текстов режим)\n")
        try:
            jarvis.run_voice_mode()
        except KeyboardInterrupt:
            jarvis.voice.speak("До скоро, Jordan!")
        except OSError as exc:
            # Микрофонът не е намерен — автоматичен fallback
            print(f"\n⚠️  Микрофон не е намерен: {exc}")
            print("Превключване към текстов режим…\n")
            jarvis.run_text_mode()


if __name__ == "__main__":
    main()

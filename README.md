# J.A.R.V.I.S — KatanaFlow Records Edition

> *Just A Rather Very Intelligent System* — личен AI гласов асистент за Jordan, захранван от Anthropic Claude Sonnet 4.6.

---

## Функции

| Команда / Тема | Какво прави JARVIS |
|---|---|
| Свободен разговор | Отговаря на въпроси, дава идеи, помни контекста |
| „потърси X" | Търси в интернет (DuckDuckGo) |
| „времето в София" | Текущо време и температура |
| „отвори Suno / Shopify" | Отваря сайта в браузъра |
| „изпрати имейл до X" | Съставя и изпраща имейл |
| „изключи" / „стоп" / „край" | Спира асистента |

---

## Изисквания

- Python **3.11+**
- Интернет връзка
- Микрофон (за гласов режим) или само терминал (текстов режим `--text`)

---

## Инсталация — Windows

### 1. Клониране / изтегляне на проекта

```bash
git clone https://github.com/jordanhennen816-oss/jordan.git
cd jordan
```

### 2. Виртуална среда (препоръчително)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. PyAudio (специална стъпка за Windows)

PyAudio изисква предкомпилиран wheel за Windows:

```bash
pip install pipwin
pipwin install pyaudio
```

Ако `pipwin` не работи, изтеглете wheel ръчно от:
https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio (напр. `PyAudio-0.2.14-cp311-cp311-win_amd64.whl`)

```bash
pip install PyAudio-0.2.14-cp311-cp311-win_amd64.whl
```

### 4. Останалите зависимости

```bash
pip install -r requirements.txt
```

### 5. Конфигурация

```bash
copy .env.example .env
```

Редактирайте `.env` и попълнете `ANTHROPIC_API_KEY`.

### 6. Стартиране

```bash
# Гласов режим (с микрофон)
python jarvis.py

# Текстов режим (без микрофон — за тестване)
python jarvis.py --text
```

---

## Инсталация — Replit

> **Важно:** Replit не поддържа микрофон. Използвайте текстов режим (`--text`).

### 1. Импортирайте проекта

В Replit → **Create Repl** → **Import from GitHub** → вкарайте URL на хранилището.

### 2. Задайте Secrets

Replit → **Secrets** (катинарче) → добавете:

| Key | Value |
|---|---|
| `ANTHROPIC_API_KEY` | вашият ключ от console.anthropic.com |
| `EMAIL_USER` | (незадължително) |
| `EMAIL_PASSWORD` | (незадължително) |

### 3. Инсталирайте зависимостите

В Shell:

```bash
pip install anthropic SpeechRecognition pyttsx3 python-dotenv requests
```

> `PyAudio` не е необходим в Replit (няма микрофон).

### 4. Стартиране

```bash
python jarvis.py --text
```

Или задайте Run command в `.replit`:

```toml
run = "python jarvis.py --text"
```

---

## Структура на проекта

```
jordan/
├── jarvis.py          # Основен файл на асистента
├── requirements.txt   # Python зависимости
├── .env.example       # Шаблон за конфигурация
└── README.md          # Тази документация
```

---

## Конфигурационни опции (.env)

```env
# Задължително
ANTHROPIC_API_KEY=sk-ant-...

# Незадължително — имейл изпращане
EMAIL_USER=jordan@example.com
EMAIL_PASSWORD=app_password_here
EMAIL_SMTP=smtp.gmail.com
EMAIL_PORT=587
```

---

## Upgrade към ElevenLabs TTS

В `jarvis.py` намерете метода `VoiceEngine.speak()` и заменете pyttsx3 извикването:

```python
# Инсталирайте: pip install elevenlabs
from elevenlabs.client import ElevenLabs

client_el = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

def speak(self, text: str) -> None:
    print(f"\n🤖 JARVIS: {text}\n")
    audio = client_el.text_to_speech.convert(
        voice_id="YOUR_VOICE_ID",
        text=text,
        model_id="eleven_multilingual_v2",
    )
    # Записвайте и пускайте audio bytes с playsound или pygame
```

---

## Известни ограничения

- Разпознаването на реч изисква активна интернет връзка (Google Speech API).
- DuckDuckGo Instant Answers връща резюмета, не пълни резултати.
- Gmail App Password е необходима при активирана 2FA.

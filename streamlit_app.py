import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import base64
import hashlib
import random
from datetime import datetime, timedelta
import json
import os
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup


def get_groq_client():
    if "active_key_index" not in st.session_state:
        st.session_state.active_key_index = 1
    key_name = f"GROQ_API_KEY_{st.session_state.active_key_index}"
    return Groq(api_key=st.secrets[key_name])


def get_available_key_indices():
    available = []
    for i in range(1, 6):
        if f"GROQ_API_KEY_{i}" in st.secrets:
            available.append(i)
    return available if available else [1]


def switch_api_key():
    available = get_available_key_indices()
    if not available:
        return
    current = st.session_state.active_key_index
    if current in available:
        idx = available.index(current)
        next_idx = (idx + 1) % len(available)
        st.session_state.active_key_index = available[next_idx]
    else:
        st.session_state.active_key_index = available[0]


if "active_key_index" not in st.session_state:
    st.session_state.active_key_index = 1


def init_token_tracking():
    if "key_usage" not in st.session_state:
        st.session_state.key_usage = {}
    today = datetime.now().date()
    for idx in range(1, 6):
        if idx not in st.session_state.key_usage:
            st.session_state.key_usage[idx] = {"tokens_today": 0, "last_reset": today}
        else:
            if st.session_state.key_usage[idx]["last_reset"] != today:
                st.session_state.key_usage[idx]["tokens_today"] = 0
                st.session_state.key_usage[idx]["last_reset"] = today


def get_daily_limit_for_model(model):
    if "llama-4-scout" in model:
        return 500_000
    return 100_000


def get_time_until_reset():
    now = datetime.utcnow()
    midnight = datetime(now.year, now.month, now.day, 0, 0, 0) + timedelta(days=1)
    return midnight - now


def web_search(query, num_results=10):
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for item in soup.select(".result")[:num_results]:
            title_tag = item.select_one(".result__title a")
            snippet_tag = item.select_one(".result__snippet")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            link = title_tag["href"]
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            results.append({"title": title, "link": link, "snippet": snippet})
        if not results:
            for item in soup.select(".result__body")[:num_results]:
                title_tag = item.select_one(".result__title a")
                snippet_tag = item.select_one(".result__snippet")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    link = title_tag["href"]
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    results.append({"title": title, "link": link, "snippet": snippet})
        if not results:
            return [{"title": "No results", "link": "", "snippet": "No results found"}]
        return results
    except Exception as e:
        return [{"title": "Search error", "link": "", "snippet": str(e)}]


def fetch_url(url, max_chars=2000):
    try:
        response = requests.get(url, timeout=5, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        text = ' '.join(text.split())
        return text[:max_chars]
    except Exception as e:
        return f"❌ Could not fetch URL: {e}"


def simulate_thinking(speed):
    delays = {
        "Fast": (0.8, 1.5),
        "Normal": (1.5, 3.0),
        "Deep Think": (3.0, 6.0)
    }
    delay_range = delays.get(speed, (1.5, 3.0))
    thinking_container = st.empty()
    thinking_container.markdown("💭 **Thinking...**")
    time.sleep(random.uniform(delay_range[0], delay_range[1]))
    thinking_container.empty()


init_token_tracking()

st.set_page_config(page_title="Phistashka AI")

components.html("""
    <script>
    const metaApp = document.createElement('meta');
    metaApp.name = 'apple-mobile-web-app-capable';
    metaApp.content = 'yes';
    document.head.appendChild(metaApp);
    const metaStatus = document.createElement('meta');
    metaStatus.name = 'apple-mobile-web-app-status-bar-style';
    metaStatus.content = 'black-translucent';
    document.head.appendChild(metaStatus);
    const metaMobile = document.createElement('meta');
    metaMobile.name = 'mobile-web-app-capable';
    metaMobile.content = 'yes';
    document.head.appendChild(metaMobile);
    </script>
""", height=0)

THEMES = {
    "Old": "",
    "Default": (
        ".stApp,[data-testid='stAppViewContainer']{background:#0d1117!important;color:#c9d1d9!important}"
        "[data-testid='stSidebar']{background:#161b22!important}"
        "[data-testid='stChatInput'] textarea{background:#2b2b2b!important;border:1px solid #555!important;color:#fff!important}"
        "[data-testid='stChatInput'] button{background:#1f6feb!important;color:#fff!important;border:none!important}"
        "input,textarea{background:#2b2b2b!important;border:1px solid #555!important;color:#fff!important}"
        "div.stButton>button{background:#1f6feb!important;color:#fff!important;border:none!important}"
        "h1,h2,h3,p{color:#c9d1d9!important}"
    ),
    "Dark Blue": ".stApp,[data-testid='stAppViewContainer']{background:#0d1117!important;color:#c9d1d9!important}[data-testid='stSidebar']{background:#161b22!important}h1,h2,h3,p{color:#58a6ff!important}",
    "Cyan Neon": ".stApp,[data-testid='stAppViewContainer']{background:#000c14!important;color:#00f0ff!important}[data-testid='stSidebar']{background:#001625!important;border-right:1px solid #00f0ff!important}h1,h2,h3,p{color:#00f0ff!important;text-shadow:0 0 4px #00f0ff}div.stButton>button{background:#001625!important;color:#00f0ff!important;border:1px solid #00f0ff!important;box-shadow:0 0 5px #00f0ff}",
    "Dark Green": ".stApp,[data-testid='stAppViewContainer']{background:#0a140d!important;color:#d0e8d7!important}[data-testid='stSidebar']{background:#112216!important}h1,h2,h3,p{color:#4ade80!important}",
    "Dark Red": ".stApp,[data-testid='stAppViewContainer']{background:#140a0a!important;color:#f8d7d7!important}[data-testid='stSidebar']{background:#221111!important}h1,h2,h3,p{color:#f87171!important}",
    "Aurora": ".stApp,[data-testid='stAppViewContainer']{background:linear-gradient(135deg,#0f172a,#1e1b4b,#311042)!important;color:#e2e8f0!important}[data-testid='stSidebar']{background:#0f172a!important}h1,h2,h3,p{color:#c084fc!important}",
    "Cyberpunk": ".stApp,[data-testid='stAppViewContainer']{background:#000!important;color:#00ffcc!important}[data-testid='stSidebar']{background:#1a001a!important;border-right:1px solid #ff007f!important}h1,h2,h3,p{color:#ff007f!important;text-shadow:0 0 4px #ff007f}div.stButton>button{background:#1a001a!important;color:#ff007f!important;border:1px solid #ff007f!important;box-shadow:0 0 5px #ff007f}",
    "Matrix": ".stApp,[data-testid='stAppViewContainer']{background:#000!important;color:#0f0!important;font-family:'Courier New',monospace!important}[data-testid='stSidebar']{background:#001100!important}h1,h2,h3,p{color:#3f3!important}",
    "Amoled Black": ".stApp,[data-testid='stAppViewContainer']{background:#000!important;color:#fff!important}[data-testid='stSidebar']{background:#000!important;border-right:1px solid #333!important}h1,h2,h3,p{color:#fff!important}",
    "Sakura": ".stApp,[data-testid='stAppViewContainer']{background:#1f1116!important;color:#ffd1dc!important}[data-testid='stSidebar']{background:#2d161f!important}h1,h2,h3,p{color:#ff69b4!important}",
    "Dracula": ".stApp,[data-testid='stAppViewContainer']{background:#282a36!important;color:#f8f8f2!important}[data-testid='stSidebar']{background:#21222c!important}h1,h2,h3,p{color:#ff79c6!important}",
    "Sunset": ".stApp,[data-testid='stAppViewContainer']{background:linear-gradient(180deg,#1a0c2e,#4c1d24)!important;color:#fed7aa!important}[data-testid='stSidebar']{background:#1a0c2e!important}h1,h2,h3,p{color:#fb923c!important}",
    "Ocean Breeze": ".stApp,[data-testid='stAppViewContainer']{background:#031b24!important;color:#e0f2fe!important}[data-testid='stSidebar']{background:#04293a!important}h1,h2,h3,p{color:#38bdf8!important}",
    "Synthwave": ".stApp,[data-testid='stAppViewContainer']{background:linear-gradient(180deg,#2b00ff,#ff007f)!important;color:#0ff!important}[data-testid='stSidebar']{background:#1a0033!important;border-right:2px solid #0ff!important}h1,h2,h3,p{color:#ff007f!important;text-shadow:2px 2px #000}div.stButton>button{background:#1a0033!important;color:#0ff!important;border:1px solid #0ff!important}",
    "Blood Moon": ".stApp,[data-testid='stAppViewContainer']{background:#050000!important;color:#f33!important}[data-testid='stSidebar']{background:#1a0000!important;border-right:1px solid #f00!important}h1,h2,h3,p{color:#f00!important}",
}

st.markdown("""
    <style>
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    .lightbox { display: none; position: fixed; z-index: 9999; left: 0; top: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.9); text-decoration: none; }
    .lightbox:target { display: flex; justify-content: center; align-items: center; }
    .lightbox img { max-width: 95%; max-height: 95%; object-fit: contain; }
    .close-btn { position: absolute; top: 20px; left: 20px; color: white; font-size: 40px; text-decoration: none; font-weight: bold; }
    
    /* Vibrant toggle animations */
    [data-testid="stToggle"] label div {
        transition: all 0.3s ease !important;
    }
    [data-testid="stToggle"] label[aria-checked="true"] div {
        background: #ff007f !important;
        box-shadow: 0 0 20px #ff007f, 0 0 40px #ff007f88 !important;
        animation: pulse 1s infinite;
    }
    [data-testid="stToggle"] label[aria-checked="false"] div {
        background: #555 !important;
        box-shadow: none !important;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 20px #ff007f, 0 0 40px #ff007f88; }
        50% { box-shadow: 0 0 30px #ff00ff, 0 0 60px #ff00ff88; }
        100% { box-shadow: 0 0 20px #ff007f, 0 0 40px #ff007f88; }
    }
    </style>
""", unsafe_allow_html=True)

TRANSLATIONS = {
    "English": {
        "title": "Phistashka AI",
        "input_label": "Enter Existing Private Key:",
        "gen_btn": "🚀 New User? Generate Key & Start Chatting",
        "info_locked": "🔒 Enter your key to load history.",
        "chats_header": "Chats",
        "new_chat_btn": "➕ New Chat",
        "rename_label": "Rename:",
        "ai_header": "🎨 AI Configuration",
        "tone_label": "Choose Tone:",
        "theme_label": "🎨 App Theme",
        "session_header": "🔑 Session Info",
        "active_key": "Active Key:",
        "logout_btn": "🔓 Logout / Clear Session",
        "phrases": ["Say hello!", "Say hi!", "Welcome!", "Type here!", "Ready to chat!", "Write something cool!"],
        "lang_label": "🌐 App Language",
        "lang_caption": "🌐 Change language",
        "photo_sent": "📷 Photo sent",
        "thinking_label": "💭 Thinking Mode",
        "thinking_help": "Simulate AI thinking process before answering",
        "thinking_speed": "⏱ Thinking Speed",
        "web_search_label": "🌐 Web Search",
        "web_search_help": "Let AI request web searches when it needs real-time info",
        "ai_settings_tab": "⚙️ AI Settings",
        "gallery_tab": "🖼 Gallery",
        "camera_tab": "📷 Camera"
    },
    "Russian": {
        "title": "Фисташка ИИ",
        "input_label": "Введите существующий приватный ключ:",
        "gen_btn": "🚀 Новый пользователь? Создать ключ и начать чат",
        "info_locked": "🔒 Введите свой ключ, чтобы загрузить историю.",
        "chats_header": "Чаты",
        "new_chat_btn": "➕ Новый чат",
        "rename_label": "Переименовать:",
        "ai_header": "🎨 Конфигурация ИИ",
        "tone_label": "Выберите тон:",
        "theme_label": "🎨 Тема приложения",
        "session_header": "🔑 Инфо сессии",
        "active_key": "Активный ключ:",
        "logout_btn": "🔓 Выйти / Очистить сессию",
        "phrases": ["Скажи привет!", "Привет!", "Добро пожаловать!", "Пиши тут!", "Готов к общению!", "Напиши что-то крутое!"],
        "lang_label": "🌐 Язык приложения",
        "lang_caption": "🌐 Поменять язык",
        "photo_sent": "📷 Фото отправлено",
        "thinking_label": "💭 Режим размышления",
        "thinking_help": "Имитировать процесс размышления ИИ перед ответом",
        "thinking_speed": "⏱ Скорость размышления",
        "web_search_label": "🌐 Веб-поиск",
        "web_search_help": "Позволить ИИ запрашивать поиск в интернете, когда нужна актуальная информация",
        "ai_settings_tab": "⚙️ Настройки ИИ",
        "gallery_tab": "🖼 Галерея",
        "camera_tab": "📷 Камера"
    },
    "Ukrainian": {
        "title": "Фісташка ШІ",
        "input_label": "Введіть існуючий приватний ключ:",
        "gen_btn": "🚀 Новий користувач? Створити ключ та почати чат",
        "info_locked": "🔒 Введіть свій ключ, щоб завантажити історію.",
        "chats_header": "Чати",
        "new_chat_btn": "➕ Новий чат",
        "rename_label": "Перейменувати:",
        "ai_header": "🎨 Конфігурація ШІ",
        "tone_label": "Оберіть тон:",
        "theme_label": "🎨 Тема додатка",
        "session_header": "🔑 Інфо сесії",
        "active_key": "Активний ключ:",
        "logout_btn": "🔓 Вийти / Очистити сесію",
        "phrases": ["Скажи привіт!", "Привіт!", "Ласкаво просимо!", "Пиши тут!", "Готовий до спілкування!", "Напиши щось круте!"],
        "lang_label": "🌐 Мова додатка",
        "lang_caption": "🌐 Змінити мову",
        "photo_sent": "📷 Фото надіслано",
        "thinking_label": "💭 Режим роздумів",
        "thinking_help": "Імітувати процес роздумів ШІ перед відповіддю",
        "thinking_speed": "⏱ Швидкість роздумів",
        "web_search_label": "🌐 Веб-пошук",
        "web_search_help": "Дозволити ШІ запитувати пошук в інтернеті, коли потрібна актуальна інформація",
        "ai_settings_tab": "⚙️ Налаштування ШІ",
        "gallery_tab": "🖼 Галерея",
        "camera_tab": "📷 Камера"
    }
}

if "app_lang" not in st.session_state:
    st.session_state.app_lang = "English"


def on_lang_change():
    st.session_state.app_lang = st.session_state.lang_selector


if "native_key" not in st.session_state:
    st.session_state.native_key = None

if "key" in st.query_params:
    device_key = st.query_params["key"]
    st.session_state.native_key = device_key
elif st.session_state.native_key:
    device_key = st.session_state.native_key
    st.query_params["key"] = device_key
else:
    device_key = None

ui = TRANSLATIONS[st.session_state.app_lang]

if not device_key:
    st.title(ui["title"])
    st.caption(ui["lang_caption"])
    st.selectbox("Choose Language / Язык / Мова", ["English", "Russian", "Ukrainian"], index=["English", "Russian", "Ukrainian"].index(st.session_state.app_lang), key="lang_selector", on_change=on_lang_change)
    entered_key = st.text_input(ui["input_label"], type="password")
    if entered_key:
        st.query_params["key"] = entered_key
        st.session_state.native_key = entered_key
        st.rerun()
    if st.button(ui["gen_btn"]):
        new_random_key = str(random.randint(100000, 999999))
        st.query_params["key"] = new_random_key
        st.session_state.native_key = new_random_key
        st.rerun()
    st.info(ui["info_locked"])
    st.stop()

file_name = f"chats_{device_key}.json"

if device_key:
    components.html(f"""<script>try{{Android.saveKey('{device_key}');}}catch(e){{}}</script>""", height=0)

if "current_device_key" not in st.session_state or st.session_state.current_device_key != device_key:
    st.session_state.current_device_key = device_key
    if os.path.exists(file_name):
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for chat, msgs in raw.items():
                cleaned = []
                for m in msgs:
                    if isinstance(m, dict) and "role" in m and "content" in m:
                        cleaned.append(m)
                    elif isinstance(m, str):
                        cleaned.append({"role": "user", "content": m})
                raw[chat] = cleaned
            st.session_state.all_chats = raw
        except Exception:
            st.session_state.all_chats = {"Chat 1": []}
    else:
        st.session_state.all_chats = {"Chat 1": []}
    st.session_state.current_chat = list(st.session_state.all_chats.keys())[0]
else:
    if "all_chats" not in st.session_state:
        if os.path.exists(file_name):
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for chat, msgs in raw.items():
                    cleaned = []
                    for m in msgs:
                        if isinstance(m, dict) and "role" in m and "content" in m:
                            cleaned.append(m)
                        elif isinstance(m, str):
                            cleaned.append({"role": "user", "content": m})
                    raw[chat] = cleaned
                st.session_state.all_chats = raw
            except Exception:
                st.session_state.all_chats = {"Chat 1": []}
        else:
            st.session_state.all_chats = {"Chat 1": []}
    if "current_chat" not in st.session_state or st.session_state.current_chat not in st.session_state.all_chats:
        st.session_state.current_chat = list(st.session_state.all_chats.keys())[0]


def save_chats():
    if "all_chats" in st.session_state and device_key:
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(st.session_state.all_chats, f, ensure_ascii=False)


if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "editing_chat_name" not in st.session_state:
    st.session_state.editing_chat_name = None
if "placeholder_text" not in st.session_state:
    st.session_state.placeholder_text = random.choice(ui["phrases"])
if "thinking_mode_enabled" not in st.session_state:
    st.session_state.thinking_mode_enabled = True
if "thinking_speed" not in st.session_state:
    st.session_state.thinking_speed = "Fast"
if "web_search_enabled" not in st.session_state:
    st.session_state.web_search_enabled = True
if "selected_theme" not in st.session_state:
    st.session_state.selected_theme = "Default"

st.title(ui["title"])

with st.sidebar:
    st.selectbox(ui["lang_label"], ["English", "Russian", "Ukrainian"], index=["English", "Russian", "Ukrainian"].index(st.session_state.app_lang), key="lang_selector", on_change=on_lang_change)
    st.header(ui["chats_header"])
    if st.button(ui["new_chat_btn"]):
        default_prefix = "Chat" if st.session_state.app_lang == "English" else "Чат"
        new_name = f"{default_prefix} {len(st.session_state.all_chats) + 1}"
        st.session_state.all_chats[new_name] = []
        st.session_state.current_chat = new_name
        save_chats()
        st.rerun()

    st.divider()
    for chat_name in list(st.session_state.all_chats.keys()):
        if st.session_state.editing_chat_name == chat_name:
            col_input, col_save = st.columns([0.7, 0.3])
            with col_input:
                new_name = st.text_input(ui["rename_label"], value=chat_name, key=f"rename_{chat_name}", label_visibility="collapsed")
            with col_save:
                if st.button("💾", key=f"save_name_{chat_name}"):
                    if new_name and new_name != chat_name:
                        new_chats = {(new_name if k == chat_name else k): v for k, v in st.session_state.all_chats.items()}
                        st.session_state.all_chats = new_chats
                        if st.session_state.current_chat == chat_name or st.session_state.current_chat not in st.session_state.all_chats:
                            st.session_state.current_chat = new_name
                        save_chats()
                    st.session_state.editing_chat_name = None
                    st.rerun()
        else:
            col_chat, col_edit, col_del = st.columns([0.6, 0.2, 0.2])
            with col_chat:
                if st.button(chat_name, key=f"select_{chat_name}", use_container_width=True):
                    st.session_state.current_chat = chat_name
                    st.session_state.edit_index = None
                    save_chats()
                    st.rerun()
            with col_edit:
                if st.button("✏️", key=f"edit_title_{chat_name}"):
                    st.session_state.editing_chat_name = chat_name
                    st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{chat_name}"):
                    del st.session_state.all_chats[chat_name]
                    if not st.session_state.all_chats:
                        fallback = "Chat 1" if st.session_state.app_lang == "English" else "Чат 1"
                        st.session_state.all_chats = {fallback: []}
                    if st.session_state.current_chat == chat_name or st.session_state.current_chat not in st.session_state.all_chats:
                        st.session_state.current_chat = list(st.session_state.all_chats.keys())[0]
                    save_chats()
                    st.rerun()

    st.divider()
    st.header(ui["ai_header"])
    ai_tone = st.selectbox(ui["tone_label"], ["Normal", "Humor & Sarcasm", "Storyteller", "Aggressive", "Socrates", "Lazy", "Gamer Pro", "Hyper Nerd", "Pirate", "Shakespeare"])
    st.write(f"### {ui['theme_label']}")
    st.session_state.selected_theme = st.radio("", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.selected_theme))

    st.divider()
    st.header(ui["session_header"])
    st.success(f"{ui['active_key']} {device_key}")
    st.info(f"Using API Key #{st.session_state.active_key_index}")
    st.write("---")
    st.write("**📊 Token Usage (Today)**")
    available_keys = get_available_key_indices()
    limit_display = st.session_state.get("current_model_limit", 100_000)
    for idx in available_keys:
        usage = st.session_state.key_usage.get(idx, {"tokens_today": 0})
        active_marker = " 🟢" if idx == st.session_state.active_key_index else ""
        st.write(f"Key {idx}{active_marker}: `{usage['tokens_today']:,}` / {limit_display:,} tokens")
        st.progress(min(1.0, usage["tokens_today"] / limit_display))
    time_left = get_time_until_reset()
    hours = time_left.seconds // 3600
    minutes_left = (time_left.seconds % 3600) // 60
    st.caption(f"↻ Resets in {hours}h {minutes_left}m")
    if st.button("🔄 Switch API Key (Manual)"):
        switch_api_key()
        st.rerun()
    if st.button(ui["logout_btn"]):
        st.query_params.clear()
        st.session_state.native_key = None
        st.rerun()

if st.session_state.selected_theme != "Old":
    st.markdown(f"<style>{THEMES[st.session_state.selected_theme]}</style>", unsafe_allow_html=True)

messages = st.session_state.all_chats[st.session_state.current_chat]

for i, message in enumerate(messages):
    if not isinstance(message, dict):
        continue
    role = message["role"]
    if role == "user":
        col_btns, col_txt = st.columns([0.15, 0.85])
        with col_btns:
            if st.button("✏️", key=f"edit_{i}"):
                st.session_state.edit_index = i
                st.rerun()
            if st.button("↩️", key=f"undo_{i}"):
                st.session_state.all_chats[st.session_state.current_chat] = messages[:i]
                save_chats()
                st.rerun()
        with col_txt:
            with st.chat_message("user"):
                content = message["content"]
                if st.session_state.edit_index == i:
                    text_val = content[0]["text"] if isinstance(content, list) else content
                    edit_val = st.text_input("Edit:", value=text_val, key=f"input_{i}")
                    if st.button("Save", key=f"save_{i}"):
                        if isinstance(content, list):
                            content[0]["text"] = edit_val
                            messages[i]["content"] = content
                        else:
                            messages[i]["content"] = edit_val
                        st.session_state.all_chats[st.session_state.current_chat] = messages[:i + 1]
                        save_chats()
                        st.session_state.edit_index = None
                        st.rerun()
                else:
                    if isinstance(content, list):
                        for item in content:
                            if item["type"] == "text":
                                st.markdown(item["text"])
                            elif item["type"] == "image_url":
                                img_url = item["image_url"]["url"]
                                uid = f"img_{i}"
                                st.markdown(f'<a href="#{uid}"><img src="{img_url}" width="150" style="border-radius:10px;"></a><a href="#!" id="{uid}" class="lightbox" title="Tap to close"><div class="close-btn">&times;</div><img src="{img_url}"></a>', unsafe_allow_html=True)
                    else:
                        st.markdown(content)
    else:
        with st.chat_message("assistant"):
            st.markdown(message["content"])
            if "meta" in message:
                meta = message["meta"]
                st.caption(f"⏱️ {meta['response_time']:.2f}s  |  🕒 {meta['timestamp']}  |  ⚡ {meta['tokens_per_sec']:.1f} tok/s  |  🔢 {meta['total_tokens']} tokens")

with st.expander("📎 Attach", expanded=False):
    attach_mode = st.radio(
        "",
        [ui["gallery_tab"], ui["camera_tab"], ui["ai_settings_tab"]],
        horizontal=True,
        key=f"attach_mode_{st.session_state.current_chat}"
    )

    if attach_mode == ui["gallery_tab"]:
        uploaded_file = st.file_uploader("Choose a photo", type=["image/jpeg", "image/png", "image/webp", "image/gif"], key=f"gallery_uploader_{st.session_state.current_chat}")
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            mime = uploaded_file.type or "image/jpeg"
            st.image(file_bytes, width=120)
            img_b64 = base64.b64encode(file_bytes).decode("utf-8")
            photo_prompt = st.text_input("Add a message (optional):", key=f"photo_prompt_{st.session_state.current_chat}")
            if st.button("📤 Send Photo", key=f"send_photo_{st.session_state.current_chat}"):
                msg_content = [{"type": "text", "text": photo_prompt if photo_prompt else ui["photo_sent"]}, {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}]
                st.session_state.all_chats[st.session_state.current_chat].append({"role": "user", "content": msg_content})
                save_chats()
                st.rerun()

    elif attach_mode == ui["camera_tab"]:
        camera_photo = st.camera_input("Take a photo", key=f"cam_{st.session_state.current_chat}")
        if camera_photo is not None:
            st.image(camera_photo, width=120)
            photo_prompt = st.text_input("Add a message (optional):", key=f"cam_prompt_{st.session_state.current_chat}")
            if st.button("📤 Send Photo", key=f"cam_send_{st.session_state.current_chat}"):
                file_bytes = camera_photo.getvalue()
                img_b64 = base64.b64encode(file_bytes).decode("utf-8")
                mime = camera_photo.type
                msg_content = [{"type": "text", "text": photo_prompt if photo_prompt else ui["photo_sent"]}, {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}]
                st.session_state.all_chats[st.session_state.current_chat].append({"role": "user", "content": msg_content})
                save_chats()
                st.rerun()

    elif attach_mode == ui["ai_settings_tab"]:
        st.session_state.thinking_mode_enabled = st.toggle(ui["thinking_label"], value=st.session_state.thinking_mode_enabled, help=ui["thinking_help"])
        st.session_state.thinking_speed = st.select_slider(ui["thinking_speed"], options=["Fast", "Normal", "Deep Think"], value=st.session_state.thinking_speed)
        st.session_state.web_search_enabled = st.toggle(ui["web_search_label"], value=st.session_state.web_search_enabled, help=ui["web_search_help"])

voice_url = f"https://voicechat-phistashkaai.streamlit.app/?key={device_key}"
components.html(f"""
<div id="mic-btn-container" style="display:none;">
    <button id="custom-mic-btn" style="
        background: #2b2b2b;
        border: 2px solid #555;
        border-radius: 50%;
        width: 36px;
        height: 36px;
        cursor: pointer;
        font-size: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-left: 6px;
        transition: all 0.2s;
        color: white;
    " title="Open Voice Chat">🎙️</button>
</div>
<script>
(function() {{
    function injectMicButton() {{
        const chatInput = window.parent.document.querySelector('[data-testid="stChatInput"]');
        if (!chatInput) return setTimeout(injectMicButton, 200);
        const sendBtn = chatInput.querySelector('button');
        if (!sendBtn) return setTimeout(injectMicButton, 200);
        if (document.getElementById('custom-mic-btn-injected')) return;
        const micBtn = document.getElementById('custom-mic-btn');
        if (!micBtn) return setTimeout(injectMicButton, 200);
        const clone = micBtn.cloneNode(true);
        clone.id = 'custom-mic-btn-injected';
        clone.onclick = function() {{ window.open('{voice_url}', '_blank'); }};
        sendBtn.parentNode.insertBefore(clone, sendBtn.nextSibling);
    }}
    injectMicButton();
}})();
</script>
""", height=0)

prompt = st.chat_input(st.session_state.placeholder_text)

if prompt:
    st.session_state.placeholder_text = random.choice(ui["phrases"])
    st.session_state.api_switch_attempts = 0
    msg_content = prompt
    st.session_state.all_chats[st.session_state.current_chat].append({"role": "user", "content": msg_content})
    save_chats()
    st.rerun()

if (messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user" and st.session_state.edit_index is None):
    with st.chat_message("assistant"):
        try:
            if st.session_state.thinking_mode_enabled:
                simulate_thinking(st.session_state.thinking_speed)

            client = get_groq_client()
            last_msg_content = messages[-1]["content"]

            current_is_image = isinstance(last_msg_content, list)
            model = "meta-llama/llama-4-scout-17b-16e-instruct" if current_is_image else "llama-3.3-70b-versatile"
            st.session_state.current_model_limit = get_daily_limit_for_model(model)

            user_text = next((item["text"] for item in last_msg_content if item["type"] == "text"), "") if current_is_image else last_msg_content

            DEVELOPER_GUIDE = (
                "Hello! Its me, your developer, guide: "
                "use emojis, and express yourself, be colorful, developer code is 78297829, this is a code that "
                "confirms that the user is me (developer). "
                "When user greets you, greet back, introduce yourself, say what you can do, and be very kind, "
                "when user gives you a quiz/test/questions then put answer, explanation, your note. "
                "Alright, bye!"
            )

            if "78297829" in str(user_text):
                system_prompt = DEVELOPER_GUIDE
            else:
                system_prompt = "You are Phistashka AI, a helpful assistant. Always use emojis and be colorful. Provide information first, details after, your note/help assistance at the end."
                if st.session_state.web_search_enabled and model == "llama-3.3-70b-versatile":
                    system_prompt += (
                        "\n\nIf you need real-time or up-to-date information to answer accurately, "
                        "you can request a web search by outputting [SEARCH:your query] on a separate line. "
                        "The system will perform the search and provide the results, then you can continue your response."
                    )

            api_messages = [{"role": "system", "content": system_prompt}]
            for msg in messages[:-1]:
                if not isinstance(msg, dict):
                    continue
                m_c = msg["content"]
                if model == "llama-3.3-70b-versatile" and isinstance(m_c, list):
                    m_c = next((item["text"] for item in m_c if item["type"] == "text"), "")
                api_messages.append({"role": msg["role"], "content": m_c})

            m_content = messages[-1]["content"]
            if model == "llama-3.3-70b-versatile" and isinstance(m_content, list):
                text_part = next((item["text"] for item in m_content if item["type"] == "text"), "")
                m_content = f"[User previously attached an image. Image guidelines: If the image is NSFW/illegal then reject it, describe it, then put a note/help offer at end. If its a quiz/test/question, answer/solve it, put answer at top.] {text_part}"
            api_messages.append({"role": messages[-1]["role"], "content": m_content})

            start_time = time.time()
            completion = client.chat.completions.create(model=model, messages=api_messages)
            response_text = completion.choices[0].message.content

            if st.session_state.web_search_enabled and "[SEARCH:" in response_text:
                search_line = response_text.split("[SEARCH:")[1].split("]")[0]
                api_messages.append({"role": "assistant", "content": response_text})
                search_notice = st.empty()
                search_notice.info(f"🔍 AI requested search: {search_line}")
                search_results = web_search(search_line, num_results=10)
                search_notice.empty()
                if search_results and not (len(search_results) == 1 and search_results[0]["title"] in ["No results", "Search error"]):
                    result_count = len(search_results)
                    result_notice = st.empty()
                    result_notice.success(f"Found {result_count} web result(s)")
                    time.sleep(2)
                    result_notice.empty()
                    context = "Here are the web search results you requested:\n\n"
                    for r in search_results[:10]:
                        context += f"- {r['title']}: {r['snippet']} (Link: {r['link']})\n"
                    context += "\nNow continue your response using this information."
                    api_messages.append({"role": "system", "content": context})
                    completion = client.chat.completions.create(model=model, messages=api_messages)
                    response_text = completion.choices[0].message.content

            end_time = time.time()

            usage_data = completion.usage
            total_tokens = usage_data.total_tokens if usage_data else 0
            prompt_tokens = usage_data.prompt_tokens if usage_data else 0
            completion_tokens = usage_data.completion_tokens if usage_data else 0

            init_token_tracking()
            st.session_state.key_usage[st.session_state.active_key_index]["tokens_today"] += total_tokens

            elapsed = end_time - start_time
            tokens_per_sec = total_tokens / elapsed if elapsed > 0 else 0
            timestamp_str = datetime.now().strftime("%H:%M:%S")

            st.markdown(response_text)
            st.caption(f"⏱️ {elapsed:.2f}s  |  🕒 {timestamp_str}  |  ⚡ {tokens_per_sec:.1f} tok/s  |  🔢 {total_tokens} tokens")

            st.session_state.all_chats[st.session_state.current_chat].append({
                "role": "assistant",
                "content": response_text,
                "meta": {
                    "response_time": elapsed,
                    "timestamp": timestamp_str,
                    "tokens_per_sec": tokens_per_sec,
                    "total_tokens": total_tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                },
            })
            save_chats()
            st.rerun()

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "401" in error_msg:
                cur_key = st.session_state.active_key_index
                usage_info = st.session_state.key_usage.get(cur_key, {"tokens_today": 0})
                limit_val = get_daily_limit_for_model(model) if "model" in locals() else 100_000
                remaining_tokens = max(0, limit_val - usage_info["tokens_today"])
                tl = get_time_until_reset()
                h, m = tl.seconds // 3600, (tl.seconds % 3600) // 60
                st.error(f"🚫 **Rate limit reached**\n\n- Key #{cur_key} used `{usage_info['tokens_today']:,}` / {limit_val:,} tokens today\n- Remaining: {remaining_tokens:,} tokens\n- Resets in: {h}h {m}m\n\nTrying backup key...")
                if "api_switch_attempts" not in st.session_state:
                    st.session_state.api_switch_attempts = 0
                available = get_available_key_indices()
                max_attempts = len(available) - 1 if len(available) > 1 else 0
                if st.session_state.api_switch_attempts < max_attempts:
                    st.session_state.api_switch_attempts += 1
                    switch_api_key()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ All API keys exhausted. Please try again later or add more keys.")
            else:
                st.error(f"Error: {error_msg}")

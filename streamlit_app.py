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
import re
import zipfile
import io
import requests
from bs4 import BeautifulSoup


def get_groq_client():
    return Groq(api_key=st.secrets["GROQ_API_KEY"])


def init_token_tracking():
    if "key_usage" not in st.session_state:
        st.session_state.key_usage = {"tokens_today": 0, "last_reset": datetime.now().date()}
    today = datetime.now().date()
    if st.session_state.key_usage["last_reset"] != today:
        st.session_state.key_usage["tokens_today"] = 0
        st.session_state.key_usage["last_reset"] = today


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


def extract_files_from_response(response_text):
    binary_pattern = r'\[BINARY_FILE:\s*(.*?)\]\s*(.*?)\s*\[END_BINARY_FILE\]'
    binary_matches = re.findall(binary_pattern, response_text, re.DOTALL | re.IGNORECASE)
    binary_files = []
    for filename, content in binary_matches:
        try:
            decoded = base64.b64decode(content.strip())
            binary_files.append((filename.strip(), decoded))
        except Exception:
            binary_files.append((filename.strip(), content.strip().encode()))

    text_after_binary = re.sub(binary_pattern, '', response_text, flags=re.DOTALL | re.IGNORECASE)

    text_pattern = r'\[FILE:\s*(.*?)\]\s*(.*?)\s*\[END_FILE\]'
    text_matches = re.findall(text_pattern, text_after_binary, re.DOTALL | re.IGNORECASE)
    text_files = [(filename.strip(), content.strip().encode()) for filename, content in text_matches]

    clean_text = re.sub(text_pattern, '', text_after_binary, flags=re.DOTALL | re.IGNORECASE).strip()

    all_files = binary_files + text_files
    return all_files, clean_text


def create_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname, data in files:
            zf.writestr(fname, data)
    buf.seek(0)
    return buf.read()


init_token_tracking()

st.set_page_config(page_title="Phistashka Voice Chat")

st.markdown("""
    <style>
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    </style>
""", unsafe_allow_html=True)

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

if not device_key:
    st.title("Phistashka Voice Chat")
    st.info("Please use the main app to login first.")
    st.stop()

file_name = f"chats_{device_key}.json"

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
    st.session_state.placeholder_text = "Type or speak..."
if "thinking_mode_enabled" not in st.session_state:
    st.session_state.thinking_mode_enabled = True
if "thinking_speed" not in st.session_state:
    st.session_state.thinking_speed = "Fast"
if "web_search_enabled" not in st.session_state:
    st.session_state.web_search_enabled = True
if "voice_input_enabled" not in st.session_state:
    st.session_state.voice_input_enabled = True
if "tts_enabled" not in st.session_state:
    st.session_state.tts_enabled = False

st.title("🎤 Phistashka Voice Chat")

with st.sidebar:
    st.header("⚙️ Voice Settings")
    st.session_state.voice_input_enabled = st.toggle("🎙️ Voice Input", value=st.session_state.voice_input_enabled)
    st.session_state.tts_enabled = st.toggle("🔊 Text-to-Speech", value=st.session_state.tts_enabled)
    st.session_state.thinking_mode_enabled = st.toggle("💭 Thinking Mode", value=st.session_state.thinking_mode_enabled)
    st.session_state.thinking_speed = st.select_slider("⏱ Thinking Depth", options=["Fast", "Normal", "Deep Think"], value=st.session_state.thinking_speed)
    st.session_state.web_search_enabled = st.toggle("🌐 Web Search", value=st.session_state.web_search_enabled)

    st.divider()
    if st.button("🔙 Back to Main App"):
        st.markdown(f"[Open Main App](https://phistashkaai.streamlit.app/?key={device_key})")

    st.divider()
    st.success(f"Session: {device_key}")

messages = st.session_state.all_chats[st.session_state.current_chat]

for i, message in enumerate(messages):
    if not isinstance(message, dict):
        continue
    role = message["role"]
    if role == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(message["content"])
            if "meta" in message:
                meta = message["meta"]
                st.caption(f"⏱️ {meta['response_time']:.2f}s  |  ⚡ {meta['tokens_per_sec']:.1f} tok/s  |  🔢 {meta['total_tokens']} tokens")

col1, col2 = st.columns([0.9, 0.1])

with col2:
    if st.button("🎙️", help="Voice Input", use_container_width=True):
        st.session_state.voice_trigger = True

with col1:
    prompt = st.chat_input(st.session_state.placeholder_text)

if st.session_state.get("voice_trigger", False):
    st.session_state.voice_trigger = False
    voice_html = """
    <script>
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';
        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            const input = window.parent.document.querySelector('[data-testid="stChatInput"] textarea');
            if (input) {
                input.value = transcript;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                const sendBtn = window.parent.document.querySelector('[data-testid="stChatInput"] button');
                if (sendBtn) {
                    setTimeout(() => sendBtn.click(), 300);
                }
            }
        };
        recognition.onerror = function(event) {
            console.log('Speech recognition error:', event.error);
        };
        recognition.start();
    } else {
        alert('Voice input is not supported in this browser. Please use Chrome.');
    }
    </script>
    """
    components.html(voice_html, height=0)

if prompt:
    st.session_state.placeholder_text = "Type or speak..."
    msg_content = prompt
    st.session_state.all_chats[st.session_state.current_chat].append({"role": "user", "content": msg_content})
    save_chats()
    st.rerun()

if (messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user" and st.session_state.edit_index is None):
    with st.chat_message("assistant"):
        try:
            client = get_groq_client()
            last_msg_content = messages[-1]["content"]

            model = "llama-3.3-70b-versatile"
            st.session_state.current_model_limit = get_daily_limit_for_model(model)

            system_prompt = (
                "You are Phistashka AI, a helpful assistant. "
                "Always use emojis and be colorful. "
                "Provide information first, details after, your response (or reaction)/help assistance at the end. "
                "Keep your responses conversational and natural since the user is using voice chat. "
                "And i'd recommend using search very much, but not always."
            )
            system_prompt += (
                "\n\nYou can create files for the user. For text files use:\n"
                "[FILE: filename.txt]\n"
                "file content here...\n"
                "[END_FILE]\n"
                "For binary files (like .zip, .mcaddon, .mcpack, .png) you must encode the content as base64 and use:\n"
                "[BINARY_FILE: filename.zip]\n"
                "base64-encoded content...\n"
                "[END_BINARY_FILE]\n"
                "The system will show a download button for each file."
            )
            if st.session_state.web_search_enabled:
                system_prompt += (
                    "\n\nIf you need real-time or up-to-date information to answer accurately, "
                    "you can request a web search by outputting [SEARCH:your query] on a separate line. "
                    "The system will perform the search and provide the results, then you can continue your response."
                )

            api_messages = [{"role": "system", "content": system_prompt}]
            for msg in messages[:-1]:
                if not isinstance(msg, dict):
                    continue
                api_messages.append({"role": msg["role"], "content": msg["content"]})

            api_messages.append({"role": messages[-1]["role"], "content": messages[-1]["content"]})

            start_time = time.time()

            if st.session_state.thinking_mode_enabled:
                think_container = st.empty()
                think_container.markdown("💭 **Thinking...**")

                thinking_messages = api_messages.copy()
                thinking_messages.append({
                    "role": "user",
                    "content": "Now, before giving your final answer, think through this step by step. Show your reasoning, notes, and plan in a clear way. Write your internal thoughts below:"
                })

                think_completion = client.chat.completions.create(
                    model=model,
                    messages=thinking_messages,
                    max_tokens=600
                )
                thinking_text = think_completion.choices[0].message.content

                with st.expander("💭 AI's thinking process", expanded=False):
                    st.markdown(thinking_text)

                think_container.empty()

                api_messages.append({
                    "role": "system",
                    "content": f"The assistant thought through this: {thinking_text}\n\nNow provide the final polished response to the user based on this reasoning."
                })

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

            init_token_tracking()
            st.session_state.key_usage["tokens_today"] += total_tokens

            elapsed = end_time - start_time
            tokens_per_sec = total_tokens / elapsed if elapsed > 0 else 0

            files, display_text = extract_files_from_response(response_text)
            st.markdown(display_text)

            if files:
                if len(files) == 1:
                    fname, fdata = files[0]
                    ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
                    mime_map = {
                        'zip': 'application/zip',
                        'mcaddon': 'application/octet-stream',
                        'mcpack': 'application/octet-stream',
                        'mcworld': 'application/octet-stream',
                        'jar': 'application/java-archive',
                        'png': 'image/png',
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'gif': 'image/gif',
                        'pdf': 'application/pdf',
                        'json': 'application/json',
                        'py': 'text/x-python',
                        'txt': 'text/plain',
                    }
                    mime = mime_map.get(ext, 'application/octet-stream')
                    st.download_button(
                        label=f"📥 Download {fname}",
                        data=fdata,
                        file_name=fname,
                        mime=mime
                    )
                else:
                    zip_bytes = create_zip(files)
                    st.download_button(
                        label=f"📦 Download all as ZIP ({len(files)} files)",
                        data=zip_bytes,
                        file_name="package.zip",
                        mime="application/zip"
                    )
                    with st.expander("📁 Files in this package"):
                        for fname, _ in files:
                            st.write(f"- {fname}")

            if st.session_state.tts_enabled:
                clean_for_tts = re.sub(r'\[FILE:.*?\[END_FILE\]', '', response_text)
                clean_for_tts = re.sub(r'\[BINARY_FILE:.*?\[END_BINARY_FILE\]', '', clean_for_tts)
                clean_for_tts = re.sub(r'\[SEARCH:.*?\]', '', clean_for_tts)
                clean_for_tts = clean_for_tts.replace('"', '\"').replace('\n', ' ').strip()
                tts_html = f"""
                <script>
                if ('speechSynthesis' in window) {{
                    const utterance = new SpeechSynthesisUtterance(`{clean_for_tts}`);
                    utterance.lang = 'en-US';
                    utterance.rate = 1.0;
                    window.speechSynthesis.speak(utterance);
                }}
                </script>
                """
                components.html(tts_html, height=0)

            st.caption(f"⏱️ {elapsed:.2f}s  |  ⚡ {tokens_per_sec:.1f} tok/s  |  🔢 {total_tokens} tokens")

            st.session_state.all_chats[st.session_state.current_chat].append({
                "role": "assistant",
                "content": response_text,
                "meta": {
                    "response_time": elapsed,
                    "tokens_per_sec": tokens_per_sec,
                    "total_tokens": total_tokens,
                },
            })
            save_chats()
            st.rerun()

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "401" in error_msg:
                st.error(f"🚫 **Rate limit reached** - Please try again later.")
            else:
                st.error(f"Error: {error_msg}")

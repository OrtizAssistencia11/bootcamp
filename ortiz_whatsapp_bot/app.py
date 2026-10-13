import os
import re
import sqlite3
import unicodedata
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

DB_PATH = os.getenv("DB_PATH", "bot.db")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "troque-este-token")
WA_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
OWNER_PHONE = os.getenv("OWNER_PHONE", "").replace("+", "").replace(" ", "").replace("-", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        direction TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS faq (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS unanswered (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        question TEXT NOT NULL,
        normalized TEXT NOT NULL,
        hits INTEGER DEFAULT 1,
        notified INTEGER DEFAULT 0,
        approved_faq_id INTEGER,
        last_seen TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()


def normalize(text):
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    return text


def log_message(phone, direction, text):
    conn = db()
    conn.execute(
        "INSERT INTO messages(phone,direction,text,created_at) VALUES(?,?,?,?)",
        (phone, direction, text, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_faqs():
    conn = db()
    rows = conn.execute(
        "SELECT question, answer FROM faq WHERE active=1 ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return rows


def find_faq(text):
    n = normalize(text)
    best = None
    best_score = 0

    # Matching simples por palavras. Para uma base pequena funciona muito bem.
    stop = {"a", "o", "os", "as", "de", "do", "da", "e", "é", "um", "uma",
            "para", "por", "no", "na", "em", "com", "que", "qual", "quanto"}
    words = {w for w in re.findall(r"[a-z0-9]+", n) if w not in stop}

    for row in get_faqs():
        qwords = {w for w in re.findall(r"[a-z0-9]+", normalize(row["question"])) if w not in stop}
        if not qwords:
            continue
        score = len(words & qwords) / max(len(qwords), 1)
        if score > best_score:
            best_score = score
            best = row

    return best if best_score >= 0.60 else None


def register_unanswered(phone, question):
    n = normalize(question)
    conn = db()
    row = conn.execute(
        "SELECT id, hits, notified FROM unanswered WHERE normalized=?",
        (n,)
    ).fetchone()

    if row:
        hits = row["hits"] + 1
        conn.execute(
            "UPDATE unanswered SET hits=?, last_seen=? WHERE id=?",
            (hits, datetime.now().isoformat(), row["id"])
        )
    else:
        hits = 1
        conn.execute(
            """INSERT INTO unanswered
            (phone,question,normalized,hits,notified,last_seen)
            VALUES(?,?,?,?,?,?)""",
            (phone, question, n, 1, 0, datetime.now().isoformat())
        )

    conn.commit()
    conn.close()
    return hits


def send_whatsapp(to, text):
    if not WA_TOKEN or not PHONE_NUMBER_ID:
        print("WhatsApp não configurado. Mensagem:", text)
        return False

    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text[:4096]}
    }
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=payload, headers=headers, timeout=20)
    if not r.ok:
        print("Erro WhatsApp:", r.status_code, r.text)
    return r.ok


def notify_owner(phone, question):
    if not OWNER_PHONE:
        return

    text = (
        "🔔 *Cliente pediu atendimento humano*\n\n"
        f"📱 Cliente: {phone}\n"
        f"💬 Pergunta: {question}\n\n"
        "Responda o cliente diretamente pelo WhatsApp Business."
    )
    send_whatsapp(OWNER_PHONE, text)


def ai_answer(phone, question):
    if not client:
        return (
            "Não encontrei essa informação na minha base ainda. 😅\n"
            "Se quiser, posso encaminhar você para um atendente."
        )

    faq_text = "\n".join(
        f"- Pergunta: {r['question']}\n  Resposta: {r['answer']}"
        for r in get_faqs()
    )

    system = f"""
Você é o atendente virtual da Ortiz Assistência Técnica.

Regras:
- Responda em português do Brasil.
- Seja curto, educado e natural para WhatsApp.
- Ajude sobre manutenção de celular, tablet, PC e notebook.
- Não invente preços, prazos, garantia, peças ou diagnósticos.
- Se a informação não estiver disponível, diga que precisa de avaliação/orçamento.
- Nunca diga que fez algo que não fez.
- Se o cliente pedir humano, dono, atendente ou orçamento personalizado, indique atendimento humano.
- Use a base abaixo como fonte principal.

BASE DE FAQ:
{faq_text}
""".strip()

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=system,
        input=question,
    )
    return response.output_text.strip()


def process_message(phone, text):
    log_message(phone, "incoming", text)
    n = normalize(text)

    human_words = [
        "atendente", "humano", "pessoa", "dono", "responsavel",
        "responsável", "falar com voce", "falar com você",
        "quero falar com alguem", "quero falar com alguém"
    ]

    if any(w in n for w in human_words):
        notify_owner(phone, text)
        answer = (
            "Claro! 👍 Já avisei o responsável pela assistência. "
            "Assim que possível, ele continua o atendimento por aqui."
        )
        log_message(phone, "outgoing", answer)
        return answer

    faq = find_faq(text)
    if faq:
        answer = faq["answer"]
    else:
        hits = register_unanswered(phone, text)

        # A partir de 3 ocorrências, avisa o dono que essa pergunta merece virar FAQ.
        if hits == 3:
            notify_owner(
                phone,
                f"📚 Pergunta frequente detectada 3x:\n\n{text}\n\n"
                "Vale cadastrar uma resposta na tabela FAQ do bot."
            )

        answer = ai_answer(phone, text)

    log_message(phone, "outgoing", answer)
    return answer


@app.get("/webhook")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Token inválido", 403


@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                for message in value.get("messages", []):
                    if message.get("type") != "text":
                        continue

                    phone = message.get("from")
                    text = message.get("text", {}).get("body", "").strip()

                    if not phone or not text:
                        continue

                    answer = process_message(phone, text)
                    send_whatsapp(phone, answer)

    except Exception as e:
        print("Erro no webhook:", repr(e))

    return jsonify({"status": "ok"}), 200


@app.get("/health")
def health():
    return jsonify({"status": "online", "service": "Ortiz WhatsApp Bot"})


@app.get("/faq")
def faq_list():
    conn = db()
    rows = conn.execute(
        "SELECT id, question, answer, active FROM faq ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.post("/faq")
def faq_create():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()

    if not question or not answer:
        return jsonify({"error": "question e answer são obrigatórios"}), 400

    conn = db()
    cur = conn.execute(
        "INSERT INTO faq(question,answer,created_at) VALUES(?,?,?)",
        (question, answer, datetime.now().isoformat())
    )
    conn.commit()
    faq_id = cur.lastrowid
    conn.close()

    return jsonify({"id": faq_id, "message": "FAQ cadastrada"}), 201


@app.get("/learning")
def learning():
    conn = db()
    rows = conn.execute(
        """SELECT id, question, hits, last_seen, approved_faq_id
           FROM unanswered
           ORDER BY hits DESC, last_seen DESC"""
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)

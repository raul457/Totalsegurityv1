import os
import json
import logging
from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
RECIPIENT_PHONE = os.getenv("RECIPIENT_PHONE", "5544991561510")
API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v17.0")
DATABASE_URL = os.getenv("DATABASE_URL")

ALLOWED_EXTENSIONS = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf'}

# ─── Banco de Dados ────────────────────────────────────────────────────────────

def get_db_conn():
    if not DATABASE_URL:
        return None
    try:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as e:
        app.logger.error("Erro ao conectar banco: %s", e)
        return None

def init_db():
    conn = get_db_conn()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orcamentos (
                id          SERIAL PRIMARY KEY,
                nome        VARCHAR(255),
                email       VARCHAR(255),
                telefone    VARCHAR(50),
                estado      VARCHAR(100),
                cidade      VARCHAR(255),
                natureza    VARCHAR(100),
                servicos    JSONB,
                whatsapp_enviado BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        app.logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        app.logger.error("Erro ao criar tabela: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass

def save_to_db(data: dict, whatsapp_sent: bool = False) -> bool:
    conn = get_db_conn()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO orcamentos
                (nome, email, telefone, estado, cidade, natureza, servicos, whatsapp_enviado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('nome'),
            data.get('email'),
            data.get('telefone'),
            data.get('estado'),
            data.get('cidade'),
            data.get('natureza'),
            json.dumps(data.get('servicos', []), ensure_ascii=False),
            whatsapp_sent,
        ))
        conn.commit()
        cur.close()
        conn.close()
        app.logger.info("Orçamento salvo no banco de dados")
        return True
    except Exception as e:
        app.logger.error("Erro ao salvar no banco: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False

with app.app_context():
    init_db()

# ─── WhatsApp ──────────────────────────────────────────────────────────────────

def build_whatsapp_payload(form_data: dict) -> dict:
    lines = [
        "📩 *Novo Pedido de Orçamento*",
        "",
        f"*Nome:* {form_data.get('nome', '-')}",
        f"*E-mail:* {form_data.get('email', '-')}",
        f"*Telefone:* {form_data.get('telefone', '-')}",
        f"*Estado:* {form_data.get('estado', '-')}",
        f"*Cidade:* {form_data.get('cidade', '-')}",
        "",
        "*Natureza da operação:*",
        f"{form_data.get('natureza', '-')}",
        "",
        "*Serviços solicitados:*",
    ]
    servicos = form_data.get("servicos", [])
    if isinstance(servicos, list) and servicos:
        for s in servicos:
            lines.append(f"- {s}")
    else:
        lines.append("- Nenhum especificado")
    lines += ["", "Enviado via site — Total Security"]
    return {
        "messaging_product": "whatsapp",
        "to": RECIPIENT_PHONE,
        "type": "text",
        "text": {"body": "\n".join(lines)},
    }

def send_whatsapp(form_data: dict) -> bool:
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        app.logger.warning("WhatsApp não configurado — configure WHATSAPP_TOKEN e WHATSAPP_PHONE_ID")
        return False
    url = f"https://graph.facebook.com/{API_VERSION}/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=build_whatsapp_payload(form_data), timeout=10)
        if resp.status_code in (200, 201):
            app.logger.info("WhatsApp enviado com sucesso")
            return True
        app.logger.error("WhatsApp API: %s — %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        app.logger.exception("Erro ao conectar WhatsApp API: %s", e)
        return False

# ─── Rotas estáticas ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/orcamento')
@app.route('/orcamento.html')
@app.route('/orçamento.html')
def orcamento_page():
    return send_from_directory(BASE_DIR, 'orçamento.html')

@app.route('/<path:filename>')
def static_files(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(BASE_DIR, filename)

# ─── API ───────────────────────────────────────────────────────────────────────

@app.route('/submit-orcamento', methods=['POST'])
def submit_orcamento():
    data = request.get_json(silent=True) or {}
    app.logger.info("Recebido orçamento: %s", data)

    if not data.get('nome') and not data.get('telefone'):
        return jsonify({"ok": False, "error": "Informe pelo menos nome ou telefone."}), 400

    whatsapp_sent = send_whatsapp(data)
    db_saved = save_to_db(data, whatsapp_sent)

    if not whatsapp_sent and not db_saved:
        return jsonify({
            "ok": False,
            "error": "Nenhum canal disponível. Configure WHATSAPP_TOKEN e/ou DATABASE_URL no Vercel.",
        }), 500

    return jsonify({"ok": True, "whatsapp": whatsapp_sent, "banco": db_saved})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

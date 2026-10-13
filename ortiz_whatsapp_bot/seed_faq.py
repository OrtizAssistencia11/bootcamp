from app import init_db, db
from datetime import datetime

FAQS = [
    (
        "Onde fica a Ortiz Assistência Técnica?",
        "Estamos na Rua Lázaro de Barros, 50."
    ),
    (
        "Qual o horário de atendimento?",
        "Atendemos de segunda a domingo, das 8:00 às 23:00."
    ),
    (
        "Qual o WhatsApp da assistência?",
        "Você pode falar com a Ortiz Assistência Técnica pelo WhatsApp da assistência."
    ),
    (
        "Quais aparelhos vocês consertam?",
        "Trabalhamos com manutenção de celulares, tablets, PCs e notebooks."
    ),
    (
        "Vocês fazem troca de tela?",
        "Sim! Trabalhamos com troca de tela/display. Envie o modelo do aparelho para verificarmos a disponibilidade da peça e preparar o orçamento."
    ),
    (
        "Vocês trocam bateria?",
        "Sim! Trabalhamos com troca de bateria. Envie o modelo do aparelho para verificarmos a peça e o orçamento."
    ),
    (
        "Como faço para solicitar um orçamento?",
        "É só enviar o modelo do aparelho e, se possível, explicar o problema. A assistência avalia o serviço e informa o orçamento."
    ),
]

init_db()
conn = db()

for question, answer in FAQS:
    exists = conn.execute(
        "SELECT 1 FROM faq WHERE question=? LIMIT 1", (question,)
    ).fetchone()

    if not exists:
        conn.execute(
            "INSERT INTO faq(question,answer,created_at) VALUES(?,?,?)",
            (question, answer, datetime.now().isoformat())
        )

conn.commit()
conn.close()

print("FAQ inicial cadastrada com sucesso.")

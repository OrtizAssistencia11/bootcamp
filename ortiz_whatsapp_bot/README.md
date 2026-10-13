# Ortiz WhatsApp Bot

Bot em Python para WhatsApp Business com:

- Respostas automáticas.
- FAQ cadastrável.
- IA opcional para perguntas que ainda não estão na FAQ.
- Registro das conversas em SQLite.
- Detecção de perguntas repetidas.
- Alerta ao responsável quando uma pergunta desconhecida aparece 3 vezes.
- Alerta ao responsável quando o cliente pede atendimento humano.
- Endpoints simples para consultar e cadastrar FAQ.

## 1. Instalação

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

Linux/macOS:
```bash
source .venv/bin/activate
```

Depois:

```bash
pip install -r requirements.txt
```

## 2. Configuração

Copie `.env.example` para `.env` e preencha:

- WHATSAPP_VERIFY_TOKEN
- WHATSAPP_ACCESS_TOKEN
- WHATSAPP_PHONE_NUMBER_ID
- OWNER_PHONE
- OPENAI_API_KEY

A chave da OpenAI é opcional. Sem ela, o bot funciona usando apenas a FAQ.

## 3. Rodar

```bash
python app.py
```

O servidor ficará em:

```text
http://localhost:5000
```

Teste:

```text
http://localhost:5000/health
```

## 4. Webhook do WhatsApp

A URL pública do webhook deve ser:

```text
https://SEU-DOMINIO/webhook
```

O token usado na configuração do webhook deve ser exatamente o mesmo valor de:

```text
WHATSAPP_VERIFY_TOKEN
```

Para desenvolvimento local, use um túnel HTTPS, como ngrok ou Cloudflare Tunnel.

## 5. FAQ

Consultar:

```text
GET /faq
```

Cadastrar:

```http
POST /faq
Content-Type: application/json

{
  "question": "Vocês trocam tela de celular?",
  "answer": "Sim! Trabalhamos com troca de telas. Envie o modelo do aparelho para verificarmos a peça e o orçamento."
}
```

## 6. Aprendizado

Consultar:

```text
GET /learning
```

O bot registra perguntas que não encontrou na FAQ.

Quando a mesma pergunta normalizada aparecer 3 vezes, o responsável recebe uma notificação.

A ideia é transformar perguntas reais em novas FAQs depois de revisar a resposta.

## 7. Atendimento humano

Se o cliente escrever algo como:

- "quero falar com atendente"
- "quero falar com uma pessoa"
- "quero falar com o responsável"
- "quero falar com o dono"

o bot avisa o número configurado em `OWNER_PHONE`.

## Importante

O bot não deve guardar senha, cartão, código de autenticação ou outros dados sensíveis.

Para uso real, coloque o servidor atrás de HTTPS e proteja os endpoints administrativos `/faq` e `/learning` com autenticação antes de publicar o sistema.

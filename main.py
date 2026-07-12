import os
import ccxt
import anthropic
from flask import Flask, request, jsonify

app = Flask(__name__)

# Leitura e verificação das variáveis de ambiente
API_KEY = os.getenv('OKX_API_KEY', '')
SECRET_KEY = os.getenv('OKX_SECRET_KEY', '')
PASSPHRASE = os.getenv('OKX_PASSPHRASE', '')
CLAUDE_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# Conexão OKX
okx = ccxt.okx({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSPHRASE,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})

# Conexão Claude
anthropic_client = anthropic.Anthropic(api_key=CLAUDE_KEY) if CLAUDE_KEY else None

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Servidor rodando com sucesso!"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return jsonify({"status": "erro", "mensagem": "Sem dados recebidos"}), 400

    symbol = data.get('symbol')
    direction = data.get('action')
    
    try:
        price = float(data.get('price', 0))
        sl = float(data.get('sl', 0))
        tp = float(data.get('tp', 0))
    except (ValueError, TypeError):
        return jsonify({"status": "erro", "mensagem": "Dados numericos invalidos"}), 400

    print(f"🚨 Webhook Recebido: {symbol} - {direction} | Preço: {price} | SL: {sl} | TP: {tp}")

    if not anthropic_client:
        return jsonify({"status": "erro", "mensagem": "Chave ANTHROPIC_API_KEY nao configurada"}), 500

    # Chamada de validação ao Claude
    prompt = f"""
    Voce e um gerenciador de risco SMC.
    Analise a oportunidade:
    - Ativo: {symbol}
    - Operacao: {direction}
    - Entrada: {price}
    - Stop Loss: {sl}
    - Take Profit: {tp}

    Responda ESTRITAMENTE em formato JSON:
    {{
        "aprovado": true,
        "motivo": "sua justificativa"
    }}
    """

    try:
        resposta = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        
        analise = resposta.content[0].text.strip()
        print(f"🤖 Claude: {analise}")

        if '"aprovado": true' in analise.lower():
            side = 'buy' if str(direction).lower() == 'buy' else 'sell'
            
            # Executa na OKX
            order = okx.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=0.001,
                params={
                    'stopLoss': {'triggerPrice': sl, 'type': 'market'},
                    'takeProfit': {'triggerPrice': tp, 'type': 'market'}
                }
            )
            return jsonify({"status": "sucesso", "ordem_id": order.get('id')}), 200
        else:
            return jsonify({"status": "rejeitado_pelo_claude", "detalhes": analise}), 200

    except Exception as e:
        print(f"❌ Erro no processamento: {str(e)}")
        return jsonify({"status": "erro", "detalhes": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

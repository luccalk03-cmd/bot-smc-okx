import os
import ccxt
import anthropic
from flask import Flask, request, jsonify

app = Flask(__name__)

# Leitura e verificação das variáveis
API_KEY = os.getenv('OKX_API_KEY', '')
SECRET_KEY = os.getenv('OKX_SECRET_KEY', '')
PASSPHRASE = os.getenv('OKX_PASSPHRASE', '')
CLAUDE_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# Teste de inicialização das APIs
print("--- INICIANDO SERVIDOR BOT SMC ---")
print(f"OKX API Key configurada: {'SIM' if API_KEY else 'NAO'}")
print(f"Claude API Key configurada: {'SIM' if CLAUDE_KEY else 'NAO'}")

try:
    okx = ccxt.okx({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'password': PASSPHRASE,
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })
except Exception as e:
    print(f"Erro ao inicializar OKX CCXT: {e}")

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "Servidor do Bot no Ar!"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return jsonify({"status": "erro", "mensagem": "Sem dados"}), 400

    symbol = data.get('symbol')
    direction = data.get('action')
    
    try:
        price = float(data.get('price', 0))
        sl = float(data.get('sl', 0))
        tp = float(data.get('tp', 0))
    except Exception:
        return jsonify({"status": "erro", "mensagem": "Valores incorretos"}), 400

    print(f"🚨 Webhook Recebido: {symbol} | {direction} | Preço: {price}")

    if not CLAUDE_KEY:
        return jsonify({"status": "erro", "mensagem": "ANTHROPIC_API_KEY ausente"}), 500

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_KEY)
        prompt = f"""
        Analise esta entrada SMC:
        Ativo: {symbol}, Operacao: {direction}, Entrada: {price}, SL: {sl}, TP: {tp}
        Responda em JSON: {{"aprovado": true, "motivo": "explicacao"}}
        """
        
        resposta = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        
        analise = resposta.content[0].text.strip()
        print(f"🤖 Claude: {analise}")

        if '"aprovado": true' in analise.lower():
            side = 'buy' if str(direction).lower() == 'buy' else 'sell'
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
            return jsonify({"status": "rejeitado", "detalhes": analise}), 200

    except Exception as e:
        print(f"Erro na execucao: {e}")
        return jsonify({"status": "erro", "detalhes": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

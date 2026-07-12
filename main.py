import os
import ccxt
import anthropic
from flask import Flask, request, jsonify

app = Flask(__name__)

# Conexão com a OKX via CCXT
okx = ccxt.okx({
    'apiKey': os.getenv('OKX_API_KEY'),
    'secret': os.getenv('OKX_SECRET_KEY'),
    'password': os.getenv('OKX_PASSPHRASE'),
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}  # Para Mercado Futuro / Perpétuos
})

# Conexão com o Claude
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return jsonify({"status": "erro", "mensagem": "Sem dados"}), 400

    symbol = data.get('symbol')
    direction = data.get('action')
    price = float(data.get('price'))
    sl = float(data.get('sl'))
    tp = float(data.get('tp'))

    # 1. Pergunta ao Claude se o Trade é seguro
    prompt = f"""
    Você é um gerenciador de risco e analista técnico especialista em Smart Money Concepts (SMC).
    
    Analise a seguinte oportunidade enviada pelo indicador:
    - Ativo: {symbol}
    - Operação: {direction} (buy/sell)
    - Preço de Entrada: {price}
    - Stop Loss (SL): {sl}
    - Take Profit (TP): {tp}
    
    Regras de Validação:
    1. A relação Risco x Retorno (R:R) deve ser de no mínimo 1:1.5.
    2. O Stop Loss deve ser anatomicamente coerente.

    Responda EXATAMENTE no formato JSON com duas chaves:
    {{
        "aprovado": true,
        "motivo": "Sua justificativa aqui"
    }}
    """

    try:
        resposta = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        
        analise_texto = resposta.content[0].text.strip()

        # Check se o Claude Aprovou
        if '"aprovado": true' in analise_texto.lower():
            side = 'buy' if direction.lower() == 'buy' else 'sell'
            amount = 0.001  # Tamanho da ordem/contratos

            # 2. Executa a ordem na OKX com SL e TP
            order = okx.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params={
                    'stopLoss': {'triggerPrice': sl, 'type': 'market'},
                    'takeProfit': {'triggerPrice': tp, 'type': 'market'}
                }
            )
            return jsonify({"status": "sucesso", "ordem_id": order['id']}), 200
        else:
            return jsonify({"status": "rejeitado_pelo_claude", "motivo": analise_texto}), 200

    except Exception as e:
        return jsonify({"status": "erro", "detalhes": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

import os
import ccxt
import json
import anthropic
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configurações de Ambiente
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
    'options': {'defaultType': 'swap'}  # Mercado de Futuros Perpétuos
})

# 🚨 TRAVA DE SEGURANÇA OBRIGATÓRIA: MODO DEMO / SIMULADO (PAPER TRADING)
okx.set_sandbox_mode(True)

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "Servidor do Bot SMC Rodando em MODO DEMO!"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return jsonify({"status": "erro", "mensagem": "Sem dados"}), 400

    symbol = data.get('symbol', 'BTC/USDT:USDT')
    direction = data.get('action')  # 'buy' ou 'sell'
    
    # Busca a cotação atual na OKX se o TradingView não enviar o preço fixo
    try:
        price = float(data.get('price')) if data.get('price') else float(okx.fetch_ticker(symbol)['last'])
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": f"Erro ao obter preco atual: {e}"}), 400

    print(f"\n🚨 SINAL RECEBIDO DO TRADINGVIEW: {direction} em {symbol} | Preço Atual: {price}")

    if not CLAUDE_KEY:
        return jsonify({"status": "erro", "mensagem": "Chave ANTHROPIC_API_KEY ausente no Render"}), 500

    # ------------------------------------------------──
    # O CLAUDE ANALISA O PREÇO E CALCULA O SL E TP
    # ------------------------------------------------──
    prompt = f"""
    Você é um gestor de risco e trader especialista em Smart Money Concepts (SMC).
    Um sinal de entrada foi gerado pelo indicador no TradingView:
    - Ativo: {symbol}
    - Operação: {direction} (buy/sell)
    - Preço de Entrada Atual: {price}

    Sua tarefa de análise de risco SMC:
    1. Calcule um Stop Loss (SL) técnico coerente para esta entrada e um Take Profit (TP).
    2. A relação Risco x Retorno (R:R) DEVE ser de no mínimo 1:2.
    3. Se a estrutura do preço for desfavorável, reprove a operação.

    Responda ESTRITAMENTE em formato JSON com o seguinte padrão:
    {{
        "aprovado": true,
        "sl": valor_do_stop_loss_numerico,
        "tp": valor_do_take_profit_numerico,
        "motivo": "Breve justificativa tecnica do calculo"
    }}
    (Se reprovar, defina "aprovado": false e coloque "sl": 0, "tp": 0).
    """

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_KEY)
        resposta = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        
        texto_resposta = resposta.content[0].text.strip()
        print(f"🤖 RESPOSTA DO CLAUDE:\n{texto_resposta}")

        dados_claude = json.loads(texto_resposta)

        if dados_claude.get("aprovado") == True:
            sl_calculado = float(dados_claude.get("sl"))
            tp_calculado = float(dados_claude.get("tp"))
            side = 'buy' if str(direction).lower() in ['buy', 'buy_signal', 'long'] else 'sell'
            amount = 0.001  # Tamanho do lote simulado para o teste

            # Executa a ordem na OKX DEMO
            order = okx.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params={
                    'stopLoss': {'triggerPrice': sl_calculado, 'type': 'market'},
                    'takeProfit': {'triggerPrice': tp_calculado, 'type': 'market'}
                }
            )
            print(f"✅ ORDEM EXECUTADA NA DEMO! ID: {order.get('id')} | SL: {sl_calculado} | TP: {tp_calculado}")
            return jsonify({
                "status": "sucesso_demo", 
                "ordem_id": order.get('id'), 
                "sl_calculado": sl_calculado,
                "tp_calculado": tp_calculado,
                "motivo": dados_claude.get("motivo")
            }), 200
        else:
            print("🛑 TRADE REPROVADO PELO CLAUDE.")
            return jsonify({"status": "rejeitado_pelo_claude", "motivo": dados_claude.get("motivo")}), 200

    except Exception as e:
        print(f"❌ ERRO NA EXECUÇÃO: {e}")
        return jsonify({"status": "erro", "detalhes": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

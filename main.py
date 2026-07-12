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
    'options': {'defaultType': 'swap'}  # Contratos Futuros Perpétuos
})

# 🚨 TRAVA DE SEGURANÇA: MODO DEMO / SIMULADO (PAPER TRADING)
okx.set_sandbox_mode(True)

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "Servidor Bot SMC ativo em MODO DEMO!"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return jsonify({"status": "erro", "mensagem": "Sem dados no Webhook"}), 400

    symbol = data.get('symbol', 'BTC/USDT:USDT')
    direction = data.get('action', 'buy')  # 'buy' ou 'sell'
    
    # 1. Obter Cotação Atual do Ativo e Saldo da Conta Demo
    try:
        ticker = okx.fetch_ticker(symbol)
        price = float(data.get('price')) if data.get('price') else float(ticker['last'])
        
        balance = okx.fetch_balance()
        usdt_free = float(balance.get('USDT', {}).get('free', 1000.0))  # Saldo USDT disponível na Demo
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": f"Erro ao obter dados do mercado/banca: {e}"}), 400

    print(f"\n🚨 SINAL DO TRADINGVIEW: {direction.upper()} em {symbol} | Preço Atual: {price} | Saldo Demo Livre: ${usdt_free:.2f}")

    if not CLAUDE_KEY:
        return jsonify({"status": "erro", "mensagem": "Chave ANTHROPIC_API_KEY ausente"}), 500

    # 2. PROMPT DE GESTÃO DE RISCO E ESTRUTURA PARA O CLAUDE
    prompt = f"""
    Você é o Gerente Institucional de Risco e Gestão de Banca especialista em Smart Money Concepts (SMC).

    DADOS DA OPORTUNIDADE:
    - Ativo: {symbol}
    - Direção: {direction.upper()}
    - Preço Atual de Entrada: {price}
    - Saldo Livre na Conta (USDT): {usdt_free}

    SUAS REGRAS OPERACIONAIS E TÉCNICAS:
    1. Análise Estrutural: Calcule um Stop Loss (SL) técnico baseado na estrutura de mercado SMC (Order Blocks, FVG, Highs/Lows recentes) para o preço atual.
    2. Relação Risco x Retorno (R:R): O Take Profit (TP) DEVE ser posicionado para oferecer uma relação R:R de no mínimo 1:2 (mínimo 2x a distância do SL).
    3. Tamanho de Lote (Gestão de Banca): Defina a quantidade do lote/contratos ('amount') garantindo que, se o SL for atingido, o prejuízo Máximo seja de no máximo 1% do saldo disponível em USDT.
    4. Veredito Final: Se a volatilidade estiver insana ou o risco desproporcional, REPROVE a operação.

    Responda EXCLUSIVAMENTE em formato JSON com esta estrutura (sem formatação markdown adicional):
    {{
        "aprovado": true,
        "sl": valor_do_stop_loss,
        "tp": valor_do_take_profit,
        "amount": quantidade_do_lote_em_contratos,
        "risco_usd": valor_em_dolares_em_risco,
        "rr_ratio": "1:2",
        "motivo": "Explicação sucinta do veredito técnico"
    }}
    (Se reprovar, coloque "aprovado": false, "sl": 0, "tp": 0, "amount": 0, "risco_usd": 0, "rr_ratio": "N/A", "motivo": "Justificativa da rejeição").
    """

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_KEY)
        resposta = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}]
        )
        
        texto_resposta = resposta.content[0].text.strip()
        print(f"\n🤖 VEREDITO E CÁLCULO DO CLAUDE:\n{texto_resposta}\n")

        # Limpeza para garantir parsing JSON perfeito
        if texto_resposta.startswith("```json"):
            texto_resposta = texto_resposta.replace("```json", "").replace("```", "").strip()

        dados_claude = json.loads(texto_resposta)

        if dados_claude.get("aprovado") == True:
            sl_calculado = float(dados_claude.get("sl"))
            tp_calculado = float(dados_claude.get("tp"))
            amount_calculado = float(dados_claude.get("amount", 0.001))
            side = 'buy' if str(direction).lower() in ['buy', 'buy_signal', 'long'] else 'sell'

            # 3. Execução da Ordem na OKX DEMO
            order = okx.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount_calculado,
                params={
                    'stopLoss': {'triggerPrice': sl_calculado, 'type': 'market'},
                    'takeProfit': {'triggerPrice': tp_calculado, 'type': 'market'}
                }
            )

            print(f"✅ ORDEM EXECUTADA NA DEMO! ID: {order.get('id')} | Lote: {amount_calculado} | SL: {sl_calculado} | TP: {tp_calculado}")
            return jsonify({
                "status": "sucesso_demo",
                "ordem_id": order.get('id'),
                "detalhes": dados_claude
            }), 200
        else:
            print(f"🛑 TRADE REPROVADO PELO CLAUDE. Motivo: {dados_claude.get('motivo')}")
            return jsonify({"status": "rejeitado_pelo_claude", "detalhes": dados_claude}), 200

    except Exception as e:
        print(f"❌ ERRO NO PROCESSAMENTO / EXECUÇÃO: {e}")
        return jsonify({"status": "erro", "detalhes": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

import http.server
import socketserver
import threading
import asyncio
import websockets
import json
import time
import os

liq_log = []
symbol = "BTCUSDT"

def generate_html():
    is_weekend = time.localtime().tm_wday in [5, 6]
    threshold = 30000 if is_weekend else 100000
    log_items = "".join(liq_log)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Tier-1 Liquidity Radar</title>
        <style>
            body {{ font-family: sans-serif; background: #0e1117; color: white; padding: 15px; margin: 0; }}
            .container {{ display: flex; flex-direction: column; gap: 15px; margin-top: 15px; }}
            .col {{ background: #161b22; padding: 15px; border-radius: 8px; border: 1px solid #30363d; }}
            h2 {{ margin-top: 0; color: #f0f6fc; font-size: 1.1em; }}
            .btn {{ padding: 10px 20px; background: #21262d; border: 1px solid #30363d; color: white; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; font-weight: bold; }}
            .active {{ background: #238636; border-color: #2ea44f; }}
            .badge {{ background: #8b949e22; padding: 5px 10px; border-radius: 20px; font-size: 0.85em; color: #c9d1d9; }}
        </style>
        <script>
            function playSiren() {{
                var audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                var osc = audioCtx.createOscillator();
                var gain = audioCtx.createGain();
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(900, audioCtx.currentTime);
                osc.frequency.linearRampToValueAtTime(1400, audioCtx.currentTime + 0.3);
                osc.frequency.linearRampToValueAtTime(900, audioCtx.currentTime + 0.6);
                gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(); osc.stop(audioCtx.currentTime + 0.6);
            }}
            setTimeout(function() {{ location.reload(); }}, 2000);
        </script>
    </head>
    <body>
        <h2 style="color: #58a6ff; margin-bottom: 10px;">🐋 TIER-1 LIVE LIQUIDATION FEED</h2>
        <div style="margin-bottom: 15px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <a href="/set_btc" class="btn {'active' if symbol=='BTCUSDT' else ''}">₿ BTC</a>
            <a href="/set_eth" class="btn {'active' if symbol=='ETHUSDT' else ''}">⟠ ETH</a>
            <span class="badge">{ '⚡️ ВЫХОДНОЙ РЕЖИМ' if is_weekend else '💼 БУДНИ' }</span>
            <span class="badge">Фильтр: ${threshold:,}</span>
        </div>
        <div class="container">
            <div class="col">
                <h2>🔥 ПОТОК ПРИНУДИТЕЛЬНЫХ ЛИКВИДАЦИЙ ТОЛПЫ ({symbol.replace("USDT","")})</h2>
                {log_items if log_items else '<p style="color:#8b949e; font-style: italic;">Подключение к шлюзу Bybit... Ожидание крупных ликвидаций.</p>'}
            </div>
        </div>
    </body>
    </html>
    """

class RadarWebServer(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args): return
    def do_GET(self):
        global symbol, liq_log
        if self.path == '/set_btc':
            symbol = "BTCUSDT"
            liq_log = []
            self.send_response(303); self.send_header('Location', '/'); self.end_headers()
        elif self.path == '/set_eth':
            symbol = "ETHUSDT"
            liq_log = []
            self.send_response(303); self.send_header('Location', '/'); self.end_headers()
        elif self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(generate_html().encode('utf-8'))

async def run_bybit_ws():
    global liq_log
    url = "wss://://bybit.com"
    while True:
        try:
            async with websockets.connect(url) as ws:
                sub_msg = {"op": "subscribe", "args": [f"liquidation.{symbol}"]}
                await ws.send(json.dumps(sub_msg))
                while True:
                    res = await ws.recv()
                    d = json.loads(res)
                    if "data" in d:
                        ld = d["data"]
                        price = float(ld.get("price"))
                        usd_val = float(ld.get("size")) * price
                        is_w = time.localtime().tm_wday in [5, 6]
                        th = 30000 if is_w else 100000
                        if usd_val >= th:
                            t_str = time.strftime('%H:%M:%S', time.localtime())
                            is_l = ld.get("side") == "Buy"
                            txt = "🔴 ЛИКВИДАЦИЯ ЛОНГА (Рвет вниз)" if is_l else "🟢 ЛИКВИДАЦИЯ ШОРТА (Рвет вверх)"
                            c = "#ff4b4b" if is_l else "#00e676"
                            item = f"<div style='padding:12px; margin-bottom:8px; background:#1c2128; border-radius:6px; border-left:5px solid {c}; font-size:0.9em; color:white;'>" \
                                   f"<b>[{t_str}]</b> <span style='color:{c}; font-weight:bold;'>{txt}</span> | " \
                                   f"Объем: <span style='color:yellow; font-weight:bold;'>${usd_val:,.2f}</span> | Цена: <b>{price}</b>" \
                                   f"<script>playSiren();</script></div>"
                            liq_log.insert(0, item)
                            if len(liq_log) > 25: liq_log.pop()
        except:
            await asyncio.sleep(1)

threading.Thread(target=lambda: asyncio.run(run_bybit_ws()), daemon=True).start()

PORT = int(os.environ.get("PORT", 8080))
with socketserver.TCPServer(("", PORT), RadarWebServer) as httpd:
    httpd.serve_forever()

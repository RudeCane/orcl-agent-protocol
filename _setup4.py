# Update trading.html to use Binance WebSocket for instant order books
import re

with open("trading.html", "r", encoding="utf-8") as f:
    content = f.read()

# Add Binance WebSocket orderbook code
ws_code = """
// -- BINANCE WEBSOCKET ORDER BOOK (instant, free, no API key) --
let obSocket = null;

function connectOrderBookWS() {
    const pair = currentPair.replace('-', '').toLowerCase();
    if (obSocket) obSocket.close();

    obSocket = new WebSocket(`wss://stream.binance.com:9443/ws/${pair}@depth20@100ms`);

    obSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.bids && data.asks) {
            renderOrderBookFromChart({
                bids: data.bids.map(b => [parseFloat(b[0]), parseFloat(b[1])]),
                asks: data.asks.map(a => [parseFloat(a[0]), parseFloat(a[1])]),
                mid_price: (parseFloat(data.bids[0][0]) + parseFloat(data.asks[0][0])) / 2
            });

            const bestBid = parseFloat(data.bids[0][0]);
            const bestAsk = parseFloat(data.asks[0][0]);
            const spread = bestAsk - bestBid;
            const spreadPct = (spread / bestAsk) * 100;
            document.getElementById('spreadVal').textContent = spreadPct.toFixed(4) + '%';

            const bidVol = data.bids.reduce((s, b) => s + parseFloat(b[0]) * parseFloat(b[1]), 0);
            const askVol = data.asks.reduce((s, a) => s + parseFloat(a[0]) * parseFloat(a[1]), 0);
            const imb = (bidVol - askVol) / (bidVol + askVol);
            document.getElementById('imbalanceVal').textContent = imb.toFixed(4);

            // Quick signals
            const el = document.getElementById('signalsList');
            let items = [];
            if (Math.abs(imb) > 0.1) {
                const bull = imb > 0;
                items.push('<div class="signal-item"><div class="signal-dot ' + (bull?'bullish':'bearish') + '"></div><span class="signal-text">Book ' + (bull?'bid':'ask') + ' heavy</span><span class="signal-val">' + (imb*100).toFixed(1) + '%</span></div>');
            }
            if (spreadPct > 0.05) {
                items.push('<div class="signal-item"><div class="signal-dot neutral"></div><span class="signal-text">Spread</span><span class="signal-val">' + spreadPct.toFixed(4) + '%</span></div>');
            }
            items.push('<div class="signal-item"><div class="signal-dot bullish"></div><span class="signal-text">Bid depth</span><span class="signal-val">$' + bidVol.toLocaleString(undefined,{maximumFractionDigits:0}) + '</span></div>');
            items.push('<div class="signal-item"><div class="signal-dot bearish"></div><span class="signal-text">Ask depth</span><span class="signal-val">$' + askVol.toLocaleString(undefined,{maximumFractionDigits:0}) + '</span></div>');
            el.innerHTML = items.join('');
        }
    };

    obSocket.onclose = () => { setTimeout(connectOrderBookWS, 2000); };
    obSocket.onerror = () => { obSocket.close(); };
}

// Override setPair to reconnect WS
const _origSetPair = setPair;
setPair = function(pair) {
    _origSetPair(pair);
    connectOrderBookWS();
};
"""

# Insert before the closing </script>
content = content.replace("// Auto refresh\nsetInterval", ws_code + "\nconnectOrderBookWS();\n\n// Auto refresh\nsetInterval")

# Also try alternate format
content = content.replace("// Auto refresh\r\nsetInterval", ws_code + "\nconnectOrderBookWS();\n\n// Auto refresh\nsetInterval")

# Fallback: insert before last </script>
if "connectOrderBookWS" not in content:
    content = content.replace("setInterval(() => { loadCandles(); loadOrderBook(); }, 30000);", ws_code + "\nconnectOrderBookWS();\n\nsetInterval(() => { loadCandles(); }, 30000);")

# If still not added, try original interval
if "connectOrderBookWS" not in content:
    content = content.replace("setInterval(() => { loadCandles(); loadOrderBook(); }, 15000);", ws_code + "\nconnectOrderBookWS();\n\nsetInterval(() => { loadCandles(); }, 30000);")

with open("trading.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Updated trading.html with Binance WebSocket - order book is now real-time!")

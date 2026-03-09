"""
Patch dashboard.html and trading.html with full exchange support:
- Binance, Binance.US, BloFin in chain dropdown
- Default tokens per exchange
- Exchange status display
- Trading page exchange selector
"""
import os

def patch_dashboard():
    path = "dashboard.html"
    if not os.path.exists(path):
        print(f"ERROR: {path} not found")
        return False

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update chain dropdown to include all exchanges
    old_select = """<option value="base">Base</option>
                <option value="ethereum">Ethereum</option>
                <option value="bnb">BNB Chain</option>
                <option value="blofin">BloFin CEX</option>"""

    new_select = """<option value="base">Base</option>
                <option value="ethereum">Ethereum</option>
                <option value="bnb">BNB Chain</option>
                <option value="binance">Binance</option>
                <option value="binance_us">Binance.US</option>
                <option value="blofin">BloFin CEX</option>"""

    if "binance" not in content or "Binance</option>" not in content:
        content = content.replace(old_select, new_select)
        # Try without extra spaces too
        content = content.replace(
            '<option value="blofin">BloFin CEX</option>',
            '<option value="blofin">BloFin CEX</option>' if '<option value="binance">' in content else
            '<option value="binance">Binance</option>\n                <option value="binance_us">Binance.US</option>\n                <option value="blofin">BloFin CEX</option>'
        )

    # 2. Update default tokens in send() function
    old_tokens = "blofin:['BTC-USDT','ETH-USDT']"
    new_tokens = "blofin:['BTC-USDT','ETH-USDT'],binance:['BTCUSDT','ETHUSDT'],binance_us:['BTCUSDT','ETHUSDT']"
    if "binance:['BTCUSDT'" not in content:
        content = content.replace(old_tokens, new_tokens)

    # 3. Update submitTask tokens
    old_task = "blofin:['BTC-USDT']"
    new_task = "blofin:['BTC-USDT'],binance:['BTCUSDT'],binance_us:['BTCUSDT']"
    if new_task not in content:
        content = content.replace(old_task, new_task)

    # 4. Add exchange status section after chains
    # Find the chains panel and add exchange status after it
    old_chains_panel = """<div class="chains-row" id="chainsRow"><div class="empty">Loading chains...</div></div>
        </div>"""

    new_chains_panel = """<div class="chains-row" id="chainsRow"><div class="empty">Loading chains...</div></div>
            <div style="margin-top:16px">
                <div class="panel-title" style="margin-bottom:12px">Exchanges</div>
                <div class="chains-row" id="exchangeRow"><div class="empty">Loading exchanges...</div></div>
            </div>
        </div>"""

    if "exchangeRow" not in content:
        content = content.replace(old_chains_panel, new_chains_panel)

    # 5. Add exchange refresh function
    old_refresh = "await Promise.all([rStatus(),rAgents(),rTrades(),rWallet(),rMemory(),rChains(),rPos()])"
    new_refresh = "await Promise.all([rStatus(),rAgents(),rTrades(),rWallet(),rMemory(),rChains(),rPos(),rExchanges()])"
    if "rExchanges" not in content:
        content = content.replace(old_refresh, new_refresh)

    # 6. Add rExchanges function before the log function
    exchange_fn = """
// -- EXCHANGES --
async function rExchanges(){
    const el=document.getElementById('exchangeRow');
    if(!el)return;
    const exchanges=[];

    // Binance
    const bnTicker=await api('/binance/ticker/BTCUSDT');
    if(bnTicker&&!bnTicker.error){
        exchanges.push({name:'Binance',connected:true,price:'$'+Number(bnTicker.last).toLocaleString(undefined,{maximumFractionDigits:2}),vol:'$'+(bnTicker.quote_volume_24h/1e9).toFixed(1)+'B',pairs:'500+'});
    } else {
        exchanges.push({name:'Binance',connected:false,price:'-',vol:'-',pairs:'500+'});
    }

    // Binance.US
    const busTicker=await api('/binance/ticker/BTCUSDT?us=true');
    if(busTicker&&!busTicker.error){
        exchanges.push({name:'Binance.US',connected:true,price:'$'+Number(busTicker.last).toLocaleString(undefined,{maximumFractionDigits:2}),vol:'$'+(busTicker.quote_volume_24h/1e6).toFixed(0)+'M',pairs:'150+'});
    } else {
        exchanges.push({name:'Binance.US',connected:false,price:'-',vol:'-',pairs:'150+'});
    }

    // BloFin
    const bfTicker=await api('/blofin/ticker/BTC-USDT');
    if(bfTicker&&!bfTicker.error){
        exchanges.push({name:'BloFin',connected:true,price:'$'+Number(bfTicker.last).toLocaleString(undefined,{maximumFractionDigits:2}),vol:'-',pairs:'200+'});
    } else {
        exchanges.push({name:'BloFin',connected:false,price:'-',vol:'-',pairs:'200+'});
    }

    if(!exchanges.length){el.innerHTML='<div class="empty">No exchange data</div>';return}
    el.innerHTML=exchanges.map(ex=>{
        const on=ex.connected;
        return '<div class="chain-card"><div class="chain-head"><span class="chain-name">'+ex.name+'</span><div class="chain-dot '+(on?'on':'off')+'"></div></div><div class="chain-detail">BTC: '+ex.price+'<br>24h Vol: '+ex.vol+'<br>Pairs: '+ex.pairs+'</div></div>';
    }).join('');
}

"""

    if "rExchanges" not in content:
        # Insert before the log function
        content = content.replace("function log(msg,type='i')", exchange_fn + "function log(msg,type='i')")

    # 7. Add binance agent tag colors if not present
    if "tag-binance" not in content:
        old_tag_blofin = ".tag-blofin { background: var(--purple-dim); color: var(--purple); border: 1px solid #a78bfa25; }"
        new_tags = """.tag-blofin { background: var(--purple-dim); color: var(--purple); border: 1px solid #a78bfa25; }
        .tag-binance { background: #f0b90b10; color: #f0b90b; border: 1px solid #f0b90b25; }
        .tag-binance_us { background: #f0b90b10; color: #f0b90b; border: 1px solid #f0b90b25; }"""
        content = content.replace(old_tag_blofin, new_tags)

    # 8. Update agent tag detection to include binance
    old_tag_detect = "type.includes('blofin')?'tag-blofin':type.includes('leverage')?'tag-leverage':'tag-market'"
    new_tag_detect = "type.includes('blofin')?'tag-blofin':type.includes('binance')?'tag-binance':type.includes('leverage')?'tag-leverage':'tag-market'"
    content = content.replace(old_tag_detect, new_tag_detect)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Patched {path}")
    return True


def patch_trading():
    path = "trading.html"
    if not os.path.exists(path):
        print(f"ERROR: {path} not found")
        return False

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add exchange selector next to pair selector
    old_pairs = """<button class="pair-btn" onclick="setPair('DOGE-USDT')">DOGE</button>"""

    new_pairs = """<button class="pair-btn" onclick="setPair('DOGE-USDT')">DOGE</button>
        <span style="color:var(--border-2)">|</span>
        <select id="exchangeSel" onchange="setExchange(this.value)" style="background:var(--bg-3);border:1px solid var(--border-0);color:var(--text-1);font-family:'IBM Plex Mono',monospace;font-size:10px;padding:5px 10px;border-radius:4px;cursor:pointer;outline:none">
            <option value="binance">Binance</option>
            <option value="binance_us">Binance.US</option>
            <option value="blofin">BloFin</option>
        </select>"""

    if "exchangeSel" not in content:
        content = content.replace(old_pairs, new_pairs)

    # 2. Add exchange-aware candle loading
    exchange_js = """
// -- EXCHANGE SUPPORT --
let currentExchange = 'binance';

function setExchange(ex) {
    currentExchange = ex;
    loadCandles();
    // Reconnect orderbook WS if binance
    if (typeof connectOrderBookWS === 'function') {
        if (ex === 'binance' || ex === 'binance_us') {
            connectOrderBookWS();
        }
    }
}

// Override loadCandles to use selected exchange
const _origLoadCandles = loadCandles;
loadCandles = async function() {
    try {
        let url;
        const pair = currentPair;
        if (currentExchange === 'binance' || currentExchange === 'binance_us') {
            const symbol = pair.replace('-', '');
            const us = currentExchange === 'binance_us' ? '&us=true' : '';
            url = `${API}/binance/candles/${symbol}?interval=${currentTF}&limit=200${us}`;
        } else {
            url = `${API}/candles/${pair}?bar=${currentTF}&limit=200`;
        }
        const resp = await fetch(url);
        const data = await resp.json();

        if (Array.isArray(data) && data.length > 0) {
            candleSeries.setData(data.map(c => ({
                time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
            })));
            volumeSeries.setData(data.map(c => ({
                time: c.time, value: c.volume,
                color: c.close >= c.open ? '#34d39930' : '#f8717130',
            })));
            const last = data[data.length - 1];
            const first = data[0];
            updatePriceBar(last, first, data);
        }
    } catch (e) {
        console.error('Candle fetch error:', e);
    }
};

"""

    if "currentExchange" not in content:
        # Insert before the init section
        content = content.replace("// -- INIT --\ninitChart();", exchange_js + "// -- INIT --\ninitChart();")
        # Try alternate
        if "currentExchange" not in content:
            content = content.replace("initChart();\nloadCandles();", exchange_js + "initChart();\nloadCandles();")
        # Another alternate
        if "currentExchange" not in content:
            content = content.replace("initChart();", exchange_js + "initChart();")

    # 3. Update WS connection to respect exchange selection
    if "connectOrderBookWS" in content and "currentExchange" in content:
        old_ws = "const pair = currentPair.replace('-', '').toLowerCase();"
        new_ws = """const pair = currentPair.replace('-', '').toLowerCase();
    const wsBase = currentExchange === 'binance_us' ? 'wss://stream.binance.us:9443/ws' : 'wss://stream.binance.com:9443/ws';"""
        if "wsBase" not in content:
            content = content.replace(old_ws, new_ws)

        old_ws_url = "obSocket = new WebSocket(`wss://stream.binance.com:9443/ws/${pair}@depth20@100ms`);"
        new_ws_url = "obSocket = new WebSocket(`${wsBase}/${pair}@depth20@100ms`);"
        content = content.replace(old_ws_url, new_ws_url)

    # 4. Add exchange label to price bar
    old_price_pair = '<span class="price-pair" id="pricePair">BTC-USDT</span>'
    new_price_pair = '<span class="price-pair" id="pricePair">BTC-USDT</span><span id="exchangeLabel" style="font-size:10px;color:var(--text-3);margin-left:8px;padding:3px 8px;background:var(--bg-3);border-radius:4px">Binance</span>'
    if "exchangeLabel" not in content:
        content = content.replace(old_price_pair, new_price_pair)

    # 5. Update exchange label when switching
    update_label = """
    if(document.getElementById('exchangeLabel')){
        const names={binance:'Binance',binance_us:'Binance.US',blofin:'BloFin'};
        document.getElementById('exchangeLabel').textContent=names[currentExchange]||currentExchange;
    }
"""
    if "exchangeLabel" in content and "names[currentExchange]" not in content:
        content = content.replace("function setExchange(ex) {\n    currentExchange = ex;", "function setExchange(ex) {\n    currentExchange = ex;" + update_label)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Patched {path}")
    return True


if __name__ == "__main__":
    print("Updating frontend for all exchanges...\n")
    d = patch_dashboard()
    t = patch_trading()
    if d and t:
        print("\nDone! Dashboard and trading page updated.")
        print("\nDashboard now includes:")
        print("  - Binance + Binance.US + BloFin in chain dropdown")
        print("  - Exchange status cards showing BTC price + volume")
        print("  - Binance agent tag colors (gold)")
        print("\nTrading page now includes:")
        print("  - Exchange selector (Binance / Binance.US / BloFin)")
        print("  - Candles load from selected exchange")
        print("  - Order book WS switches between Binance / Binance.US")
        print("  - Exchange label on price bar")

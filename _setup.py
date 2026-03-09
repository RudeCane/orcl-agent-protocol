import os
os.makedirs("orderbook", exist_ok=True)
with open("orderbook/__init__.py", "w") as f:
    f.write("from orderbook.fetcher import OrderBookFetcher, OrderBook, orderbook_fetcher\n")
print("Created __init__.py")

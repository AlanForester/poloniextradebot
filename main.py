from bittrex.bittrex import Bittrex, API_V1_1, API_V2_0
import time
import asyncio
import uvloop
import datetime
API_KEY = "88e548ba9f424c5bbd6706555aa69109"
API_SECRET = "b1c0bf1aa947490c8a5a1c9a20ae2188"

TIME_LAST_TRADE = 10


class App:
    def __init__(self, api_key=None, api_sec=None):
        self.orders = {}
        self.min_trades = {}
        self.api = Bittrex(api_key, api_sec, api_version=API_V1_1)
        self.invest = 0
        self.balance = 0.
        self.trades = {'act': 0, 'buy': 0, 'sell': 0, 'lose': 0}
        self.last_tick = time.time()

    async def run(self, input_market=None):
        trade_history = await self.api.get_market_history('BTC-DOGE')
        vol_sell = 0.
        vol_buy = 0.
        vol_all = 0.
        buy_delta = 0
        if trade_history['success'] and trade_history['result']:
            print(trade_history['result'][0]['Quantity'])
            for th in trade_history['result']:
                try:
                    ts = int(datetime.datetime.strptime(th['TimeStamp'], '%Y-%m-%dT%H:%M:%S.%f').timestamp()) + 10800
                except ValueError:
                    ts = int(datetime.datetime.strptime(th['TimeStamp'], '%Y-%m-%dT%H:%M:%S').timestamp()) + 10800
                now = int(time.time())
                if ts > now - (TIME_LAST_TRADE * 60):
                    if th['OrderType'] == 'BUY':
                        vol_buy += float(th['Quantity'])
                    if th['OrderType'] == 'SELL':
                        vol_sell += float(th['Quantity'])
                    vol_all += float(th['Total'])
            if vol_sell != 0.:
                buy_delta = (vol_buy * 100. / vol_sell) - 100
            else:
                if vol_all == 0.:
                    buy_delta = 0
                else:
                    buy_delta = 100
        print(vol_buy, vol_sell, buy_delta)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    app = App(api_key=API_KEY, api_sec=API_SECRET)
    loop.run_until_complete(app.run())

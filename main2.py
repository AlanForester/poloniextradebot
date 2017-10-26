from bittrex.bittrex import Bittrex, API_V2_0, API_V1_1
import time
import asyncio
from threading import Thread
from datetime import datetime, timedelta

__author__ = 'alex@collin.su'

API_KEY = "4e7cf9c842534da8ab72a2978aeb77ef"
API_SECRET = "9e4adc5ccb0546b7adcccd93e4c058ba"
FEE = 0.5
PROFIT = 0.5
STOP = 2.
BID = 0.00001
MIN_BUY_MORE_VOL = 30
TIME_VOL_SEC = 60


class App:
    def __init__(self, api_key=None, api_sec=None):
        super().__init__()
        self.orders = {}
        self.api = Bittrex(api_key, api_sec, api_version=API_V1_1)
        self.urls = []

    async def ticker(self, market):
        tick = await self.api.get_ticker(market)
        print(tick)
        if tick['success'] and tick['result'] and tick['result']['Last']:
            currency = market
            check_btc = currency.split('-')
            if check_btc[0] == 'BTC':
                last = float(tick['result']['Last'])
                if not self.orders.get(currency) or not self.orders[currency]['trading']:
                    if not self.orders.get(currency):
                        self.orders[currency] = {}
                        self.orders[currency]['profit'] = 0.

                    # Анализатор объема торгов
                    # trade_history = self.public.returnTradeHistory(currency_pair=currency,
                    #                                                start=time.time() - TIME_VOL_SEC,
                    #                                                end=time.time())
                    # vol_sell = 0.
                    # vol_buy = 0.
                    # vol_all = 0.
                    # for th in trade_history:
                    #     if th['type'] == 'buy':
                    #         vol_buy += float(th['amount'])
                    #     if th['type'] == 'sell':
                    #         vol_sell -= float(th['amount'])
                    #     vol_all += float(th['amount'])
                    # if vol_sell > 0.:
                    #     buy_delta = (vol_buy * 100. / vol_sell) - 100.
                    # else:
                    #     buy_delta = 100
                    # if int(buy_delta) >= TIME_VOL_SEC:
                    self.orders[currency]['time'] = time.time()
                    self.orders[currency]['price'] = last
                    self.orders[currency]['trading'] = True
                    self.orders[currency]['volume'] = float(BID) / last
                    self.orders[currency]['profit'] = 0
                else:
                    comission = (self.orders[currency]['price'] / 100.0) * (FEE + PROFIT)
                    price_with_fee = float(comission) + float(self.orders[currency]['price'])
                    delta = int((last - price_with_fee) * 100000000. * self.orders[currency]['volume'])

                    stop_comission = (self.orders[currency]['price'] / 100.0) * (STOP - FEE)
                    price_stop = float(self.orders[currency]['price']) - float(stop_comission)

                    # Инициализируем массив торгов если не было
                    if not self.orders[currency].get('trades'):
                        self.orders[currency]['trades'] = []
                    trades = self.orders[currency]['trades']

                    if price_with_fee < last and delta >= 1:
                        trade = dict()
                        trade['profit'] = delta
                        trade['time'] = time.time()
                        trades.append(trade)
                        self.orders[currency]['trading'] = False
                    elif price_stop >= last:
                        # Обработчик на закрытие по убытку
                        trade = dict()
                        trade['profit'] = delta
                        trade['time'] = time.time()
                        trades.append(trade)
                        self.orders[currency]['trading'] = False
                    self.orders[currency]['profit'] = delta - FEE
                self.orders[currency]['last'] = last
                # if self.orders[currency].get('trades') and len(self.orders[currency]['trades']) > 0:
                #     self.logger.info(self.orders[currency])

    def log(self):
        while True:
            fail = 0
            success = 0
            trading = 0
            win = 0
            loose = 0

            for order in self.orders.keys():
                if self.orders[order]['profit'] > 0.:
                    success += int(self.orders[order]['profit'])
                elif self.orders[order]['profit'] < 0.:
                    fail -= int(self.orders[order]['profit'])
                if self.orders[order].get('trading'):
                    trading += 1

                if self.orders[order].get('trades') and len(self.orders[order]['trades']) > 0:
                    for t in self.orders[order]['trades']:
                        if t['profit'] > 0:
                            win += t['profit']
                        if t['profit'] < 0:
                            loose -= t['profit']
            print(success, fail, trading, win, loose)
            time.sleep(1)

    async def run(self,loop):
        # t = Thread(target=self.log)
        # t.start()
        tm = {}
        while True:
            print(1)
            markets = await self.api.get_markets()
            print(markets)
            if markets['success']:
                coros = []
                for market in markets['result']:
                    task = asyncio.ensure_future(self.ticker(market['MarketName']))
                    coros.append(task)
                await asyncio.gather(*coros)
            asyncio.sleep(1)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    app = App(api_key=API_KEY, api_sec=API_SECRET)
    loop.run_until_complete(app.run(loop))

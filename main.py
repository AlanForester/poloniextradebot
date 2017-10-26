from poloniex.app import AsyncApp
import time
import asyncio
from threading import Thread
from datetime import datetime, timedelta

__author__ = 'alex@collin.su'

API_KEY = "CNVUTAVQ-YGE5S5HN-0FA8BA7U-QQC2MRAP"
API_SECRET = "abec87d8ba68ed29893927e770879e8291003f5cfc3cf9cf3ae6bdcfd2c293f8f2f43c84b5d966d668c742165df71fc8207e7a0eed1e8052e83b5195b4775792"
FEE = 0.5
PROFIT = 0.5
STOP = 2.
BID = 0.00001
MIN_BUY_MORE_VOL = 30
TIME_VOL_SEC = 60


class App(AsyncApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orders = {}

    def wrapped_trade_his(self, currency):
        async def get_trades():
            return await self.public.returnTradeHistory(currency,
                                                        datetime.now() - timedelta(seconds=TIME_VOL_SEC),
                                                        datetime.now())

        return asyncio.wait(get_trades())

    def ticker(self, **kwargs):
        tick = kwargs
        if type(tick) is dict and tick.get('last'):
            currency = kwargs['currency_pair']
            check_btc = currency.split('_')
            if check_btc[0] == 'BTC':
                last = float(tick['last'])
                if not self.orders.get(currency) or not self.orders[currency]['trading']:
                    if not self.orders.get(currency):
                        self.orders[currency] = {}
                        self.orders[currency]['profit'] = 0.

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

    def trades(self, **kwargs):
        self.logger.info(kwargs)

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

    async def main(self):
        # self.push.subscribe(topic="BTC_ETH", handler=self.trades)
        self.push.subscribe(topic="ticker", handler=self.ticker)

        # volume = await self.public.return24hVolume()
        # currencies = await self.public.returnCurrencies()
        # if currencies.get('BTC'):
        #     self.logger.info(currencies.get('BTC'))
        # while True:
        #     ticker = await self.public.returnTicker()
        #     self.ticker(**ticker)
        #     time.sleep(1)
        # Анализатор объема торгов
        # trade_history = self.public.returnTradeHistory(currency,
        #                                                datetime.now() - timedelta(seconds=TIME_VOL_SEC),
        #                                                datetime.now()).__await__()
        # vol_sell = 0.
        # vol_buy = 0.
        # vol_all = 0.
        # print(trade_history)
        # for th in trade_history:
        #     if th['type'] == 'buy':
        #         vol_buy += th['amount']
        #     if th['type'] == 'sell':
        #         vol_sell -= th['amount']
        #     vol_all += th['amount']
        # buy_delta = (vol_buy * 100. / vol_sell) - 100.
        # if int(buy_delta) >= TIME_VOL_SEC:
        t = Thread(target=self.log)
        t.start()


if __name__ == "__main__":
    app = App(api_key=API_KEY, api_sec=API_SECRET)
    app.run()

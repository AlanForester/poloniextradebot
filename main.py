from poloniex.app import AsyncApp
import time
from threading import Thread

__author__ = 'alex@collin.su'

API_KEY = "CNVUTAVQ-YGE5S5HN-0FA8BA7U-QQC2MRAP"
API_SECRET = "abec87d8ba68ed29893927e770879e8291003f5cfc3cf9cf3ae6bdcfd2c293f8f2f43c84b5d966d668c742165df71fc8207e7a0eed1e8052e83b5195b4775792"
FEE = 0.55
STOP = 2.


class App(AsyncApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orders = {}

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
                    self.orders[currency]['profit'] = 0
                else:
                    comission = (self.orders[currency]['price'] / 100.0) * FEE
                    price_with_fee = float(comission) + float(self.orders[currency]['price'])
                    delta = int((last - price_with_fee) * 100000000.)

                    stop_comission = (self.orders[currency]['price'] / 100.0) * STOP
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
                    self.orders[currency]['profit'] = delta
                self.orders[currency]['last'] = last

            # if self.orders[currency].get('trades') and len(self.orders[currency]['trades']) > 0:
            #     self.logger.info(self.orders[currency])

    def trades(self, **kwargs):
        self.logger.info(kwargs)

    def log(self):
        while True:
            fail = 0
            success = 0
            good = 0
            trading = 0
            win = 0
            loose = 0

            for order in self.orders.keys():
                if self.orders[order]['profit'] > 0.:
                    success += int(self.orders[order]['profit'])
                elif self.orders[order]['profit'] < 0.:
                    fail -= int(self.orders[order]['profit'])
                if self.orders[order].get('last'):
                    good += 1
                if self.orders[order]['trading']:
                    trading += 1

                if self.orders[order].get('trades') and len(self.orders[order]['trades']) > 0:
                    for t in self.orders[order]['trades']:
                        if t['profit'] > 0:
                            win += t['profit']
                        if t['profit'] < 0:
                            loose -= t['profit']
            print(success, fail, good, trading, win, loose)
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

        t = Thread(target=self.log)
        t.start()


if __name__ == "__main__":
    app = App(api_key=API_KEY, api_sec=API_SECRET)
    app.run()

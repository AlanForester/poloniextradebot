from bittrex.bittrex import Bittrex, API_V1_1
import time
import asyncio

__author__ = 'alex@collin.su'

API_KEY = "4e7cf9c842534da8ab72a2978aeb77ef"
API_SECRET = "9e4adc5ccb0546b7adcccd93e4c058ba"
FEE = 0.5
PROFIT = 0.5
STOP_LIMIT = 10.
BID = 0.00001
MIN_BUY_MORE_VOL = 30


class App:
    def __init__(self, api_key=None, api_sec=None):
        self.orders = {}
        self.api = Bittrex(api_key, api_sec, api_version=API_V1_1)
        self.invest = 0
        self.balance = 0.
        self.trades = {'act': 0, 'buy': 0, 'sell': 0, 'lose': 0}

    async def handler(self, currency, last, trade_history):
        if not self.orders.get(currency) or not self.orders[currency].get('trading', False):
            if not self.orders.get(currency):
                self.orders[currency] = {}

            # Анализатор объема торгов
            if trade_history['success'] and trade_history['result']:
                vol_sell = 0.
                vol_buy = 0.
                vol_all = 0.
                for th in trade_history['result']:
                    if th['OrderType'] == 'BUY':
                        vol_buy += float(th['Total'])
                    if th['OrderType'] == 'SELL':
                        vol_sell += float(th['Total'])
                    vol_all += float(th['Total'])
                if vol_sell != 0.:
                    buy_delta = (vol_buy * 100. / vol_sell) - 100
                else:
                    buy_delta = 100
                if int(buy_delta) >= MIN_BUY_MORE_VOL:
                    self.orders[currency]['time'] = time.time()
                    self.orders[currency]['price'] = last
                    self.orders[currency]['trading'] = True
                    self.orders[currency]['volume'] = float(BID) / last
                    self.orders[currency]['profit'] = 0
                    self.invest += int(float(BID) * 100000000.)
                    self.balance -= float(BID) + (float(BID) * (FEE / 100))
                    self.trades['buy'] += 1
                    self.trades['act'] += 1
                    print("BUY:", currency, "Market:", "+" + str(int(buy_delta)) + "%", "Price:", last,
                          "Fee:", "%.8f" % (float(BID) * (FEE / 100)))
        else:
            comission = (self.orders[currency]['price'] / 100.0) * (FEE + PROFIT)
            price_with_fee = float(comission) + float(self.orders[currency]['price'])
            delta = int((last - price_with_fee) * 100000000. * self.orders[currency]['volume'])
            delta_wo_fee = int(
                (last - float(self.orders[currency]['price'])) * 100000000. * self.orders[currency]['volume'])
            stop_comission = (self.orders[currency]['price'] / 100.0) * (STOP_LIMIT - FEE)
            price_stop = float(self.orders[currency]['price']) - float(stop_comission)

            # Инициализируем массив торгов если не было
            if not self.orders[currency].get('trades'):
                self.orders[currency]['trades'] = []
            trades = self.orders[currency]['trades']

            if price_with_fee < last and delta >= 1:
                # Обработчик на закрытие сделки по прибыли
                trade = dict()
                trade['profit'] = delta
                trade['time'] = time.time()
                trades.append(trade)
                self.orders[currency]['trading'] = False
                self.invest -= int(float(BID) * 100000000.)
                self.balance += float(BID) + (float(delta) / 100000000.)
                self.trades['act'] -= 1
                self.trades['sell'] += 1
                print("SELL:", currency, "Profit:", delta, "Buy:", self.orders[currency]['price'],
                      "Sell:", last, "Delta:", "%.8f" % float(last - self.orders[currency]['price']),
                      "Fee:", "%.8f" % (float(BID) / 100000000.))
            elif price_stop >= last:
                # Обработчик на закрытие по убытку
                trade = dict()
                trade['profit'] = delta
                trade['time'] = time.time()
                trades.append(trade)
                self.orders[currency]['trading'] = False
                self.invest -= int(float(BID) * 100000000.)
                self.balance += float(BID) - (float(delta) / 100000000.)
                self.trades['act'] -= 1
                self.trades['lose'] += 1
                print("LOSE:", currency, "Profit:", delta, "Buy:", self.orders[currency]['price'],
                      "Sell:", last, "Delta:", "%.8f" % float(last - self.orders[currency]['price'] - last),
                      "Fee:", "%.8f" % (float(BID) / 100000000.))
            self.orders[currency]['profit'] = delta_wo_fee
        self.orders[currency]['last'] = last
        return await asyncio.sleep(0)

    async def ticker(self, market):
        # result = await asyncio.gather(
        #     self.api.get_ticker(market),
        #     self.api.get_market_history(market)
        # )
        # tick = result[0]
        # trade_history = result[1]
        tick = await self.api.get_ticker(market)
        trade_history = await self.api.get_market_history(market)
        if tick['success'] and tick['result'] and tick['result']['Last']:
            last = float(tick['result']['Last'])
            return await self.handler(market, last, trade_history)
        return False

    async def log(self):
        while True:
            fail = 0
            success = 0
            trading = 0
            win = 0
            lose = 0

            for order in self.orders.keys():
                if self.orders.get(order) and self.orders[order].get('profit'):
                    if self.orders[order]['profit'] > 0.:
                        success += int(self.orders[order]['profit'])
                    elif self.orders[order]['profit'] < 0.:
                        fail -= int(self.orders[order]['profit'])

                if self.orders[order].get('trading') and self.orders[order]['trading'] == 1:
                    trading += 1

                if self.orders[order].get('trades') and len(self.orders[order]['trades']) > 0:
                    for t in self.orders[order]['trades']:
                        if t['profit'] > 0:
                            win += t['profit']
                        if t['profit'] < 0:
                            lose -= t['profit']

            print("Raise:", success, "Waste:", fail, "Trading:", trading, "Win:", win, "Lose:", lose, "Invest:",
                  "%.8f" % (self.invest / 100000000), "Balance:", "%.8f" % self.balance,
                  "Orders:", self.trades['act'], self.trades['buy'], self.trades['sell'], self.trades['lose'])
            await asyncio.sleep(1)

    async def run(self, input_market=None):
        asyncio.ensure_future(self.log())
        while True:
            gather = []
            if not input_market:
                markets = await self.api.get_markets()
                if markets['success']:
                    for market in markets['result']:
                        check_btc = market['MarketName'].split('-')
                        if check_btc[0] == 'BTC':
                            gather.append(self.ticker(market['MarketName']))
            else:
                gather.append(self.ticker(input_market))
            await asyncio.gather(*gather)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    app = App(api_key=API_KEY, api_sec=API_SECRET)
    loop.run_until_complete(app.run())

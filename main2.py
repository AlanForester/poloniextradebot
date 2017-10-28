from bittrex.bittrex import Bittrex, API_V1_1, API_V2_0
import time
import asyncio
import uvloop
import datetime
from concurrent.futures import ProcessPoolExecutor
from calendar import timegm

__author__ = 'alex@collin.su'

API_KEY = "88e548ba9f424c5bbd6706555aa69109"
API_SECRET = "b1c0bf1aa947490c8a5a1c9a20ae2188"
# API_KEY = "4e7cf9c842534da8ab72a2978aeb77ef"
# API_SECRET = "9e4adc5ccb0546b7adcccd93e4c058ba"
FEE = 0.5
PROFIT = 1.0
STOP_LOSS = 10.
BID = 0.00001
MIN_BUY_MORE_VOL = 500
TIME_LAST_TRADE = 10
BUY_LIMIT = 0.0001
OVER_MINBUY_COEF = 0.1


class App:
    def __init__(self, api_key=None, api_sec=None):
        self.executor = ProcessPoolExecutor(2)
        self.orders = {}
        self.min_trades = {}
        self.api = Bittrex(api_key, api_sec, api_version=API_V2_0)
        self.invest = 0
        self.balance = 0.
        self.trades = {'act': 0, 'buy': 0, 'sell': 0, 'lose': 0}
        self.last_tick = time.time()

    async def buy_handler(self, currency, last):
        # Анализатор объема торгов
        trade_history = await self.api.get_market_history(currency)
        if trade_history['success'] and trade_history['result']:
            vol_sell = 0.
            vol_buy = 0.
            vol_all = 0.
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
                    vol_all += float(th['Quantity'])
            if vol_sell != 0.:
                buy_delta = (vol_buy * 100. / vol_sell) - 100
            else:
                buy_delta = 0

            buy_volume = float(BID) + (float(BID) * (buy_delta / MIN_BUY_MORE_VOL * OVER_MINBUY_COEF))
            if buy_volume > BUY_LIMIT:
                buy_volume = BUY_LIMIT
            if int(buy_delta) >= MIN_BUY_MORE_VOL:
                self.orders[currency]['time'] = time.time()
                self.orders[currency]['price'] = last
                self.orders[currency]['trading'] = True
                self.orders[currency]['volume'] = buy_volume / last
                self.orders[currency]['profit'] = 0
                self.orders[currency]['total'] = self.orders[currency]['volume'] * self.orders[currency]['price']
                total_percent = self.orders[currency]['total'] / 100
                win_percent = FEE + PROFIT
                self.orders[currency]['fee'] = self.orders[currency]['total'] / 100 * FEE
                self.orders[currency]['take_profit'] = total_percent * win_percent + self.orders[currency]['total']
                self.orders[currency]['stop_loss'] = self.orders[currency]['total'] - (total_percent * STOP_LOSS)
                self.invest += int(float(BID) * 100000000.)
                self.balance -= float(BID) + (float(BID) * (FEE / 100))
                self.trades['buy'] += 1
                self.trades['act'] += 1
                print("BUY:", currency, "Market:", "+" + str(int(buy_delta)) + "%",
                      "Price:", "%.8f" % last,
                      "Vol:", "%.8f" % self.orders[currency]['volume'], "Fee:",
                      "%.8f" % self.orders[currency]['fee'])
        return True

    async def sell_handler(self, currency, last):
        current_price = last * self.orders[currency]['volume']
        delta = int((current_price - self.orders[currency]['total']) * 100000000.)
        delta_with_fee = delta - int(self.orders[currency]['fee'] * 100000000.)
        self.orders[currency]['profit'] = delta
        # Инициализируем массив торгов если не было
        if not self.orders[currency].get('trades'):
            self.orders[currency]['trades'] = []
        trades = self.orders[currency]['trades']

        if current_price > self.orders[currency]['take_profit']:
            # Обработчик на закрытие сделки по прибыли
            trade = dict()
            trade['profit'] = delta_with_fee
            trade['time'] = time.time()
            trades.append(trade)
            self.orders[currency]['trading'] = False
            self.invest -= int(float(BID) * 100000000.)
            self.balance += float(BID) + (float(delta) / 100000000.)
            self.trades['act'] -= 1
            self.trades['sell'] += 1
            print("SELL:", currency, "Profit:", delta_with_fee,
                  "Buy:", "%.8f" % self.orders[currency]['price'],
                  "Sell:", "%.8f" % last,
                  "Vol:", "%.8f" % self.orders[currency]['volume'],
                  "Delta:", "%.8f" % delta,
                  "Fee:", "%.8f" % self.orders[currency]['fee'])
        elif current_price <= self.orders[currency]['stop_loss']:
            # Обработчик на закрытие по убытку
            trade = dict()
            trade['profit'] = delta_with_fee
            trade['time'] = time.time()
            trades.append(trade)
            self.orders[currency]['trading'] = False
            self.invest -= int(float(BID) * 100000000.)
            self.balance += float(BID) - (float(delta) / 100000000.)
            self.trades['act'] -= 1
            self.trades['lose'] += 1
            print("LOSE:", currency, "Profit:", delta_with_fee,
                  "Buy:", "%.8f" % self.orders[currency]['price'],
                  "Sell:", "%.8f" % last,
                  "Vol:", "%.8f" % self.orders[currency]['volume'],
                  "Delta:", "%.8f" % delta,
                  "Fee:", "%.8f" % self.orders[currency]['fee'])

    async def handler(self, currency, last):
        if not self.orders.get(currency) or not self.orders[currency].get('trading', False):
            if not self.orders.get(currency):
                self.orders[currency] = {}
            self.orders[currency]['working'] = asyncio.ensure_future(self.buy_handler(currency, last))
        else:
            await self.sell_handler(currency, last)
        self.orders[currency]['last'] = last

    async def ticker(self, market, tick):
        if float(self.min_trades.get(market, 0.)):
            if not self.orders.get(market) or \
                    (self.orders.get(market) and self.orders[market].get('working')
                     and self.orders[market]['working'].done()):
                return await self.handler(market, float(tick))
        return False

    async def log(self):
        while True:
            fail = 0
            fail_c = 0
            success = 0
            success_c = 0
            trading = 0
            win = 0
            lose = 0
            fee = 0
            uniq = {}
            for order in self.orders.keys():
                if self.orders[order].get('trading', False):
                    if self.orders.get(order) and self.orders[order].get('profit'):
                        if self.orders[order]['profit'] > 0.:
                            success_c += 1
                            success += int(self.orders[order]['profit'])
                        elif self.orders[order]['profit'] < 0.:
                            fail_c += 1
                            fail -= int(self.orders[order]['profit'])
                    trading += 1
                    if not uniq.get(order):
                        uniq[order] = 1
                if self.orders[order].get('trades') and len(self.orders[order]['trades']) > 0:
                    for t in self.orders[order]['trades']:
                        if t['profit'] > 0:
                            win += t['profit']
                        if t['profit'] < 0:
                            lose -= t['profit']
                if self.orders[order].get('fee'):
                    fee += self.orders[order].get('fee')

            u = 0
            for k in uniq.keys():
                u += 1
            print("Raise:", str(success) + "(" + str(success_c) + ")", "Waste:", str(fail) + "(" + str(fail_c) + ")",
                  "Fee:", int(fee * 100000000.), "Trading:", trading, "Take:", win, "Loss:", lose, "Invest:",
                  "%.8f" % (self.invest / 100000000), "Balance:", "%.8f" % self.balance,
                  "Orders(All,Profit,Loss):", self.trades['buy'], self.trades['sell'], self.trades['lose'],
                  "Tick:", str(int(time.time() - self.last_tick))+'sec.',
                  "Uniq:", u)
            await asyncio.sleep(1)

    async def run(self, input_market=None):
        asyncio.ensure_future(self.log())
        while True:
            markets = await self.api.get_market_summaries()
            if markets['success']:
                gather = []
                for market in markets['result']:
                    if not input_market:
                        check_btc = market['Summary']['MarketName'].split('-')
                        if check_btc[0] == 'BTC':
                            self.min_trades[market['Market']['MarketName']] = market['Market']['MinTradeSize']
                            gather.append(self.ticker(market['Summary']['MarketName'], market['Summary']['Last']))
                    else:
                        if market['Summary']['MarketName'] == input_market:
                            self.min_trades[market['Market']['MarketName']] = market['Market']['MinTradeSize']
                            gather.append(self.ticker(market['Summary']['MarketName'], market['Summary']['Last']))
                if len(gather) > 0:
                    await asyncio.gather(*gather)
            self.last_tick = time.time()
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    app = App(api_key=API_KEY, api_sec=API_SECRET)
    loop.run_until_complete(app.run())

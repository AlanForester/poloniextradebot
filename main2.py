from bittrex.bittrex import Bittrex, API_V1_1, API_V2_0
import time
import asyncio
import uvloop
import datetime
import aiohttp
import aiofiles
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
__author__ = 'alex@collin.su'

# API_KEY = "88e548ba9f424c5bbd6706555aa69109"
# API_SECRET = "b1c0bf1aa947490c8a5a1c9a20ae2188"
API_KEY = "4e7cf9c842534da8ab72a2978aeb77ef"
API_SECRET = "9e4adc5ccb0546b7adcccd93e4c058ba"

FEE = 0.5
# Take profit цена (PROFIT + FEE)
PROFIT = 2.5
# Stop loss цена
STOP_LOSS = 20.
# Сумма покупки актива BTC
BID = 0.00001

# Время выборки данных из истории торгов
# Условие для длительного анализа истории

# Условие которое ограничевает покупку валют объем покупок которых
# ниже чем продаж в процентном соотношении
TIME_LAST_TRADE = {
    10: [1, None],  # От до
    120: [None, -5],
}

PASS_TIME_CONFIRMED = True

LOGGING_TO_FILE = False
# Максимальная сумма BTC при покупке актива
BUY_LIMIT = 0.0001
# Коэффициэнт суммы покупки на превышение минимального объема MIN_BUY_MORE_VOL
OVER_MIN_BUY_COEFFICIENT = 0.1

# Минимальная разница высокой и низкой цены за 24ч
MARKET_HIGH_LOW_MIN_DELTA = 50
# Условие для разности цены актива (Больше меньше)
MARKET_DELTA_CONDITION = 'more'  # 'more' or 'less'

# Максимальный спред, отключить - 0
MAX_SPREAD = 0


class App:
    def __init__(self, api_key=None, api_sec=None):
        self.orders = {}
        self.min_trades = {}

        self.api = Bittrex(api_key, api_sec, api_version=API_V2_0)
        self.invest = 0
        self.trades = {'act': 0, 'buy': 0, 'sell': 0, 'lose': 0}
        self.last_tick = time.time()
        dt = datetime.datetime.now()
        self.init_time_str = dt.strftime("%Y-%m-%d_%H-%M-%S")

    async def buy_handler(self, currency, last):
        # Анализатор объема торгов
        trade_history = await self.api.get_candles(currency, 'fiveMin')
        if trade_history.get('success') and trade_history['result']:
            confirm_trade = True
            first_trade_vol = 0.
            first_time = None
            time_confirmation = {}
            volumes = {}
            for trade_min in TIME_LAST_TRADE.keys():
                change = 0.
                first_candle = None
                if time_confirmation.get(trade_min) is None:
                    time_confirmation[trade_min] = False
                if volumes.get(trade_min) is None:
                    volumes[trade_min] = 0.
                for th in trade_history['result']:
                    ts = int(datetime.datetime.strptime(th['T'], '%Y-%m-%dT%H:%M:%S').timestamp()) + 10800
                    now = int(time.time())
                    if ts > now - (trade_min * 60):
                        if first_candle is None:
                            first_candle = th
                        change = float(th['C']) / (float(first_candle['O']) / 100.)
                        time_confirmation[trade_min] = True
                if change != .0:
                    buy_delta = change - 100.
                else:
                    buy_delta = 0.

                volumes[trade_min] = buy_delta

                if first_time is None or first_time >= trade_min:
                    first_time = trade_min
                    first_trade_vol = buy_delta

                if not TIME_LAST_TRADE[trade_min][0] is None:
                    if buy_delta < float(TIME_LAST_TRADE[trade_min][0]):
                        confirm_trade = False
                        break
                if not TIME_LAST_TRADE[trade_min][1] is None:
                    if buy_delta > float(TIME_LAST_TRADE[trade_min][1]):
                        confirm_trade = False
                        break

            time_confirmed = True
            for confirm in time_confirmation.keys():
                if not time_confirmation[confirm]:
                    time_confirmed = False
                    break

            buy_volume = float(BID)
            if first_trade_vol != 0. and first_time != 0:
                buy_volume += (float(BID) * (first_trade_vol / float(first_time) * float(OVER_MIN_BUY_COEFFICIENT)))

            if buy_volume > BUY_LIMIT:
                buy_volume = BUY_LIMIT
            if confirm_trade and (time_confirmed or PASS_TIME_CONFIRMED):
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
                self.trades['buy'] += 1
                self.trades['act'] += 1
                now = datetime.datetime.now()
                log = "[{0}] BUY  - {1} Market:{2} Price:{3} Vol:{4} Total:{5} Fee:{6}" \
                    .format(now.strftime('%Y-%m-%d %H:%M:%S'),
                            currency, "%.2f" % float(first_trade_vol) + "%",
                            "%.8f" % last,
                            "%.8f" % self.orders[currency]['volume'],
                            "%.8f" % self.orders[currency]['total'],
                            "%.8f" % self.orders[currency]['fee'])
                print(log, volumes)
                if LOGGING_TO_FILE:
                    async with aiofiles.open('./logs/{0}_trades.log'.format(self.init_time_str), 'a+') as f:
                        await f.write(str(log) + '\n')
        return True

    async def handler(self, currency, last):
        if not self.orders.get(currency):
            self.orders[currency] = {'last': last}
        if not self.orders.get(currency) or not self.orders[currency].get('trading', False):
            self.orders[currency]['task'] = asyncio.ensure_future(self.buy_handler(currency, last))
        else:
            current_price = last * self.orders[currency]['volume']
            delta = int((current_price - self.orders[currency]['total']) * 100000000.)
            delta_with_fee = delta - int(self.orders[currency]['fee'] * 100000000.)
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
                self.trades['act'] -= 1
                self.trades['sell'] += 1
                now = datetime.datetime.now()
                log = "[{0}] SELL  - {1} Profit:{2} Buy:{3} Sell:{4} Vol:{5} Total:{6} Delta:{7} Fee:{8}" \
                    .format(now.strftime('%Y-%m-%d %H:%M:%S'),
                            currency, delta_with_fee, "%.8f" % self.orders[currency]['price'],
                            "%.8f" % last, "%.8f" % self.orders[currency]['volume'],
                            "%.8f" % self.orders[currency]['total'],
                            "%.8f" % delta, "%.8f" % self.orders[currency]['fee'])
                print(log)
                if LOGGING_TO_FILE:
                    async with aiofiles.open('./logs/{0}_trades.log'.format(self.init_time_str), 'a+') as f:
                        await f.write(log + '\n')
            elif current_price <= self.orders[currency]['stop_loss']:
                # Обработчик на закрытие по убытку
                trade = dict()
                trade['profit'] = delta_with_fee
                trade['time'] = time.time()
                trades.append(trade)
                self.orders[currency]['trading'] = False
                self.invest -= int(float(BID) * 100000000.)
                self.trades['act'] -= 1
                self.trades['lose'] += 1
                now = datetime.datetime.now()
                log = "[{0}] LOSS - {1} Profit:{2} Buy:{3} Sell:{4} Vol:{5} Total:{6} Delta:{7} Fee:{8}" \
                    .format(now.strftime('%Y-%m-%d %H:%M:%S'),
                            currency, delta_with_fee, "%.8f" % self.orders[currency]['price'],
                            "%.8f" % last, "%.8f" % self.orders[currency]['volume'],
                            "%.8f" % self.orders[currency]['total'],
                            "%.8f" % delta, "%.8f" % self.orders[currency]['fee'])
                print(log)
                if LOGGING_TO_FILE:
                    async with aiofiles.open(
                            './logs/{0}_trades.log'.format(self.init_time_str).format(self.init_time_str),
                            'a+') as f:
                        await f.write(log + '\n')
            self.orders[currency]['profit'] = delta
        return last

    async def ticker(self, market, tick):
        if float(self.min_trades.get(market, 0.)) != 0.:
            if not self.orders.get(market) or \
                    (self.orders.get(market) and self.orders[market].get('task')
                     and self.orders[market]['task'].done()):
                asyncio.ensure_future(self.handler(market, float(tick)))

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

                    model = self.orders[order]
                    curr_price = model['last'] * model['volume']
                    delta = int((model['last'] - model['price']) * model['volume'] * 100000000)
                    now = datetime.datetime.now()
                    if LOGGING_TO_FILE:
                        async with open('./logs/{0}_markets.log'.format(self.init_time_str), 'a+') as f:
                            await f.write(
                                "[{0}] {1} - Last:{2} Buy:{3} TP:{7} SL:{9} | BUY Vol:{4} Total:{11} Delta:{5} Fee:{6} "
                                "| LEFT TP:{8} SL:{10}\n".format(now.strftime('%Y-%m-%d %H:%M:%S'), order,
                                                                 "%.8f" % model['last'], "%.8f" % model['price'],
                                                                 "%.8f" % model['volume'],
                                                                 "%d" % delta, "%d" % int(model['fee'] * 100000000),
                                                                 "%.8f" % (model['take_profit'] / model['volume']),
                                                                 int((model['take_profit'] - curr_price) * 100000000),
                                                                 "%.8f" % (model['stop_loss'] / model['volume']),
                                                                 int((curr_price - model['stop_loss']) * 100000000),
                                                                 "%.8f" % model['total']))
                if self.orders[order].get('trades') and len(self.orders[order]['trades']) > 0:
                    for t in self.orders[order]['trades']:
                        if t['profit'] > 0:
                            win += t['profit']
                        if t['profit'] < 0:
                            lose -= t['profit']
                if self.orders[order].get('fee'):
                    fee += self.orders[order].get('fee')
            if LOGGING_TO_FILE:
                async with open('./logs/{0}_markets.log'.format(self.init_time_str), 'a+') as f:
                    await wf.write(
                        "=======================================================================================\n")
            now = datetime.datetime.now()
            print("[" + now.strftime('%Y-%m-%d %H:%M:%S') + "]", "INFO -", "Raise:",
                  str(success) + "(" + str(success_c) + ")", "Waste:",
                  str(fail) + "(" + str(fail_c) + ")",
                  "Fee:", int(fee * 100000000.), "Take:", win, "Loss:", lose,
                  "| Invest:", "%.8f" % (self.invest / 100000000),
                  "Balance:", win + success - fail - int(fee * 100000000.) - lose,
                  "Orders(All,Profit,Loss):", self.trades['buy'], self.trades['sell'], self.trades['lose'],
                  "Tick:", str(int(time.time() - self.last_tick)) + 'sec.',
                  "Trading:", trading)
            await asyncio.sleep(1)

    async def run(self, input_market=None):
        asyncio.ensure_future(self.log())
        async with aiohttp.ClientSession() as session:
            self.api.session = session
            while True:
                markets = await self.api.get_market_summaries()
                if markets.get('success'):
                    gather = []
                    for market in markets['result']:
                        market_delta = float(market['Summary']['High']) - float(market['Summary']['Low'])
                        market_delta_sat = int(market_delta * 100000000)
                        cond = market_delta_sat >= MARKET_HIGH_LOW_MIN_DELTA
                        if MARKET_DELTA_CONDITION == 'less':
                            cond = market_delta_sat <= MARKET_HIGH_LOW_MIN_DELTA
                        spread = float(market['Summary']['Ask']) - float(market['Summary']['Bid'])
                        spread_sat = int(spread) * 100000000
                        if cond and (spread_sat <= MAX_SPREAD or MAX_SPREAD == 0):
                            if not input_market:
                                check_btc = market['Summary']['MarketName'].split('-')
                                if check_btc[0] == 'BTC':
                                    self.min_trades[market['Market']['MarketName']] = market['Market']['MinTradeSize']
                                    gather.append(asyncio.ensure_future(
                                        self.ticker(market['Summary']['MarketName'], market['Summary']['Last'])))
                            else:
                                if market['Summary']['MarketName'] == input_market:
                                    self.min_trades[market['Market']['MarketName']] = market['Market']['MinTradeSize']
                                    gather.append(asyncio.ensure_future(
                                        self.ticker(market['Summary']['MarketName'], market['Summary']['Last'])))
                    if len(gather) > 0:
                        await asyncio.gather(*gather)
                self.last_tick = time.time()
                await asyncio.sleep(1)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    app = App(api_key=API_KEY, api_sec=API_SECRET)
    future = asyncio.ensure_future(app.run(), loop=loop)
    loop.run_until_complete(future)

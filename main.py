from poloniex.app import AsyncApp

__author__ = 'alex@collin.su'

API_KEY = "CNVUTAVQ-YGE5S5HN-0FA8BA7U-QQC2MRAP"
API_SECRET = "abec87d8ba68ed29893927e770879e8291003f5cfc3cf9cf3ae6bdcfd2c293f8f2f43c84b5d966d668c742165df71fc8207e7a0eed1e8052e83b5195b4775792"

class App(AsyncApp):
    def ticker(self, **kwargs):
        self.logger.info(kwargs)

    def trades(self, **kwargs):
        self.logger.info(kwargs)

    async def main(self):
        self.push.subscribe(topic="BTC_ETH", handler=self.trades)
        self.push.subscribe(topic="ticker", handler=self.ticker)
        volume = await self.public.return24hVolume()

        self.logger.info(volume)


if __name__ == "__main__":
    app = App(api_key=API_KEY, api_sec=API_SECRET)
    app.run()

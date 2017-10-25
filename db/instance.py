import asyncpg


class Instance:
    def __init__(self, user, password, db, host):
        super().__init__()
        self.user = user
        self.password = password
        self.db = db
        self.host = host
        self.connect = None

    async def connect(self):
        self.connect = await asyncpg.connect(user=self.user, password=self.password, database=self.db, host=self.host)
        return self.connect

    async def close(self):
        if self.connect:
            await self.connect.close()
            self.connect = None

    async def query(self, query):
        return await self.connect.fetch(query)

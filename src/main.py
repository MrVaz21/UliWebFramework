import os
from UliServer import UliServer, HttpMessage
import asyncio
server = UliServer(host = "localhost", port = 5000)
async def main():

    @server.Handler(Method = "GET", RequestURL = "/")
    async def hello_world(request):
        index_path = os.path.join(os.path.dirname(__file__), "../files/readme.html")
        print(index_path)
        with open(index_path, encoding="utf-8") as f:
            message = HttpMessage()
            data_bytes = f.read().encode("utf-8")
            message = message.from_params(status_code=200, reason="OK Nice to meet you", body=data_bytes)
            return message
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
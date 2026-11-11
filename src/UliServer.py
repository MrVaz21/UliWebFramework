import asyncio
import logging
from exceptions import NotFound, MethodNotAllowed
from HttpMessage import HttpMessage
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')



class UliServer:
    async def message_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, data_bytes: bytes):
        try:
            if writer.is_closing():
                raise ValueError("Не можем отрпавить ответ тк соеденение закрыто")
            request_ = HttpMessage()
            request_ = request_.from_bytes(data_bytes)
            if request_ is not None:
                key = (request_.method, request_.request_url)
                logger.info(self.handlers)
                if self.handlers.get(key) is None:
                    if request_.request_url in self.AllowedUrls:
                        raise MethodNotAllowed
                    raise NotFound
                http_message = await self.handlers[key](request_)

                logger.info(http_message.in_bytes)
                need_close = False
                if request_.headers.get("connection"):
                    need_close = (request_.headers["connection"]) == "close"
                if need_close:
                    http_message.headers["Connection"] = "close"

                writer.write(http_message.calc_in_bytes())
                await writer.drain()
                if need_close:
                    writer.close()
            else:
                raise ValueError("Запрос не удовлетворительный")
        except NotFound:
            response = HttpMessage()
            response = response.default_error_404()
            if not writer.is_closing():
                writer.write(response.in_bytes)
                await writer.drain()
                writer.close()
            else:
                logger.error("Мы не можем отправить ошибку - соединение закрыто")
        except MethodNotAllowed:
            response = HttpMessage()
            response = response.default_error_405()
            if not writer.is_closing():
                writer.write(response.in_bytes)
                await writer.drain()
                writer.close()
            else:
                logger.error("Мы не можем отправить ошибку - соединение закрыто")

        except Exception as e:
            logger.error(f"Ошибка {e}")
            response = HttpMessage()
            response = response.default_error_503()
            if not writer.is_closing():
                writer.write(response.in_bytes)
                await writer.drain()
                writer.close()
            else:
                logger.error("Мы не можем отправить ошибку - соединение закрыто")

    async def cut_bytes(self, cur_bytes, reader, writer):

        while True:
            if writer.is_closing():
                return b""
            idx = cur_bytes.find(b"\r\n\r\n")
            if idx == -1:
                return cur_bytes
            header = HttpMessage()
            header = header.from_bytes(cur_bytes[:idx + 4])
            if not header:
                raise ValueError("Ошибка заголовка")
            sizeof= header.headers.get("content-length")
            if sizeof:
                sizeof = int(sizeof) + len(cur_bytes[:idx + 4])
                if len(cur_bytes) >= int(sizeof):
                    await self.message_handler(reader, writer, cur_bytes[:int(sizeof)])
                    cur_bytes = cur_bytes[int(sizeof):]
                    continue
                return cur_bytes
            await self.message_handler(reader, writer, cur_bytes[:idx+4])
            cur_bytes = cur_bytes[idx + 4:]

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.handlers = {}
        self.AllowedUrls = set()
        self.timeout = 60
    def Handler(self, Method, RequestURL):

        def modifed_handler(func):
            async def modifed_func(*args, **kwargs):
                value = await func(*args, **kwargs)
                return value

            key = tuple([Method, RequestURL])
            self.handlers[key] = modifed_func
            self.AllowedUrls.add(RequestURL)
            return modifed_func

        return modifed_handler


    async def user_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        cur_user_bytes = b""

        #берем текущий  набор байт если там есть заголовок отилчно, чекаем есть ли там размер контента если есть чекаем хватает ли байтов чтобы извелчь если не хватает возвращаем not enough и уходим на утерацию еще одну, если есть зоголовок, но нет длины контента то возращаем okey и обрезанный буфер и вызываем функцию повторно, если с хедером что то не так возрващаем reaise, если есть хедер, длина контента и хватает, то возвращаем обрезанный и вызываем функцию,
        while True:
            try:
                data_bytes = await asyncio.wait_for(reader.read(1024), timeout=self.timeout)
                if data_bytes == b"":
                    raise ValueError("Вероятно соеденение закрыто")
                cur_user_bytes += data_bytes
                cur_user_bytes = await self.cut_bytes(cur_user_bytes, reader, writer)

            except Exception as e:
                logger.error(f"Ошибка, возможно пользователь закрыл соеденение или превышено время ожидания")
                logger.info("Принудительно закрываю соеденение")
                try:
                    writer.close()
                except Exception as e:
                    logger.error(f"Не удалось закрыть соеденение {e}")
                finally:
                    break


    async def connection_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            await self.user_handler(reader, writer)
        except Exception as e:
            logging.error(f"Ошибка отправки приветствия{e}")


    async def start(self):
        logger.info("Сервер запущен")
        server = await asyncio.start_server(self.connection_handler, self.host, self.port)
        async with server:
            await server.serve_forever()


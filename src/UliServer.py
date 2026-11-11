import asyncio
import logging
from email.utils import formatdate

from exceptions import NotFound, MethodNotAllowed
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
class HttpMessage:
    def __init__(self):
        self.method = None
        self.request_url = None
        self.http_version = None
        self.headers = {}
        self.body = b""
        self.type = ""
        self.in_bytes = b""
        self.status_code = None
        self.reason = None

    def from_bytes(self, data: bytes):
        try:

            line_end = data.find(b"\r\n")
            if line_end == -1:
                raise ValueError("Нет конца стартовой строки")
            start_line = data[:line_end].decode("latin-1")
            parts = start_line.split(" ")
            if len(parts) != 3:
                raise ValueError(f"Кривая стартовая строка: {start_line!r}")
            self.method, self.request_url, self.http_version = parts
            data = data[line_end + 2:]


            while True:
                line_end = data.find(b"\r\n")
                if line_end == -1:
                    raise ValueError("Заголовки не закончились пустой строкой")
                line = data[:line_end]
                data = data[line_end + 2:]

                if line == b"":
                    break


                try:
                    text = line.decode("latin-1")
                except UnicodeDecodeError:
                    text = line.decode("ascii", errors="replace")

                if ":" not in text:
                    logger.warning(f"Строка без ':' пропущена: {text!r}")
                    continue

                key, _, value = text.partition(":")
                key = key.lower()
                self.headers[key.strip()] = value.strip()


            self.body = data
            if "content-length" in self.headers:
                if int(self.headers["content-length"]) != len(self.body):
                    raise ValueError("Размер body не совпадает с content-length")
            self.type = "request"
            return self

        except Exception as e:
            logger.error(f"Ошибка обработки запроса: {e}")
            return None

    def default_error_503(self):
        header = (
            "HTTP/1.1 503 Service Unavailable\r\n"
            "Content-Length: 0\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        self.status_code = 503
        self.reason = "Service Unavailable"
        self.in_bytes = header.encode()
        self.type = "response"
        return self
    def default_error_404(self):
        header = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Length: 0\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        self.status_code = 404
        self.reason = "Not Found"
        self.in_bytes = header.encode()
        self.type = "response"
        return self
    def default_error_405(self):
        header = (
            "HTTP/1.1 405 Method Not Allowed\r\n"
            "Content-Length: 0\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        self.status_code = 405
        self.reason = "Method Not Allowed"
        self.in_bytes = header.encode()
        self.type = "response"
        return self
    def calc_in_bytes(self):
        if len(self.body) > 0:
            if not self.headers.get("Content-Length"):
                self.headers["Content-Length"] = str(len(self.body))
            elif int(self.headers["Content-Length"]) != len(self.body):
                raise ValueError("размер body не совпадает с content-length")
        else:
            self.headers["Content-Length"] = "0"
        if not self.headers.get("Date"):
            self.headers["Date"] = formatdate(timeval=None, usegmt=True)
        response_line = self.http_version + " " + str(self.status_code) + " " + self.reason + "\r\n"
        headers_in_str = ""
        for key, value in self.headers.items():
            pair = f"{key}: {value}\r\n"
            headers_in_str += pair

        head = (response_line + headers_in_str + "\r\n").encode()
        head += self.body
        self.in_bytes =head
        return self.in_bytes
    def from_params(self, http_version: str = "HTTP/1.1", status_code: int = 503, reason: str = "", headers: dict | None = None, body: bytes = b""):
        try:
            if headers is None:
                headers = {}
            new_headers = {}
            for key, value in headers.items():
                key = str(key)
                new_headers[key] = str(value)

            headers = new_headers

            self.headers = headers
            self.status_code = status_code
            self.http_version = http_version
            self.body = body
            self.reason= reason
            self.type = "response"
            self.calc_in_bytes()
            return self
        except Exception as e:
            logger.error(f"Ошибка формирования ответа {e}")
            return self.default_error_503()






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


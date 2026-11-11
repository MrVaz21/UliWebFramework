import logging
from email.utils import formatdate
logger = logging.getLogger(__name__)

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




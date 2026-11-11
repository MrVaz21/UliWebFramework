import socket
from time import sleep

def send_greeting():
    # Создаём TCP-сокет
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Подключаемся к локальному серверу на порту 5000
        sock.connect(("localhost", 5000))

        # Формируем HTTP-запрос (по стандарту он должен заканчиваться \r\n\r\n)
        request = (
            "GET / HTTP/1.1\r\n"
            "Host: localhost:5000\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        data= sock.recv(1024)
        print(data.decode("utf-8"))
        # Отправляем запрос
        sock.sendall(request.encode("utf-8"))


        while True:
            sleep(1)
            try:
                sock.sendall(b"Hi bro")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(e)
                break


if __name__ == "__main__":
    send_greeting()
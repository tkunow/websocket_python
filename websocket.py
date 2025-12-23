import logging
import socket
import hashlib
from base64 import b64encode
import struct
from enum import Enum

class Opcode(Enum):
    CONTINUE_FRAME = 0
    TEXT_FRAME = 1
    BINARY_FRAME = 2
    CONNECTION_CLOSE = 8
    PING = 9
    PONG = 10

class Websocket:
    def __init__(self, address:str = '127.0.0.1', port: int = 80):
        self.address = address
        self.port = port
        self.connections = []
    
    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.address, self.port))
            s.listen(1)

            logging.info(f"[WS] listening on {self.address}:{self.port}")

            conn, addr = s.accept()
            logging.info("[TCP] connection from", addr)

            self.accept_handshake(conn)

            while True:
                msg = self.recv_frame(conn)
                if msg is None:
                    print("[WS] Connection closed")
                    break
                print("[WS] Received:", msg)


    def recv_frame(self, conn:socket) -> str:
        try:
            first_byte = conn.recv(1)
            print("first byte:", first_byte)

            if not first_byte:
                return None

            opcode = first_byte[0] & 0b00001111
            print("opcode:",opcode)
            if opcode == Opcode.TEXT_FRAME.value: 
                return self._text_frame(conn)
            elif opcode == Opcode.CONNECTION_CLOSE.value:
                self.close_handshake
        except Exception as e:
            print("[WS] Error:", e)
            return None

    def _text_frame(self, conn: socket) -> str:
        second_byte = conn.recv(1)
        print("second byte:", second_byte)
        payload_len = second_byte[0] & 0b01111111
        print("payload len:", payload_len)

        if payload_len == 126:
            payload_len = struct.unpack(">H", conn.recv(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", conn.recv(8))[0]

        print("payload len2:", payload_len)
        mask = conn.recv(4)
        print("mask:", mask)
        payload = conn.recv(payload_len)
        print("payload:", payload)

        decoded = bytes(
            payload[i] ^ mask[i % 4] for i in range(payload_len)
        )

        return decoded.decode("utf-8", errors="ignore")


    def close_handshake(self, conn:socket):
        print("close")

        conn.close()
        return None

    def accept_handshake(self, conn: socket):
        data = conn.recv(1024).decode()
        sec_websocket_key: str

        for line in data.split("\r\n"):
            if not line.find("Sec-WebSocket-Key"):
                sec_websocket_key = line.split(" ")[1]

        sha1 = hashlib.sha1()
        sha1.update((sec_websocket_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode())
        sec_websocket_accept = b64encode(sha1.digest()).decode()

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {sec_websocket_accept}\r\n"
            "\r\n"
        )

        conn.sendall(response.encode())
    
    def close(self) -> None:
        self.sock.close()
        logging.info("[TCP] close TCP socket")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    sock = Websocket()
    try:
        sock.start()
    except KeyboardInterrupt:
        sock.close()
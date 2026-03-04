import logging
import hashlib
from base64 import b64encode
import struct
from enum import Enum
import asyncio

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
        self.connections = set()
    
    
    async def start(self):
        server = await asyncio.start_server(self.handle_connections, self.address, self.port)

        async with server:
            await server.serve_forever()


    async def handle_connections(self, reader, writer):
        await self.accept_handshake(reader, writer)
        self.connections.add(writer)

        try:
            while True:
                msg = await self.recv_frame(reader, writer)
                if msg is None:
                    logging.info("Connection closed")
                    break
                logging.info(f"Received > {msg}")

        finally:
            logging.info("CLient disconnected")


    async def recv_frame(self, reader, writer) -> str:
        try:
            first_byte = await reader.readexactly(1)
            logging.info(f"first byte > {first_byte}")

            if not first_byte:
                return None

            opcode = first_byte[0] & 0b00001111
            logging.info(f"opcode > {opcode}")
            if opcode == Opcode.TEXT_FRAME.value: 
                message = await self._text_frame(reader)
                await self.send_frame(writer, message)
                return message
            elif opcode == Opcode.CONNECTION_CLOSE.value:
                await self.close_handshake(reader, writer)
            elif opcode == Opcode.PONG.value:
                await self._pong_frame(reader)
        except Exception as e:
            logging.error("Error:", e)
            return None

    async def send_frame(self, writer, data: str):
        first_byte = b'\x81'
        lenght = len(data)
        if lenght < 126:
            second_byte = struct.pack('<B', 0b00000000 | lenght)

        frame = first_byte + second_byte + data.encode()

        logging.info(f"send frame > {frame}")

        for client in self.connections:
            if client != writer:
                client.write(frame)
                await client.drain()

    async def _text_frame(self, reader) -> str:
        second_byte = await reader.readexactly(1)
        logging.info(f"second byte > {second_byte}")
        payload_len = second_byte[0] & 0b01111111
        logging.info(f"payload len > {payload_len}")

        if payload_len == 126:
            payload_len = struct.unpack(">H", await reader.readexactly(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", await reader.readexactly(8))[0]

        logging.info(f"payload len2 > {payload_len}")
        mask = await reader.readexactly(4)
        logging.info(f"mask > {mask}")
        payload = await reader.readexactly(payload_len)
        logging.info(f"payload > {payload}")

        
        decoded = bytes(
            payload[i] ^ mask[i % 4] for i in range(payload_len)
        )

        return decoded.decode("utf-8", errors="ignore")

    async def _pong_frame(self, reader):
        second_byte = await reader.readexactly(1)
        logging.info(f"pong_frame > {second_byte}")

    async def _ping_frame(self, writer):
        try:
            while True:
                await asyncio.sleep(10)

                logging.info("send ping frame")
                ping_code = b'\x89\x00'
                writer.write(ping_code)
                await writer.drain()
        except asyncio.CancelledError:
            logging.error("ping_frame error")
            pass


    async def close_handshake(self, reader, writer):

        self.connections.remove(writer)
        writer.close()
        await writer.wait_closed()

        return None

    async def accept_handshake(self, reader, writer):
        logging.info("new connection")
        data = await reader.read(1024)
        headers = data.decode().split("\r\n")
        sec_websocket_key: str

        for line in headers:
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

        writer.write(response.encode())
        await writer.drain()
    
    def close(self) -> None:
        self.sock.close()
        logging.info("close TCP socket")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    asyncio.run(Websocket().start())

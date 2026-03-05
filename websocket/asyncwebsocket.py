import logging
import hashlib
from base64 import b64encode
import struct
from enum import Enum
import asyncio
from typing import NamedTuple, Callable

class Opcode(Enum):
    CONTINUE_FRAME = 0
    TEXT_FRAME = 1
    BINARY_FRAME = 2
    CONNECTION_CLOSE = 8
    PING = 9
    PONG = 10

type Address = tuple[str, int]
type Writer = asyncio.StreamWriter
type Reader = asyncio.StreamReader
class Endpoint(NamedTuple):
    address: Address
    writer: Writer
    reader: Reader
    itemid: int


class Websocket:
    def __init__(self, address: Address):
        self.address = address
        self.connections = set()
        self.handler = None

    def __call__(self, func):
        self.handler = func

        async def wrapper(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Callable:
            logging.info("call decorator")
            await func(reader, writer)

        wrapper.recv_frame = self.recv_frame
        wrapper.send_frame = self.send_frame
        wrapper.accept_handshake = self.accept_handshake
        return wrapper

    async def start(self):
        logging.info("start socket: %s", self.address)
        server = await asyncio.start_server(self.handler, self.address[0], self.address[1])

        async with server:
            await server.serve_forever()

    async def recv_frame(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> str:
        try:
            first_byte = await reader.readexactly(1)
            logging.info("first byte > %s", first_byte)

            if not first_byte:
                return None

            opcode = first_byte[0] & 0b00001111
            logging.info("opcode > %s", opcode)
            if opcode == Opcode.TEXT_FRAME.value: 
                message = await self._text_frame(reader)
                # await self.send_frame(writer, message)
                return message
            elif opcode == Opcode.CONNECTION_CLOSE.value:
                await self.close_handshake(writer)
            elif opcode == Opcode.PONG.value:
                await self._pong_frame(reader)
        except Exception as e:
            logging.error("Error: %s", e)
            return None

    async def send_frame(self, writer: asyncio.StreamWriter, data: str):
        first_byte = b'\x81'
        lenght = len(data)
        if lenght < 126:
            second_byte = struct.pack('<B', 0b00000000 | lenght)
        else:
            logging.info("cancel send, payload length > 125")
            return

        frame = first_byte + second_byte + data.encode()

        logging.info("send frame > %s", frame)

        for client in self.connections:
            if client != writer:
                client.writer.write(frame)
                await client.writer.drain()

    async def _text_frame(self, reader: asyncio.StreamReader) -> str:
        second_byte = await reader.readexactly(1)
        logging.info("second byte > %s", second_byte)
        payload_len = second_byte[0] & 0b01111111
        logging.info("payload len > %s", payload_len)

        if payload_len == 126:
            payload_len = struct.unpack(">H", await reader.readexactly(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", await reader.readexactly(8))[0]

        logging.info("payload len2 > %s", payload_len)
        mask = await reader.readexactly(4)
        logging.info("mask > %s", mask)
        payload = await reader.readexactly(payload_len)
        logging.info("payload > %s", payload)

        
        decoded = bytes(
            payload[i] ^ mask[i % 4] for i in range(payload_len)
        )

        return decoded.decode("utf-8", errors="ignore")

    async def _pong_frame(self, reader: asyncio.StreamReader):
        second_byte = await reader.readexactly(1)
        logging.info("pong_frame > %s", second_byte)

    async def _ping_frame(self, writer: asyncio.StreamWriter):
        try:
            while True:
                await asyncio.sleep(10)

                logging.info("send ping frame")
                ping_code = b'\x89\x00'
                writer.write(ping_code)
                await writer.drain()
        except asyncio.CancelledError:
            logging.error("ping_frame error")

    async def close_handshake(self, writer: asyncio.StreamWriter):

        self.connections.remove(writer)
        writer.close()
        await writer.wait_closed()

        return None

    async def accept_handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        logging.info("new connection from > %s", writer.get_extra_info('peername'))

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

        self.connections.add(Endpoint(writer.get_extra_info('peername'), writer, reader, 99))

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from websocket.asyncwebsocket import Websocket
import asyncio
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    ws = Websocket(["127.0.0.1", 80])
    @ws
    async def ws_loop(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        await ws_loop.accept_handshake(reader, writer)

        try:
            while True:
                msg = await ws_loop.recv_frame(reader, writer)
                if msg is not None:
                    print(f"Received > {msg}")

                    await ws_loop.send_frame(writer, msg)

        finally:
            print("something went wrong")
    
    asyncio.run(ws.start())

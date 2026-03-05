# Websocket

## Description
This is a learning project to better understand how the websocket protocol works. The websocket is writen in pure python without any third party dependencies. It is not the projects intention to provide a feature complete websocket implementation.

## Capabilities
* accept handshake to establish a connection
* receive text from client
* send text to client
* send broadcast message to all clients
* disconnect client
* send ping

## Not working
* send only work with a payload length of 125
* binary not implemented
* receive pong

## Example
Receive messages from client and broadcast it to all connected clients
```python
if __name__ == "__main__":
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
```

"""Server-Sent Events helper for progress streaming."""

import asyncio
import json


class SseEvent:
    def __init__(self, event, data):
        self.event = event
        self.data = data

    def format(self):
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class SseEmitter:
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def create_stream(self, stream_id):
        self._queues[stream_id] = asyncio.Queue()
        return self

    async def emit(self, stream_id, event, data):
        if stream_id in self._queues:
            await self._queues[stream_id].put(SseEvent(event, data))

    async def stream(self, stream_id):
        if stream_id not in self._queues:
            raise ValueError(f"Stream {stream_id} not registered")
        queue = self._queues[stream_id]
        try:
            while True:
                event = await queue.get()
                yield event.format()
        except asyncio.CancelledError:
            pass
        finally:
            self._queues.pop(stream_id, None)


sse_emitter = SseEmitter()

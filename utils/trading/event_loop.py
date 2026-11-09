import asyncio

ib_event_loop = asyncio.new_event_loop()
asyncio.set_event_loop(ib_event_loop)

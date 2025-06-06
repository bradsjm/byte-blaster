"""ByteBlaster - Python implementation of the EMWIN ByteBlaster protocol.

This package provides a client for connecting to ByteBlaster servers and receiving
EMWIN (Emergency Managers Weather Information Network) data using the Quick Block
Transfer protocol.

Example usage:
    ```python
    import asyncio
    from byte_blaster import ByteBlasterClient

    async def handle_data(segment):
        print(f"Received: {segment.filename} block {segment.block_number}")

    async def main():
        client = ByteBlasterClient("user@example.com")
        client.subscribe(handle_data)
        await client.start()

    asyncio.run(main())
    ```
"""

from byte_blaster.client import ByteBlasterClient
from byte_blaster.protocol.models import (
    ByteBlasterServerList,
    QuickBlockTransferSegment,
)
from byte_blaster.server.manager import ServerListManager

__version__ = "1.0.0"
__author__ = "ByteBlaster Python Team"
__email__ = "support@example.com"

__all__ = [
    "ByteBlasterClient",
    "ByteBlasterServerList",
    "QuickBlockTransferSegment",
    "ServerListManager",
]

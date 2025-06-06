"""ByteBlaster protocol package.

This package contains the core protocol implementation for the ByteBlaster
EMWIN (Emergency Managers Weather Information Network) client, including
protocol decoding, authentication, and data models.
"""

from byte_blaster.protocol.auth import AuthenticationHandler
from byte_blaster.protocol.decoder import ProtocolDecoder
from byte_blaster.protocol.models import (
    ByteBlasterServerList,
    DataBlockFrame,
    ProtocolFrame,
    QuickBlockTransferSegment,
    ServerListFrame,
)

__all__ = [
    "AuthenticationHandler",
    "ByteBlasterServerList",
    "DataBlockFrame",
    "ProtocolDecoder",
    "ProtocolFrame",
    "QuickBlockTransferSegment",
    "ServerListFrame",
]

"""ByteBlaster protocol package.

This package contains the core protocol implementation for the ByteBlaster
EMWIN (Emergency Managers Weather Information Network) client, including
protocol decoding, authentication, and data models.
"""

from .auth import AuthenticationHandler
from .decoder import ProtocolDecoder
from .models import (
    ByteBlasterServerList,
    DataBlockFrame,
    ProtocolFrame,
    QBTSegment,
    ServerListFrame,
)

__all__ = [
    "AuthenticationHandler",
    "ByteBlasterServerList",
    "DataBlockFrame",
    "ProtocolDecoder",
    "ProtocolFrame",
    "QBTSegment",
    "ServerListFrame",
]

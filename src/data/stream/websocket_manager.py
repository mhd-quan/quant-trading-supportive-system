"""Generic WebSocket manager with reconnection logic."""

import asyncio
import json
from typing import Optional, Callable, Dict, Any
from abc import ABC, abstractmethod
import random
import websockets
from loguru import logger


class WebSocketManager(ABC):
    """Base WebSocket manager with auto-reconnection."""

    def __init__(
        self,
        url: str,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        max_reconnect_delay: int = 300,
    ):
        """Initialize WebSocket manager.

        Args:
            url: WebSocket URL
            ping_interval: Ping interval in seconds
            ping_timeout: Ping timeout in seconds
            max_reconnect_delay: Maximum reconnection delay in seconds
        """
        self.url = url
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.max_reconnect_delay = max_reconnect_delay
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.callbacks: Dict[str, Callable] = {}
        self._reconnect_delay = 1

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        try:
            self.ws = await websockets.connect(
                self.url,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
            )
            self.connected = True
            self._reconnect_delay = 1
            logger.info(f"Connected to WebSocket: {self.url}")
            await self.on_connect()
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.connected = False
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("WebSocket disconnected")

    async def reconnect_with_backoff(self) -> None:
        """Reconnect with exponential backoff."""
        while not self.connected:
            try:
                logger.info(f"Attempting reconnection (delay: {self._reconnect_delay}s)")
                await self.connect()
                self._reconnect_delay = 1
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                jitter = random.uniform(0, self._reconnect_delay * 0.1)
                await asyncio.sleep(self._reconnect_delay + jitter)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self.max_reconnect_delay
                )

    async def send(self, message: Dict[str, Any]) -> None:
        """Send message to WebSocket.

        Args:
            message: Message dictionary to send
        """
        if not self.ws or not self.connected:
            raise ConnectionError("WebSocket not connected")

        try:
            await self.ws.send(json.dumps(message))
            logger.debug(f"Sent message: {message}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def receive_loop(self) -> None:
        """Main receive loop with auto-reconnection."""
        while True:
            try:
                if not self.connected:
                    await self.reconnect_with_backoff()

                async for message in self.ws:
                    try:
                        data = json.loads(message)
                        await self.on_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                    except Exception as e:
                        logger.error(f"Message processing error: {e}")

            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed, reconnecting...")
                self.connected = False
                await self.reconnect_with_backoff()
            except Exception as e:
                logger.error(f"Receive loop error: {e}")
                self.connected = False
                await asyncio.sleep(1)

    def register_callback(self, event_type: str, callback: Callable) -> None:
        """Register callback for event type.

        Args:
            event_type: Event type identifier
            callback: Callback function
        """
        self.callbacks[event_type] = callback
        logger.debug(f"Registered callback for {event_type}")

    @abstractmethod
    async def on_connect(self) -> None:
        """Called after successful connection."""
        pass

    @abstractmethod
    async def on_message(self, data: Dict[str, Any]) -> None:
        """Called when message is received.

        Args:
            data: Parsed message data
        """
        pass

    @abstractmethod
    async def subscribe(self, channels: list) -> None:
        """Subscribe to channels.

        Args:
            channels: List of channels to subscribe
        """
        pass

    async def __aenter__(self) -> "WebSocketManager":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

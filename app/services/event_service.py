import json
import logging
import queue

logger = logging.getLogger(__name__)


class EventBus:
    """A simple publish/subscribe system for Server-Sent Events"""

    def __init__(self):
        self.subscribers = []

    def subscribe(self):
        """Register a new client (browser tab)"""
        q = queue.Queue(maxsize=50)
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        """Remove a client"""
        if q in self.subscribers:
            self.subscribers.remove(q)

    def emit(self, event_type, data):
        """Publish an event to all connected clients"""
        msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        # Use a copy of the list to allow modification during iteration
        for q in self.subscribers[:]:
            try:
                # If client is slow, we drop the MESSAGE, not the client.
                # This prevents "zombie" connections.
                q.put_nowait(msg)
            except queue.Full:
                # OPTIONAL: Log warning here if needed
                logger.warning("Event bus queue full, dropping message for slow client")
                pass
            except Exception:
                # Only unsubscribe on fatal errors (e.g. queue closed)
                self.unsubscribe(q)

        try:
            from app.extensions import socketio

            socketio.emit(event_type, data)
        except Exception as exc:
            logger.debug("SocketIO emit skipped: %s", exc)


# Global Instance
bus = EventBus()

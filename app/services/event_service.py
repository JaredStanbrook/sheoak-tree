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
        # SSE Format: "event: name\ndata: json\n\n"
        msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        for q in self.subscribers[:]:
            try:
                q.put_nowait(msg)
            except queue.Full:
                # If a client is too slow, we drop them to protect the server
                self.unsubscribe(q)
            except Exception:
                self.unsubscribe(q)


# Global Instance
bus = EventBus()

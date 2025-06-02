import logging
from collections import deque
class BufferedLogHandler(logging.Handler):
    def __init__(self, max_buffer=1000):
        super().__init__()
        self.log_buffer = deque(maxlen=max_buffer)
        self.last_processed_index = 0
    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_buffer.append(msg)
        except Exception:
            self.handleError(record)
    def get_new_logs(self):
        """Get unprocessed log lines and update counter"""
        if len(self.log_buffer) <= self.last_processed_index:
            return []
        new_logs = list(self.log_buffer)[self.last_processed_index:]
        self.last_processed_index = len(self.log_buffer)
        return new_logs
    def clear(self):
        self.log_buffer.clear()
        self.last_processed_index = 0

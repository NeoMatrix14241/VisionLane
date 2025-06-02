import logging
import weakref
class SafeLogHandler(logging.Handler):
    def __init__(self, widget=None):
        super().__init__()
        self._widget_ref = weakref.ref(widget) if widget else None
        self._recursion_prevention = False
    def emit(self, record):
        if self._recursion_prevention:
            return
        try:
            self._recursion_prevention = True
            msg = self.format(record)
            # Get widget safely
            widget = self._widget_ref() if self._widget_ref else None
            if widget and hasattr(widget, 'append'):
                try:
                    widget.append(msg)
                except RuntimeError:
                    # Widget was deleted, remove handler
                    logger = logging.getLogger()
                    logger.removeHandler(self)
        except Exception:
            self.handleError(record)
        finally:
            self._recursion_prevention = False
    def clear_widget(self):
        """Clear widget reference"""
        self._widget_ref = None

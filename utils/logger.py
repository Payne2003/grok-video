from loguru import logger

logger.add("logs/app.log")

class AppLogger:

    def __init__(self, callback=None):
        self.callback = callback

    def log(self, message):

        logger.info(message)

        if self.callback:
            self.callback(message)

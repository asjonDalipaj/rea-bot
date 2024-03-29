import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file, level=logging.INFO, max_size=10000000, backup_count=5):
    """Function to set up a logger with a specific name and logfile.

    Args:
    name (str): The name of the logger.
    log_file (str): The file name of the log file.
    level (int, optional): The logging level. Defaults to logging.INFO.
    max_size (int, optional): The maximum log file size in bytes before it is rotated. Defaults to 10 MB.
    backup_count (int, optional): The number of backup log files to keep. Defaults to 5.
    """
    
    # Create a RotatingFileHandler
    handler = RotatingFileHandler(log_file, maxBytes=max_size, backupCount=backup_count)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        logger.addHandler(handler)

    return logger
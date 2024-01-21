import logging

def setup_logger(name, log_file, level=logging.INFO):
    """Function to set up a logger with a specific name and logfile."""
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger
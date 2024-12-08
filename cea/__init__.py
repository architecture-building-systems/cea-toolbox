__version__ = "4.0.0-alpha.17"

class ConfigError(Exception):
    """Raised when the configuration of a tool contains some invalid values."""
    rc = 100  # sys.exit(rc)


class CustomDatabaseNotFound(Exception):
    """Raised when the InputLocator can't find a user-provided database (region=='custom')"""
    rc = 101  # sys.exit(rc)


class ScriptNotFoundException(Exception):
    """Raised when an invalid script name is used."""
    rc = 102  # sys.exit(rc)


class MissingInputDataException(Exception):
    """Raised when a script can't run because some information is missing"""
    rc = 103


class InvalidOccupancyNameException(Exception):
    """Raised when the occupancy.dbf has an invalid / unknown occupancy column"""
    rc = 104


def suppress_3rd_party_debug_loggers():
    """set logging level to WARN for fiona and shapely and others"""
    import logging
    loggers_to_silence = ["shapely", "Fiona", "fiona", "matplotlib", "urllib3.connectionpool",
                          "numba.core.ssa"]
    for log_name in loggers_to_silence:
        log = logging.getLogger(log_name)
        log.setLevel(logging.ERROR)

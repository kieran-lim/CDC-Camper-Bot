import logging
import os
import sys

from src.utils.common import utils

# Define standard format for log messages: timestamp, log level, and message
FORMATTER = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# Default configuration for the logging system
DEFAULT_CONFIG = {
    "log_level": 1,  # Log level mapping: 1=DEBUG, 2=INFO, 3=WARN, 4=ERROR
    "print_log_to_output": True,  # Whether to print logs to console
    "write_log_to_file": True,    # Whether to write logs to file
    "clear_logs_init": False,     # Whether to clear log directory on initialization
    "appends_stack_call_to_log": True,  # Whether to include stack trace in logs
    "save_solved_captchas": False,  # Whether to save solved captcha images
    "send_logs_to_discord": False,  # Whether to send logs to Discord
    "discord_log_level": 2        # Minimum level to send to Discord: 1=DEBUG, 2=INFO, 3=WARN, 4=ERROR
}


class Log:
    """
    Custom logger class that wraps Python's built-in logging functionality.
    
    This class provides configurable logging with options for:
    - Console and/or file output
    - Different log levels
    - Stack trace inclusion for debugging
    - Conditional logging
    - Discord integration
    """

    def __init__(self, directory: str, name: str = "cdc-helper", config: dict = DEFAULT_CONFIG):
        """
        Initialize the logger with specified configuration.
        
        Args:
            directory (str): Directory where log files will be stored
            name (str): Name of the logger (defaults to "cdc-helper")
            config (dict): Configuration options for the logger
        """
        log = logging.getLogger(name)

        self.logger = log  # Store logger instance
        self.name = name   # Store logger name
        self.directory = directory  # Store log directory path
        # Merge provided config with defaults to ensure all settings exist
        self.config = utils.init_config_with_default(config, DEFAULT_CONFIG)
        self.prefix = ""   # Initialize empty prefix for log messages
        self.discord_notification_manager = None  # Will be set later if Discord is enabled

        # Create log directory if it doesn't exist
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Clear log directory if configured to do so
        if self.config["clear_logs_init"]:
            utils.clear_directory(directory=self.directory, log=self.logger)

        # Set up console logging if enabled
        if self.config["print_log_to_output"]:
            terminal_output = logging.StreamHandler(sys.stdout)
            terminal_output.setFormatter(FORMATTER)
            log.addHandler(terminal_output)

        # Set up file logging if enabled
        if self.config["write_log_to_file"]:
            # Create timestamped log filename
            file_output = logging.FileHandler(
                os.path.join(directory, f"tracker_{utils.get_datetime_now('yyyymmdd-hhmmss')}.log"))
            file_output.setFormatter(FORMATTER)
            log.addHandler(file_output)

        # Create directory for solved captchas if enabled
        if self.config["save_solved_captchas"]:
            if not os.path.exists("solved_captchas"):
                os.makedirs("solved_captchas")

        # Set the log level based on configuration (multiplied by 10 to match Python's logging levels)
        # DEBUG=10, INFO=20, WARNING=30, ERROR=40
        log.setLevel(int(self.config["log_level"]) * 10)
        
    def set_notification_manager(self, notification_manager):
        """
        Set the notification manager for sending logs to Discord
        
        Args:
            notification_manager: The notification manager instance
        """
        self.discord_notification_manager = notification_manager

    def set_prefix(self, prefix: str):
        """
        Set a prefix to be prepended to all log messages.
        Useful for identifying messages from different accounts.
        
        Args:
            prefix (str): The prefix to add to log messages
        """
        self.prefix = prefix

    def append_stack_if(self, log_type, *output):
        """
        Internal helper method that includes stack trace information if configured.
        
        Args:
            log_type: The logging function to use (info, debug, etc.)
            *output: Variable arguments to be logged
        """
        # Add prefix to message if one is set
        prefixed_output = [f"{self.prefix}{utils.concat_tuple(output)}"] if self.prefix else output
        message = utils.concat_tuple(prefixed_output)
        
        if self.config["appends_stack_call_to_log"]:
            # Add decorative separators around the log message with stack trace
            log_type("=======================================================================================")
            log_type(*prefixed_output, stack_info=True)  # Include stack trace
            log_type("\n=======================================================================================\n")
        else:
            # Simply log the message without stack trace
            log_type(message)
            
        # Send to Discord if enabled (determine log level from the function name)
        if self.discord_notification_manager:
            # Get the log level from the function name (info, error, etc.)
            level_map = {
                self.logger.debug: 1,
                self.logger.info: 2,
                self.logger.warning: 3,
                self.logger.error: 4,
            }
            level_name = log_type.__name__.upper()
            level_value = level_map.get(log_type, 2)  # Default to INFO if unknown
            
            # Only send if the log level meets the threshold for Discord logs
            if level_value >= self.config.get("discord_log_level", 2):
                self.discord_notification_manager.send_log_to_discord(level_name, message)

    def info(self, *output):
        """Log message at INFO level with optional stack trace."""
        self.append_stack_if(self.logger.info, *output)

    def debug(self, *output):
        """Log message at DEBUG level with optional stack trace."""
        self.append_stack_if(self.logger.debug, *output)

    def error(self, *output):
        """Log message at ERROR level with optional stack trace."""
        self.append_stack_if(self.logger.error, *output)

    def warning(self, *output):
        """Log message at WARNING level with optional stack trace."""
        self.append_stack_if(self.logger.warning, *output)

    # Conditional logging methods - only log if condition is True

    def info_if(self, condition: bool, *output):
        """
        Conditionally log at INFO level if condition is True.
        
        Args:
            condition (bool): Whether to log the message
            *output: Message(s) to log
        """
        if condition:
            self.info(*output)

    def debug_if(self, condition: bool, *output):
        """
        Conditionally log at DEBUG level if condition is True.
        
        Args:
            condition (bool): Whether to log the message
            *output: Message(s) to log
        """
        if condition:
            self.debug(*output)

    def error_if(self, condition: bool, *output):
        """
        Conditionally log at ERROR level if condition is True.
        
        Args:
            condition (bool): Whether to log the message
            *output: Message(s) to log
        """
        if condition:
            self.error(*output)

    def warning_if(self, condition: bool, *output):
        """
        Conditionally log at WARNING level if condition is True.
        
        Args:
            condition (bool): Whether to log the message
            *output: Message(s) to log
        """
        if condition:
            self.warning(*output)

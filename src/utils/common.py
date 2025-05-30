# Contains common utility functions for Selenium and general tasks.

class selenium_common:
    # Imports for Selenium WebDriver and utilities.
    import selenium
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.alert import Alert

    # Waits for a web element to be present on the page.
    # 'driver': The Selenium WebDriver instance.
    # 'locator_type': The type of locator (e.g., By.ID, By.XPATH).
    # 'locator': The locator string.
    # 'timeout': Maximum time to wait for the element.
    # Returns the WebElement if found, otherwise raises TimeoutException.
    def wait_for_elem(driver: selenium.webdriver, locator_type: str, locator: str, timeout: int = 5):
        return selenium_common.WebDriverWait(driver, timeout).until(
            selenium_common.EC.presence_of_element_located((locator_type, locator)))

    # Checks if a web element is present on the page within a given timeout.
    # Returns the WebElement if present, False otherwise.
    def is_elem_present(driver: selenium.webdriver, locator_type: str, locator: str, timeout: int = 2):
        try:
            return selenium_common.wait_for_elem(driver, locator_type, locator, timeout)
        except selenium_common.TimeoutException:
            return False # Element not found within timeout.

    # Attempts to dismiss a JavaScript alert present on the page.
    # 'timeout': Time to wait for the alert to be present.
    # Returns a tuple: (bool: True if alert was dismissed, False otherwise, str: alert text or error message).
    def dismiss_alert(driver: selenium.webdriver, timeout: int = 2):
        alert_txt = ""
        try:
            # Wait for an alert to be present.
            selenium_common.WebDriverWait(driver, timeout).until(selenium_common.EC.alert_is_present())
            alert = Alert(driver) # Switch to the alert.
            if alert:
                alert_txt = alert.text # Get alert text.
                alert.accept() # Dismiss the alert.

        except Exception as e: # Catches TimeoutException if no alert, or other errors.
            return False, str(e)
        else:
            return True, alert_txt # Alert dismissed successfully.


class utils:
    # Imports for file operations, YAML parsing, and datetime handling.
    import shutil, os, yaml
    from datetime import date, datetime

    # A simple default logger class if no logger is provided to utility functions.
    class DEFAULT_LOG:
        def info(*args):
            print("[INFO]", utils.concat_tuple(args))

        def debug(*args):
            print("[DEBUG]", utils.concat_tuple(args))

        def error(*args):
            print("[ERROR]", utils.concat_tuple(args))

        def warn(*args):
            print("[WARN]", utils.concat_tuple(args))

    # --- LOAD YAML FILE ---
    # Loads configuration from a YAML file.
    # 'file_path': Path to the YAML file.
    # 'log': Logger instance for error reporting.
    # Returns a dictionary with the loaded configuration.
    def load_config_from_yaml_file(file_path: str, log=DEFAULT_LOG):
        if not utils.os.path.isfile(file_path):
            raise Exception(f"No file found at {file_path}")
        with open(file_path) as stream:
            config = {}
            try:
                config = utils.yaml.safe_load(stream) # Securely load YAML.
            except utils.yaml.YAMLError as exception:
                log.error(exception)
            return config

    # Initializes a configuration dictionary with default values if keys are missing.
    # This function seems to have a bug: `enumerate(default_config)` will iterate over keys if `default_config` is a dict,
    # and `configValue` will be the index, not the value. It should likely be `default_config.items()`.
    # Also, `configType` is a confusing name for the key from `default_config`.
    def init_config_with_default(config: dict, default_config: dict):
        for default_key, default_value in default_config.items(): # Corrected iteration
            if not utils.check_key_existence_in_dict(config, default_key):
                config[default_key] = default_value # Assign default value if key is missing
        return config

    # Checks if a specific key-value pair exists in a dictionary.
    def check_key_value_pair_exist_in_dict(dic, key, value):
        try:
            return dic[key] == value
        except KeyError:
            return False # Key not found.

    # Checks if a key exists in a dictionary.
    def check_key_existence_in_dict(dic, key):
        try:
            _ = dic[key]
            return True
        except KeyError:
            return False # Key not found.

    # Concatenates elements of a tuple into a space-separated string.
    def concat_tuple(ouput_tuple):
        result = ""
        for m in ouput_tuple:
            result += str(m) + ' '

        return result.strip() # Added strip() to remove trailing space.

    # Clears all files and subdirectories within a given directory.
    # 'directory': Path to the directory to clear.
    # 'log': Logger instance.
    def clear_directory(directory: str, log=DEFAULT_LOG):
        if not utils.os.path.isdir(directory):
            return log.error(f"Directory: {utils.os.path.join(utils.os.getcwd(), directory)} does not exist.")

        for filename in utils.os.listdir(directory):
            file_path = utils.os.path.join(directory, filename)

            try:
                if utils.os.path.isfile(file_path) or utils.os.path.islink(file_path):
                    utils.os.unlink(file_path) # Remove file or link.
                elif utils.os.path.isdir(file_path):
                    utils.shutil.rmtree(file_path) # Remove directory and its contents.
            except Exception as e:
                log.error("Failed to delete %s. Reason: %s" % (file_path, e))

    # Removes a list of specified files.
    # 'files': A list of file paths to remove.
    # 'log': Logger instance.
    def remove_files(files: list, log=DEFAULT_LOG):
        for file in files:
            if utils.os.path.exists(file):
                try:
                    utils.os.remove(file)
                except Exception as e:
                    log.error("Failed to delete %s. Reason %s" % (str(file), e))

    # Dictionary mapping common date format options to strftime format codes.
    date_formatter = {
        "dd/mm/yyyy": "%d/%m/%Y",
        "dd-mm-yyyy": "%d-%m-%Y",
        "ddmmyyyy": "%d%m%Y",
        "mm/dd/yyyy": "%m/%d/%y", # Note: %y is 2-digit year, %Y is 4-digit.
        "mm dd, yyyy": "%B %d, %Y",
        "mm-dd-yyyy": "%b-%d-%Y",

        "dd/mm/yyyy hh:mm:ss": "%d/%m/%Y %H:%M:%S",
        "dd-mm-yyyy hh:mm:ss": "%d-%m-%Y %H:%M:%S",
        "dd-mm-yyyy hhmmss": "%d-%m-%Y %H%M%S",
        "dd-mm-yyyy hhmm": "%d-%m-%Y %H%M",
        "ddmmyyyy hhmmss": "%d%m%Y %H%M%S",
        "yyyymmdd-hhmmss": "%Y%m%d-%H%M%S",
    }

    # Retrieves a strftime format string based on a format option.
    # 'format_option': Key for the desired format in 'date_formatter'.
    # 'default_format_option': Fallback format option if the primary one isn't found.
    def get_date_formatter(format_option, default_format_option):
        return utils.date_formatter.get(format_option, utils.date_formatter[default_format_option]) # Use .get() for safer access.

    # Gets the current date formatted as a string.
    # 'format_option': Desired date format key.
    def get_date_now(format_option: str = "dd-mm-yyyy"):
        date_format = utils.get_date_formatter(format_option, "dd-mm-yyyy")
        today = utils.date.today()
        return today.strftime(date_format)

    # Gets the current datetime formatted as a string.
    # 'format_option': Desired datetime format key.
    def get_datetime_now(format_option: str = "ddmmyyyy hhmmss"):
        datetime_format = utils.get_date_formatter(format_option, "ddmmyyyy hhmmss")
        now = utils.datetime.now()
        return now.strftime(datetime_format)

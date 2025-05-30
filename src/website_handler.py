import datetime
import os
import random
import re
import sys
import time
from typing import Dict, Union, Tuple, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService  # Renamed to avoid conflict
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.alert import Alert
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager

from abstracts.cdc_abstract import CDCAbstract, Types
from src.utils.common import selenium_common
import requests
import json
import logging





# ---------------------------- HELPER FUNCTIONS ----------------------------

# Converts date and time strings to a datetime object.
# Handles optional time string.
def convert_to_datetime(date_str: str, time_str: str = None):
    if time_str:
        time_str = time_str.split(' ')[0]
        return datetime.datetime.strptime(f'{date_str} | {time_str}', '%d/%b/%Y | %H:%M')
    else:
        return datetime.datetime.strptime(date_str, "%d/%b/%Y")
    
# Determine field type from lesson name
def determine_field_type(lesson_name: str):
    # Practical Test detection
    if "PT" in lesson_name:
        return Types.PT
    
    # Default all other lessons to PRACTICAL
    # This assumes anything not explicitly a PT is a practical lesson
    return Types.PRACTICAL

# Function to parse date string in DD/MM/YYYY format
def parse_date_string(date_str: str):
    """Convert DD/MM/YYYY string to datetime.date object"""
    try:
        return datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        # Try CDC's format if the first format fails
        return datetime.datetime.strptime(date_str, "%d/%b/%Y").date()


# Function to parse time string in HH:MM format
def parse_time_string(time_str: str):
    """Convert HH:MM string to datetime.time object"""
    return datetime.datetime.strptime(time_str, "%H:%M").time()

# --------------------------------------------------------------------------






# MAIN CLASS FOR HANDLING INTERACTIONS WITH THE CDC WEBSITE (INHERITS FROM CDCABSTRACT)
class handler(CDCAbstract):
    def initialize_driver(self):
        """Initialize and configure the undetected_chromedriver with optimized anti-detection settings."""
        
        headless = self.browser_config.get("headless_mode", False)
        if headless:
            self.log.warning("Profile persistence is generally more effective in non-headless mode, especially for initial Cloudflare challenges.")

        max_retries = 3
        retry_delay = 5 # seconds
        last_exception = None

        # Define profile path (e.g., in the workspace root)
        profile_path = os.path.join(os.getcwd(), "chrome_profile")
        self.log.info(f"Using Chrome profile path: {profile_path}")

        for attempt in range(max_retries):
            try:
                self.log.info(f"Initializing ChromeDriver (attempt {attempt + 1}/{max_retries})")
                
                options = uc.ChromeOptions()
                options.add_argument(f"--user-data-dir={profile_path}")
                
                # Add all the necessary options
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--start-maximized')
                options.add_argument(f"--window-size=1920,1080")
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--disable-infobars')
                options.add_argument('--disable-popup-blocking')
                options.add_argument('--disable-notifications')
                options.add_argument('--disable-extensions')
                
                if headless:
                    options.add_argument('--headless=new')

                # Get Chrome version from config or detect automatically
                chrome_version = self.browser_config.get("chrome_version")
                if not chrome_version:
                    try:
                        import subprocess
                        if self.platform == "win":
                            cmd = 'reg query "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon" /v version'
                            output = subprocess.check_output(cmd, shell=True).decode()
                            chrome_version = int(output.split()[-1].split('.')[0])
                        else:
                            cmd = '/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --version'
                            output = subprocess.check_output(cmd, shell=True).decode()
                            chrome_version = int(output.split()[2].split('.')[0])
                    except Exception as e:
                        self.log.warning(f"Failed to detect Chrome version: {e}")
                        chrome_version = 136  # Fallback to a known working version

                driver = uc.Chrome(
                    options=options,
                    version_main=chrome_version,
                    headless=headless,
                    use_subprocess=True
                )
                
                # Sanity check: try to load a simple page
                try:
                    self.log.info("Attempting to load example.com for sanity check...")
                    driver.get("https://www.example.com")
                    if "Example Domain" in driver.title:
                        self.log.info("Successfully loaded example.com.")
                    else:
                        self.log.warning(f"Failed to load example.com correctly. Title: {driver.title}")
                except Exception as ex_err:
                    self.log.warning(f"Error during example.com sanity check: {ex_err}")

                driver.set_page_load_timeout(60)
                driver.implicitly_wait(10)
                
                # Add anti-detection scripts
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                          get: () => undefined
                        });
                        Object.defineProperty(navigator, 'languages', {
                          get: () => ['en-US', 'en']
                        });
                        Object.defineProperty(navigator, 'plugins', {
                          get: () => [1, 2, 3, 4, 5]
                        });
                    """
                })
                self.log.info("ChromeDriver initialized successfully.")
                return driver
            except Exception as e:
                last_exception = e
                self.log.warning(f"ChromeDriver initialization attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    self.log.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    self.log.error("All ChromeDriver initialization attempts failed.")
                    raise last_exception

        if last_exception:
            raise last_exception
        else:
            raise Exception("Unknown error during Chromedriver initialization after retries")

    # ---------- INITIALIZES THE HANDLER WITH CONFIGURATIONS AND DEPENDENCIES ----------
    def __init__(self, login_credentials, captcha_solver, log, notification_manager, browser_config, program_config, account_name="default", full_config=None):
        # browser_type = "chrome" # This is implicit with undetected_chromedriver

        # if browser_type.lower() != "chrome": # This check is no longer needed
        #     raise ValueError("Only Chrome browser is supported")

        self.home_url = "https://www.cdc.com.sg"
        self.booking_url = "https://bookingportal.cdc.com.sg:"
        self.port = "" # Port for the booking portal, dynamically determined after login.

        self.captcha_solver = captcha_solver
        self.log = log
        self.notification_manager = notification_manager
        self.account_name = account_name
        self.full_config = full_config or {}  # Store the full config for account-specific settings

        self.browser_config = browser_config # Keep for headless_mode access
        self.program_config = program_config

        # Program behavior flags.
        self.auto_reserve = program_config["auto_reserve"]
        self.auto_restart = program_config["auto_restart"]
        self.reserve_for_same_day = program_config["reserve_for_same_day"]

        # User credentials.
        self.username = login_credentials["username"]
        self.password = login_credentials["password"]
        self.logged_in = False # Tracks login status.
        self.notification_update_msg = "" # Stores messages for notifications.
        self.has_slots_reserved = False # Tracks if any slots are currently reserved by the bot.

        # Detect platform (can be useful for other things, not directly for driver path with webdriver_manager)
        import platform
        self.platform = "win" if platform.system().lower() == "windows" else "osx"

        # Maps session types to their respective booking page opening functions.
        self.opening_booking_page_callback_map = {
            Types.PRACTICAL: self.open_practical_lessons_booking_page,
            Types.PT: self.open_practical_test_booking_page,
        }

        # Cache for common selectors to reduce DOM queries
        self.selectors_cache = {}
        
        # Initialize the driver using the new method
        try:
            self.driver = self.initialize_driver()
            self.log.info("Waiting a few seconds after driver initialization before first page load...")
            time.sleep(3) # Small delay before first interaction
        except Exception as e:
            self.log.error(f"Failed to initialize WebDriver: {e}")
            raise

        # Set browser window size (already handled by --start-maximized or specific window size in options)
        # self.driver.set_window_rect(width=1200, height=768) # Can be removed if --start-maximized is used

        self.flaresolverr_config = full_config.get("flaresolverr_config", {}) # Added for FlareSolverr

        # Monitored types for this specific account
        self.monitored_types = login_credentials.get("monitored_types", {})

        super().__init__(username=self.username, password=self.password, headless=self.browser_config.get("headless_mode", False))

        # Get cookies from FlareSolverr and add them to the driver
        try:
            cookies = self.get_flaresolverr_cookies()
            if cookies:
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
                self.log.info("Successfully added FlareSolverr cookies to driver")
            else:
                self.log.warning("No cookies received from FlareSolverr")
        except Exception as e:
            self.log.error(f"Error getting FlareSolverr cookies: {str(e)}")
            raise



    # Context manager entry point.
    def __enter__(self):
        return self

    # Context manager exit point, ensures driver is closed.
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure proper cleanup of resources when the handler is closed."""
        try:
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    self.log.error(f"Error while closing driver: {e}")
                finally:
                    self.driver = None
        except Exception as e:
            self.log.error(f"Error in cleanup: {e}")
        finally:
            # Reset state
            self.reset_state()
        
        # Don't suppress exceptions
        return False

    # Opens a specific path on the booking portal.
    def _open_index(self, path: str, sleep_delay=None):
        self.driver.get(f"{self.booking_url}{self.port}/{path}")
        if sleep_delay:
            time.sleep(sleep_delay) # Optional delay after page load.

    # String representation of the handler object.
    def __str__(self):
        return super().__str__()

    # Resets the state of the handler for a new check cycle.
    def reset_state(self):
        self.reset_attributes_for_all_fieldtypes() # Resets data for all session types.
        self.notification_update_msg = ""
        self.has_slots_reserved = False

    # Checks if a specific date is currently visible in the booking calendar for a given session type.
    def is_date_in_view(self, date_str: str, field_type: str):
        return date_str in self.get_attribute_with_fieldtype("days_in_view", field_type)

    # Gets the earliest available time slots from the provided sessions data.
    # 'length' specifies the number of earliest slots to retrieve.
    # 'field_type' is used to adjust step for simulator lessons (no back-to-back).
    def get_earliest_time_slots(self, sessions_data: Dict, length: int, field_type: str):
        # Flatten and sort all available date-time slots.
        sorted_datetimes = [(date_str, time_slot) for date_str, time_slots in sessions_data.items()
                            for time_slot in time_slots]
        sorted_datetimes.sort(key=lambda comp_date: convert_to_datetime(comp_date[0], comp_date[1]))

        return_sessions_data = {}
        # Simulator lessons cannot be back-to-back, so step is 2.
        step = 1 # Simplified as SIMULATOR is removed.

        # Select the earliest 'length' number of sessions.
        for i in range(0, min(length * step, len(sorted_datetimes)), step):
            selected_date_str, selected_time_slot = sorted_datetimes[i]

            if selected_date_str not in return_sessions_data:
                return_sessions_data[selected_date_str] = [selected_time_slot]
            else:
                return_sessions_data[selected_date_str].append(selected_time_slot)

        return return_sessions_data

    # Compares two sets of sessions to see if they are different.
    # Returns True if different, False if identical.
    def check_if_same_sessions(self, session0: Dict, session1: Dict):
        # Fast path: check if dictionaries have different keys
        if set(session0.keys()) != set(session1.keys()):
            return True
            
        # Compare values for each key
        for date_str, time_slots in session0.items():
            if set(time_slots) != set(session1.get(date_str, [])):
                return True
                
        # Dictionaries are identical
        return False

    # Checks recursion depth for page opening functions to prevent infinite loops.
    # If depth exceeds a threshold, logs out and logs back in.
    def check_call_depth(self, call_depth: int):
        if call_depth > 4: # Maximum recursion depth.
            self.account_logout()
            self.account_login()
            return False # Indicates login was re-attempted.

        return True

    # Checks if the user has access rights to a specific webpage.
    # Detects "Alert.aspx" in URL, which indicates restricted access.
    def check_access_rights(self, webpage: str):
        if "Alert.aspx" in self.driver.current_url:
            self.log.info(f"You do not have access to {webpage}.")
            return False

        return True

    # Ensures the user is still logged in by navigating to a known page.
    # If timed out, logs out and logs back in.
    def check_logged_in(self):
        self._open_index("NewPortal/Booking/StatementBooking.aspx") # Page that requires login.
        if self.port not in self.driver.current_url: # Check if the dynamic port is in the URL.
            self.log.info("User has been timed out! Now logging out and in again...")
            self.account_logout()
            self.account_login()
            time.sleep(0.5)

    # Handles the dismissal of the simpler "normal" CAPTCHA on some pages.
    # 'caller_identifier' is used for logging.
    # 'solve_captcha' determines if an attempt to solve it should be made.
    # 'force_enabled' can force captcha solving even if globally disabled.
    def dismiss_normal_captcha(self, caller_identifier: str, solve_captcha: bool = False,
                               secondary_alert_timeout: int = 5, force_enabled: bool = False):
        is_captcha_present = selenium_common.is_elem_present(self.driver, By.ID, "ctl00_ContentPlaceHolder1_CaptchaImg",
                                                             timeout=5)
        if not is_captcha_present:
            return True # No CAPTCHA present.

        if solve_captcha:
            success, _ = self.captcha_solver.solve(driver=self.driver, captcha_type="normal_captcha",
                                                   force_enable=force_enabled)
            if not success:
                return False # CAPTCHA solving failed.

            captcha_submit_btn = selenium_common.wait_for_elem(self.driver, By.ID, "ctl00_ContentPlaceHolder1_Button1")
            captcha_submit_btn.click()
        else:
            # If not solving, just try to close the CAPTCHA dialog.
            captcha_close_btn = selenium_common.wait_for_elem(self.driver, By.CLASS_NAME, "close")
            captcha_close_btn.click()

        # Dismiss any subsequent alerts (e.g., incorrect CAPTCHA).
        _, alert_text = selenium_common.dismiss_alert(driver=self.driver, timeout=2)
        if "incorrect captcha" in alert_text:
            selenium_common.dismiss_alert(driver=self.driver, timeout=secondary_alert_timeout) # Second alert.
            self.log.info(f"Normal captcha failed for opening {caller_identifier} page.")
            return False

        return True

    # Accepts terms and conditions if the checkbox and button are present.
    def accept_terms_and_conditions(self):
        terms_checkbox = selenium_common.is_elem_present(self.driver, By.ID,
                                                         "ctl00_ContentPlaceHolder1_chkTermsAndCond")
        agree_btn = selenium_common.is_elem_present(self.driver, By.ID, "ctl00_ContentPlaceHolder1_btnAgreeTerms")
        if terms_checkbox and agree_btn:
            terms_checkbox.click()
            agree_btn.click()

    # Retrieves course data (e.g., driving courses) from a dropdown menu.
    # 'course_element_id' can specify a custom dropdown ID.
    def get_course_data(self, course_element_id: Union[str, None] = None):
        # Default course dropdown ID.
        course_dropdown_id = course_element_id or "ctl00_ContentPlaceHolder1_ddlCourse"
        course = selenium_common.is_elem_present(self.driver, By.ID, course_dropdown_id)
        if not course:
            return False # Dropdown not found.

        course_selection = Select(course)
        number_of_options = len(course_selection.options)

        course_data = {"course_selection": course_selection, "available_courses": []}

        # Extract text from each option in the dropdown.
        for option_index in range(0, number_of_options):
            option = course_selection.options[option_index]
            course_data["available_courses"].append(str(option.text.strip()))

        return course_data

    # Selects a course from the dropdown by its name.
    def select_course_from_name(self, course_data: Dict, course_name: str):
        for selection_idx, current_course in enumerate(course_data["available_courses"]):
            if course_name in current_course:
                course_data["course_selection"].select_by_index(selection_idx)
                return selection_idx # Return the index of the selected course.

        return False # Course name not found.

    # Selects a course from the dropdown by its index.
    def select_course_from_idx(self, course_data: Dict, course_idx: int):
        if not (0 <= course_idx < len(course_data["available_courses"])):
            self.log.error(f"Course selected is out of range. {course_data['available_courses']}")
            return False # Index out of range.

        course_data["course_selection"].select_by_index(course_idx)
        return course_data["available_courses"][course_idx] # Return the name of the selected course.

    # Opens the CDC home page.
    def open_home_page(self, sleep_delay: Union[int, None] = None):
        self.log.info(f"Opening home page: {self.home_url}")

        flaresolverr_html = None
        flaresolverr_cookies = None

        if self.flaresolverr_config.get("enabled"):
            self.log.info(f"Attempting to fetch home page via FlareSolverr: {self.home_url}")
            response_tuple = self._fetch_with_flaresolverr(self.home_url)
            if response_tuple:
                flaresolverr_html, flaresolverr_cookies = response_tuple
            
            if flaresolverr_html:
                self.log.info("Successfully fetched home page with FlareSolverr.")
                if flaresolverr_cookies:
                    self.log.info(f"Adding {len(flaresolverr_cookies)} cookies from FlareSolverr to Selenium session.")
                    for cookie in flaresolverr_cookies:
                        # FlareSolverr cookie format might need adjustment for Selenium
                        # Common keys: name, value, domain, path, expiry, httpOnly, secure
                        # Selenium expects 'expiry' as an integer (timestamp)
                        # We might need to convert cookie['expires'] if it's a date string
                        selenium_cookie = {
                            'name': cookie.get('name'),
                            'value': cookie.get('value'),
                            'path': cookie.get('path', '/'),
                            'domain': cookie.get('domain'),
                            # Add other fields if present and compatible
                        }
                        # Selenium's add_cookie is sensitive to domain, ensure it's correct.
                        # It might be safer to navigate to the domain first if not already there,
                        # but for home_url, FlareSolverr should have used the correct domain.
                        if cookie.get('expiry'): # FlareSolverr might use 'expiry' or 'expires'
                             selenium_cookie['expiry'] = int(cookie['expiry'])
                        elif cookie.get('expires'): # Check common alternative
                            # Convert expires from string/float to int timestamp if necessary
                            # This part is tricky as 'expires' format can vary.
                            # For now, let's assume it's already a timestamp or can be cast.
                            try:
                                selenium_cookie['expiry'] = int(cookie['expires'])
                            except ValueError:
                                self.log.warning(f"Could not convert cookie expiry '{cookie['expires']}' to int for cookie '{cookie['name']}'. Skipping expiry.")
                        
                        if selenium_cookie['name'] and selenium_cookie['value'] and selenium_cookie['domain']:
                            try:
                                self.driver.add_cookie(selenium_cookie)
                            except Exception as e:
                                self.log.warning(f"Could not add cookie {selenium_cookie.get('name')} to Selenium: {e}")
                        else:
                            self.log.warning(f"Skipping cookie from FlareSolverr due to missing name, value, or domain: {cookie}")

        # Whether FlareSolverr was used or not, or if it failed, proceed to load with Selenium
        # If FlareSolverr succeeded, cookies are now in the session.
        self.driver.get(self.home_url)
        
        if not flaresolverr_html: # If FlareSolverr wasn't used or failed
            self.log.info("Pausing for 15 seconds (FlareSolverr not used or failed) for manual Cloudflare challenge resolution if it appears...")
            time.sleep(15)
        else:
            # If FlareSolverr was used, maybe a shorter delay or none if confident.
            self.log.info("Short pause after FlareSolverr-assisted page load.")
            time.sleep(2) 
        
        self.log.info(f"Current page title after loading home page: {self.driver.title}")
        self.log.info(f"Current page URL after loading home page: {self.driver.current_url}")

        if sleep_delay:
            time.sleep(sleep_delay)



    # ---------- HANDLES ACCOUNT LOGIN PROCESS ----------
    # Includes filling credentials, solving reCAPTCHA, and handling login alerts.
    def account_login(self, max_login_attempts=3, current_attempt=1):
        if current_attempt > max_login_attempts:
            self.log.error(f"Failed to login after {max_login_attempts} attempts.")
            return False
        
        self.log.info(f"Attempting login: {current_attempt}/{max_login_attempts}")

        try:
            self.open_home_page(sleep_delay=2)

            # Click the login prompt button
            login_link_text = "Learner's Login"
            try:
                prompt_login_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, login_link_text))
                )
                prompt_login_btn.click()
            except TimeoutException:
                self.log.error(f"Login prompt button (Link Text: '{login_link_text}') not clickable or not found.")
                if current_attempt < max_login_attempts:
                    time.sleep(5) 
                    return self.account_login(max_login_attempts, current_attempt + 1)
                return False
            
            # Wait for the login popup and username field
            try:
                learner_id_input = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.NAME, "userId"))
                )
            except TimeoutException:
                self.log.error("Login popup (userId field) did not appear.")
                if current_attempt < max_login_attempts:
                    time.sleep(5)
                    return self.account_login(max_login_attempts, current_attempt + 1)
                return False

            # Wait for password field
            try:
                password_input = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.NAME, "password"))
                )
            except TimeoutException:
                self.log.error("Password input field did not appear.")
                # No retry here, assume if username field appeared, password should too quickly.
                return False # Or retry: return self.account_login(max_login_attempts, current_attempt + 1)

            learner_id_input.send_keys(self.username)
            password_input.send_keys(self.password)

            # Solve reCAPTCHA v2
            captcha_solved, captcha_message = self.captcha_solver.solve(driver=self.driver, captcha_type="recaptcha_v2")
            if not captcha_solved:
                self.log.error(f"Failed to solve CAPTCHA: {captcha_message}")
                # self.notification_manager.send_error_log_to_discord(...) # Consider adding error reporting
                # Retry login if CAPTCHA fails and attempts remaining
                if current_attempt < max_login_attempts:
                    time.sleep(2) # Brief pause
                    return self.account_login(max_login_attempts, current_attempt + 1)
                return False
            
            # Click the final login button
            login_button_id = "BTNSERVICE2"
            try:
                login_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, login_button_id))
                )
                login_btn.click()
            except TimeoutException:
                self.log.error(f"Final login button (ID: {login_button_id}) not clickable or not found.")
                # Retry login if final button fails and attempts remaining
                if current_attempt < max_login_attempts:
                    time.sleep(2)
                    return self.account_login(max_login_attempts, current_attempt + 1)
                return False

            # Handle potential alerts after login attempt.
            # The selenium_common.dismiss_alert logic needs to be reviewed.
            # For now, let's assume it works or we add a try-except block around it.
            try:
                alert_present, alert_text = selenium_common.dismiss_alert(driver=self.driver, timeout=5)
                if alert_present and "complete the captcha" in alert_text.lower(): # Ensure case-insensitive check
                    self.log.info("Login alert: CAPTCHA verification failed according to website.")
                    # self.notification_manager.send_error_log_to_discord(...)
                    if current_attempt < max_login_attempts:
                        time.sleep(1)
                        # Explicitly do not logout/login here as it's part of the retry
                        return self.account_login(max_login_attempts, current_attempt + 1)
                    return False
                # Handle other alerts if necessary
            except Exception as alert_e:
                self.log.warning(f"Could not check for or dismiss alert: {alert_e}")
                # Decide if this is critical. For now, we continue to check URL.

            # Verify successful login by checking URL and extracting port
            if "NewPortal" in self.driver.current_url:
                url_digits = re.findall(r'\d+', self.driver.current_url)
                if len(url_digits) > 0:
                    self.port = str(url_digits[-1])
                    self.logged_in = True
                    self.log.info(f"Login successful for {self.account_name}.")
                    return True
                else:
                    self.log.error("Logged in, but failed to extract portal port from URL.")
                    # self.notification_manager.send_error_log_to_discord(...)
                    # No self.account_logout() here to avoid issues if already in a bad state, rely on __exit__.
                    if current_attempt < max_login_attempts:
                        return self.account_login(max_login_attempts, current_attempt + 1)
                    return False
            else:
                self.log.warning(f"Login may have failed. Current URL: {self.driver.current_url} does not contain 'NewPortal'.")
                # Potentially a silent failure or redirection to an unexpected page.
                if current_attempt < max_login_attempts:
                    return self.account_login(max_login_attempts, current_attempt + 1)
                return False
            
        except Exception as e:
            import traceback
            stack_trace = traceback.format_exc()
            self.log.error(f"Unexpected error during login (attempt {current_attempt}): {e}\n{stack_trace}")
            # self.notification_manager.send_error_log_to_discord(...)
            # If a truly unexpected error, maybe don't retry immediately, or have a different strategy.
            # For now, we let it fall through, and if it's inside a retry loop from main.py, that will handle it.
            return False



    # ---------- HANDLES ACCOUNT LOGOUT PROCESS ----------
    def account_logout(self):
        self._open_index("NewPortal/logOut.aspx?PageName=Logout")
        self.log.info("Logged out.")
        self.logged_in = False



    # ---------- OPENS DASHBOARD ----------
    def open_booking_overview(self):
        self.check_logged_in() # Ensure user is logged in.
        self._open_index("NewPortal/Booking/Dashboard.aspx")
        selenium_common.dismiss_alert(driver=self.driver, timeout=5) # Dismiss any pop-up alerts.



    # ---------- RETRIEVES CURRENTLY RESERVED LESSON DATE AND TIME FROM THE DASHBOARD ----------
    # Populates 'reserved_sessions' attribute.
    def get_reserved_lesson_date_time(self):
        rows = self.driver.find_elements(By.CSS_SELECTOR, "table#ctl00_ContentPlaceHolder1_gvReserved tr")

        for row in rows:
            td_cells = row.find_elements(By.TAG_NAME, "td")
            if len(td_cells) > 0: # Ensure row has data cells.
                lesson_name = td_cells[4].text # Lesson name from the 5th cell.

                # Use the helper function to determine field type
                field_type = determine_field_type(lesson_name)

                # Store the lesson name and session details if a valid type is identified.
                if field_type: # If a valid type is found
                    self.set_attribute_with_fieldtype("lesson_name", field_type, lesson_name)
                    reserved_sessions = self.get_attribute_with_fieldtype("reserved_sessions", field_type)

                    # Date from 1st cell, time from 3rd and 4th cells.
                    date_text = td_cells[0].text
                    time_text = f"{td_cells[2].text[:-3]} - {td_cells[3].text[:-3]}" # Format time range.

                    if date_text not in reserved_sessions:
                        reserved_sessions.update({date_text: [time_text]})
                    else:
                        reserved_sessions[date_text].append(time_text)



    # ---------- RETRIEVES BOOKED LESSON DATE AND TIME FROM THE DASHBOARD ----------
    # Populates 'booked_sessions' attribute.
    def get_booked_lesson_date_time(self):
        rows = self.driver.find_elements(By.CSS_SELECTOR, "table#ctl00_ContentPlaceHolder1_gvBooked tr")

        for row in rows:
            td_cells = row.find_elements(By.TAG_NAME, "td")
            if len(td_cells) > 0:
                lesson_name = td_cells[4].text

                # Use the helper function to determine field type
                field_type = determine_field_type(lesson_name)

                if field_type: # If a valid type is found.
                    self.set_attribute_with_fieldtype("lesson_name", field_type, lesson_name)
                    booked_sessions = self.get_attribute_with_fieldtype("booked_sessions", field_type)

                    date_text = td_cells[0].text
                    time_text = f"{td_cells[2].text[:-3]} - {td_cells[3].text[:-3]}"

                    if date_text not in booked_sessions:
                        booked_sessions.update({date_text: [time_text]})
                    else:
                        booked_sessions[date_text].append(time_text)



    # ---------- OPENS THE SPECIFIC BOOKING PAGE FOR A GIVEN SESSION TYPE USING THE CALLBACK MAP ----------
    def open_field_type_booking_page(self, field_type: str):
        return self.opening_booking_page_callback_map[field_type](field_type)



    # ---------- OPENS THE BOOKING PAGE FOR PRACTICAL LESSONS ----------
    def open_practical_lessons_booking_page(self, field_type: str, call_depth: int = 0):
        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingPL.aspx", sleep_delay=1)

        if not self.check_access_rights("NewPortal/Booking/BookingPL.aspx"):
            self.log.debug(f"User does not have {field_type.upper()} as an available option.")
            return False

        course_data = self.get_course_data() # Get available courses.
        if not course_data:
            self.log.error("Could not get course data. Program probably encountered a hCaptcha.")
            raise Exception("Could not get course data. Program probably encountered a hCaptcha.")

        if len(course_data["available_courses"]) <= 1: # Expect more than one if courses are available.
            self.log.warning(f"No {field_type.upper()} courses available.")
            return False

        # Attempt to select the "Class 3A Motorcar" course or the second course by index as a fallback.
        if not (self.select_course_from_name(course_data, "Class 3A Motorcar") or
                self.select_course_from_idx(course_data, 1)): # Index 1 assumes index 0 is a placeholder like "Select Course".
            self.log.warning("Could not a select course.")
            return False

        # This page often requires solving a normal CAPTCHA.
        if not self.dismiss_normal_captcha(caller_identifier="Practical Lessons Booking", solve_captcha=True):
            return self.open_practical_lessons_booking_page(field_type, call_depth + 1)

        time.sleep(2) # Wait for content to load after CAPTCHA.
        if selenium_common.is_elem_present(self.driver, By.ID, "ctl00_ContentPlaceHolder1_lblFullBookMsg"):
            self.log.info("No available practical lessons currently.")
            self.notification_manager.send_notification_all(title="", msg="No available practical lessons currently")
            return False

        # Check for and process sessions from other teams if applicable (OneTeam users).
        if selenium_common.is_elem_present(self.driver, By.ID, "ctl00_ContentPlaceHolder1_ddlOthTeamID"):
            available_teams_dropdown_data = self.get_course_data("ctl00_ContentPlaceHolder1_ddlOthTeamID")

            if self.program_config["book_from_other_teams"] and len(available_teams_dropdown_data["available_courses"]) > 1:
                # Store current available sessions before checking other teams.
                self.get_all_session_date_times(Types.PRACTICAL)
                self.get_all_available_sessions(Types.PRACTICAL)

                available_teams_str_report = "" # For notification.

                # Iterate through other available teams in the dropdown.
                for idx in range(1, len(available_teams_dropdown_data["available_courses"])):
                    # Re-fetch dropdown data as page might reload/change.
                    current_teams_data = self.get_course_data("ctl00_ContentPlaceHolder1_ddlOthTeamID")
                    if len(current_teams_data["available_courses"]) > idx:
                        selected_team_name = self.select_course_from_idx(current_teams_data, idx)
                        available_teams_str_report += "=======================\n"
                        available_teams_str_report += f"{selected_team_name} has slots:\n\n"
                        time.sleep(1) # Wait for team selection to apply.

                        # Wait for loading indicator to disappear.
                        loading_element = selenium_common.wait_for_elem(self.driver, By.ID,
                                                                        "ctl00_ContentPlaceHolder1_UpdateProgress1")
                        while loading_element.is_displayed():
                            time.sleep(0.5)

                        team_specific_available_sessions = {}
                        self.get_all_available_sessions(Types.PRACTICAL, team_specific_available_sessions) # Get sessions for this team.

                        for available_date_str, available_time_slots in team_specific_available_sessions.items():
                            available_teams_str_report += f"{available_date_str}:\n"
                            for time_slot in available_time_slots:
                                available_teams_str_report += f"  -> {time_slot}\n"
                        available_teams_str_report += "=======================\n"

                        # It seems the intention might be to revert to the original team or re-fetch main list here.
                        # The current implementation re-fetches main list after each team, which might be redundant
                        # if the goal is just to report other teams' slots.
                        self.get_all_session_date_times(Types.PRACTICAL)
                        self.get_all_available_sessions(Types.PRACTICAL)

                if available_teams_str_report:
                    self.notification_manager.send_notification_all(
                        title=f"SESSIONS FROM OTHER TEAMS DETECTED",
                        msg=available_teams_str_report
                    )
        return True



    # ---------- OPENS THE BOOKING PAGE FOR PRACTICAL TESTS (PT) ----------
    def open_practical_test_booking_page(self, field_type: str, call_depth: int = 0):
        # Check if the user is on revision lessons, implying they've completed practicals and might not be eligible for PT booking yet.
        # self.lesson_name_practical seems to be an attribute from the parent class or needs to be set.
        if "REVISION" in self.lesson_name_practical: # Assuming self.lesson_name_practical is available and up-to-date.
            self.log.info("No practical lesson available for user, seems user has completed practical lessons")
            return False

        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingPT.aspx", sleep_delay=1)

    def _fetch_with_flaresolverr(self, url_to_fetch: str, method: str = "request.get") -> Tuple[Optional[str], Optional[List[Dict]]] | None:
        """Fetch a URL using FlareSolverr with proper error handling and retries."""
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                self.log.info(f"Attempting to fetch {url_to_fetch} with FlareSolverr (attempt {attempt + 1}/{max_retries})")
                
                # Get FlareSolverr cookies
                cookies = self.get_flaresolverr_cookies()
                if not cookies:
                    self.log.error("Failed to get FlareSolverr cookies")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None

                # Prepare headers with cookies
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                }

                # Add cookies to headers
                cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
                headers['Cookie'] = cookie_str

                # Make the request
                if method.lower() == "request.get":
                    response = requests.get(url_to_fetch, headers=headers, timeout=30)
                else:
                    response = requests.post(url_to_fetch, headers=headers, timeout=30)

                # Check response
                if response.status_code == 200:
                    self.log.info("Successfully fetched URL with FlareSolverr")
                    return response.text, cookies
                else:
                    self.log.warning(f"FlareSolverr request failed with status code {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None

            except requests.exceptions.RequestException as e:
                self.log.error(f"Request error with FlareSolverr: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
            except Exception as e:
                self.log.error(f"Unexpected error with FlareSolverr: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None

        return None

    def get_flaresolverr_cookies(self):
        """Get cookies from FlareSolverr with proper error handling."""
        try:
            flaresolverr_url = self.browser_config.get("flaresolverr_url", "http://localhost:8191/v1")
            target_url = "https://www.cdc.com.sg"

            # Prepare the request to FlareSolverr
            data = {
                "cmd": "sessions.create",
                "url": target_url,
                "maxTimeout": 60000
            }

            # Make the request to FlareSolverr
            response = requests.post(flaresolverr_url, json=data, timeout=30)
            
            if response.status_code != 200:
                self.log.error(f"FlareSolverr request failed with status code {response.status_code}")
                return None

            result = response.json()
            if result.get("status") != "ok":
                self.log.error(f"FlareSolverr returned error: {result.get('message', 'Unknown error')}")
                return None

            # Extract cookies from the response
            cookies = result.get("solution", {}).get("cookies", [])
            if not cookies:
                self.log.error("No cookies returned from FlareSolverr")
                return None

            return cookies

        except requests.exceptions.RequestException as e:
            self.log.error(f"Request error with FlareSolverr: {e}")
            return None
        except Exception as e:
            self.log.error(f"Unexpected error with FlareSolverr: {e}")
            return None

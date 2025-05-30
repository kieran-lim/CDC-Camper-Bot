import os
import threading
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor

from src.utils.log import Log
from src.website_handler import handler
from src.utils.common import utils
from src.utils.captcha.two_captcha import Captcha as TwoCaptcha
from src.utils.notifications.notification_manager import NotificationManager


class AccountManager:
    def __init__(self, config: Dict, log: Log):
        """Initialize the account manager with configuration and shared resources
        
        Args:
            config: The loaded configuration dictionary
            log: Shared log instance
        """
        self.config = config
        self.log = log
        self.accounts = self._parse_accounts()
        
        # Initialize captcha solver only once to be shared across accounts
        self.captcha_solver = TwoCaptcha(log=log, config=config["two_captcha_config"])
        
        # Initialize shared notification manager
        self.notification_manager = NotificationManager(
            log=log, 
            discord_config=config.get("discord_config", {})
        )
        
        # Track running accounts for proper cleanup
        self.running_accounts = set()
        
    def _parse_accounts(self) -> List[Dict]:
        """Parse the accounts from the configuration file
        
        Returns:
            List of account dictionaries with username, password, and other settings
        """
        # Check if accounts section exists
        if "accounts" not in self.config:
            self.log.error("No 'accounts' section found in config.yaml. Please use the multi-account format.")
            return []
            
        accounts = self.config["accounts"]
        
        # Ensure each account has a name (for temp directories and notifications)
        for i, account in enumerate(accounts):
            if "name" not in account:
                account["name"] = f"account_{i+1}" if account.get("username", "") == "" else account["username"]
                
        # Validate and filter accounts
        valid_accounts = []
        for account in accounts:
            if not account.get("username") or not account.get("password"):
                self.log.warning(f"Account {account.get('name', 'unknown')} is missing username or password, skipping")
                continue
            valid_accounts.append(account)
            
        if not valid_accounts:
            self.log.warning("No valid accounts found in configuration")
            
        return valid_accounts
    
    def get_account_temp_dir(self, account_name: str) -> str:
        """Get the temp directory for a specific account
        
        Args:
            account_name: The name of the account
            
        Returns:
            Path to the account's temp directory
        """
        account_temp_dir = os.path.join("temp", account_name)
        if not os.path.exists(account_temp_dir):
            os.makedirs(account_temp_dir)
        return account_temp_dir
    
    def clear_account_temp_dir(self, account_name: str) -> None:
        """Clear the temp directory for a specific account
        
        Args:
            account_name: The name of the account
        """
        account_temp_dir = self.get_account_temp_dir(account_name)
        utils.clear_directory(account_temp_dir, self.log)
    
    def _delayed_account_start(self, account: Dict, delay_seconds: int = 0) -> None:
        """Start an account with an optional delay to stagger account processing
        
        Args:
            account: The account configuration
            delay_seconds: Seconds to wait before starting the account
        """
        if delay_seconds > 0:
            self.log.info(f"Account {account['name']} scheduled to start in {delay_seconds} seconds")
            time.sleep(delay_seconds)
            
        self.run_account(account)
    
    def run_account(self, account: Dict) -> None:
        """Run the bot for a single account
        
        Args:
            account: The account configuration dictionary
        """
        if not account.get("enabled", True):
            self.log.info(f"Account {account['name']} is disabled, skipping")
            return
            
        # Add to running accounts set
        self.running_accounts.add(account['name'])
            
        # Set up account temp directory
        self.clear_account_temp_dir(account["name"])
        
        # Create a new handler instance
        cdc_handler = None
        try:
            cdc_handler = handler(
                login_credentials={"username": account["username"], "password": account["password"]},
                captcha_solver=self.captcha_solver,
                log=self.log,
                notification_manager=self.notification_manager,
                browser_config=self.config["browser_config"],
                program_config=self.config["program_config"],
                account_name=account["name"],
                full_config=self.config  # Pass the full config for account-specific settings
            )
            
            # Prefix all logs for this account
            cdc_handler.log.set_prefix(f"[{account['name']}] ")
            
            try:
                # Log into CDC website
                success_logging_in = cdc_handler.account_login()
                if not success_logging_in:
                    cdc_handler.log.error(f"Failed to log in with account {account['name']}")
                    # Send notification about login failure
                    self.notification_manager.send_notification_all(
                        title=f"[{account['name']}] Login Failed",
                        msg=f"Failed to log in with account {account['name']}. Check credentials."
                    )
                    return
                    
                # Get the types of sessions to monitor from account config
                monitored_types = account.get("monitored_types", self.config["program_config"]["monitored_types"])
                
                # Process the account
                cdc_handler.process_account(monitored_types)
                    
            except Exception as e:
                cdc_handler.log.error(f"Account {account['name']} encountered an error: {e}")
                self.notification_manager.send_notification_all(
                    title=f"[{account['name']}] Error",
                    msg=f"Account {account['name']} encountered an error: {e}"
                )
            finally:
                # Ensure we log out
                if cdc_handler:
                    try:
                        cdc_handler.account_logout()
                    except:
                        pass
                    
                    # Close the driver to release resources
                    try:
                        cdc_handler.driver.quit()
                    except:
                        pass
        except Exception as e:
            self.log.error(f"Failed to create handler for account {account['name']}: {e}")
            self.notification_manager.send_notification_all(
                title=f"[{account['name']}] Setup Error",
                msg=f"Failed to initialize handler for account {account['name']}: {e}"
            )
        finally:
            # Remove from running accounts
            if account['name'] in self.running_accounts:
                self.running_accounts.remove(account['name'])

    def run_all_accounts(self) -> None:
        """Run the bot for all enabled accounts in parallel with optimized resource usage"""
        enabled_accounts = [a for a in self.accounts if a.get("enabled", True)]
        
        if not enabled_accounts:
            self.log.warning("No enabled accounts found")
            return
        
        # Get max_concurrent_accounts from config or use an unlimited value (0)
        max_concurrent_accounts = self.config.get("program_config", {}).get("max_concurrent_accounts", 0)
        
        # If unlimited (0) or value greater than available accounts, use all accounts
        if max_concurrent_accounts <= 0 or max_concurrent_accounts > len(enabled_accounts):
            max_workers = len(enabled_accounts)
        else:
            max_workers = max_concurrent_accounts
            
        self.log.info(f"Starting {max_workers} concurrent account sessions...")
        
        # Stagger account starts to reduce peak resource usage
        # Each account starts with a delay to prevent all browsers opening at once
        stagger_seconds = 30  # Seconds between account starts
        
        # Use ThreadPoolExecutor to run accounts in parallel with limited workers
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit account tasks with staggered starts
            futures = {}
            for i, account in enumerate(enabled_accounts):
                delay = i * stagger_seconds
                self.log.info(f"Scheduling account {account['name']} with {delay}s delay")
                future = executor.submit(self._delayed_account_start, account, delay)
                futures[future] = account
            
            # Process results as they complete
            for future in as_completed(futures):
                account = futures[future]
                try:
                    future.result()  # This will re-raise any exceptions from the thread
                except Exception as e:
                    self.log.error(f"Account {account['name']} raised an unhandled exception: {e}")
        
        # Force cleanup any remaining resources
        self._cleanup_resources()
                
    def _cleanup_resources(self):
        """Clean up resources for any accounts that are still running"""
        for account_name in list(self.running_accounts):
            self.log.warning(f"Forcing cleanup for account {account_name} that didn't exit cleanly")
            # Clear temp directory to remove any leftover files
            try:
                self.clear_account_temp_dir(account_name)
            except Exception as e:
                self.log.error(f"Error cleaning up temp directory for {account_name}: {e}")
            
            # Remove from running accounts
            self.running_accounts.remove(account_name) 
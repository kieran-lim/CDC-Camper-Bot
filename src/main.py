# STANDARD LIBRARY IMPORTS
import datetime  # For handling dates and times
import os        # For file and directory operations
import sys       # For system-level operations
import time      # For creating delays
import gc        # For garbage collection
import traceback # For detailed error tracking
import signal    # For handling termination signals

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# UTILITY MODULES
from src.utils.common import utils                   # General utility functions
from src.utils.log import Log                        # Logging functionality
from src.utils.account_manager import AccountManager # Account manager for multiple accounts
from src.utils.notifications.notification_manager import NotificationManager # For notifications

# For clean program termination
def signal_handler(sig, frame):
    print("\nProgram is shutting down gracefully...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Set up memory optimization
def optimize_memory():
    """Force Python garbage collection to free memory"""
    gc.collect()

# MAIN PROGRAM
if __name__ == "__main__":
    try:
        # Load configuration from config.yaml file
        config = utils.load_config_from_yaml_file(file_path="config.yaml")
        program_config = config["program_config"]  # Extract program-specific configuration

        # Initialize core components with appropriate configs
        log = Log(directory="logs", name="cdc-helper", config=config["log_config"])  # Set up logging

        # Set up notification managers
        notification_manager = NotificationManager(
            log=log,
            discord_config=config.get("discord_config", {}),
            full_config=config  # Pass the full config
        )
        
        # Connect the notification manager to the logger for Discord integration
        if config.get("discord_config", {}).get("discord_notification_enabled", False) and \
           config.get("log_config", {}).get("send_logs_to_discord", False):
            log.set_notification_manager(notification_manager)
            log.info("Discord logging enabled")

        # Create main temp directory if it doesn't exist
        if not os.path.exists("temp"):
            os.makedirs("temp")
        
        # Clean up temp directory at startup to remove stale files
        utils.clear_directory("temp", log)

        # Initialize the account manager
        account_manager = AccountManager(config=config, log=log)
        
        # Initial notification to confirm bot is running
        notification_manager.send_notification_all(
            title="CDC Bot Started",
            msg=f"CDC Bot started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # MAIN PROGRAM LOOP ---> continues indefinitely or until manual interruption
        # (if auto_restart is False)
        run_count = 0
        while True:
            run_count += 1
            try:
                # Run all accounts in parallel
                log.info(f"Starting run #{run_count}")
                account_manager.run_all_accounts()
                
                # Explicit memory optimization after each run
                optimize_memory()
                    
                # If auto restart is disabled, exit the outer loop
                if not program_config["auto_restart"]:
                    log.info("Auto restart is disabled. Exiting program.")
                    break
                    
                # If auto restart is enabled, wait for restart duration before restarting
                sleep_duration = datetime.timedelta(hours=1)
                next_run_time = datetime.datetime.now() + sleep_duration
                message = f"Program scheduled to restart at {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}"
                
                # Log restart information
                log.info(message + "\n# ------------------------------------- - ------------------------------------ #\n\n")
                
                # Wait for restart time
                time.sleep(sleep_duration.total_seconds())
                
            except KeyboardInterrupt:
                # Handle manual termination (Ctrl+C)
                log.info("Program stopped by user.")
                break
            except Exception as e:
                # Handle any unexpected errors with detailed stack trace
                log.error(f"Program encountered an error: {e}")
                log.error(traceback.format_exc())
                
                # Notify about the error
                notification_manager.send_notification_all(
                    title="CDC Bot Error",
                    msg=f"Program encountered an error: {e}\n\nSee logs for details."
                )
                
                # If auto restart is disabled, exit
                if not program_config["auto_restart"]:
                    log.error("Auto restart is disabled. Exiting after error.")
                    break
                    
                # Wait before restarting due to error
                sleep_duration = datetime.timedelta(minutes=30)  # Reduced from 1 hour to 30 minutes
                next_run_time = datetime.datetime.now() + sleep_duration
                message = f"Program will restart after error at {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}"
                log.info(message)
                time.sleep(sleep_duration.total_seconds())
            
            # Force memory cleanup between runs
            optimize_memory()

        # Final log message when program exits completely
        log.info("Program exited successfully.")
        notification_manager.send_notification_all(
            title="CDC Bot Stopped",
            msg=f"CDC Bot stopped at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    except Exception as e:
        # Handle critical errors that occur outside the main loop
        print(f"Critical error: {e}")
        print(traceback.format_exc())
        sys.exit(1)

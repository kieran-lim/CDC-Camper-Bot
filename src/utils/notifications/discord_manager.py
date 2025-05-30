import requests
import json
import time
from datetime import datetime
from typing import Dict, Optional


class DiscordManager:
    """Discord notification manager using Discord webhooks"""
    
    def __init__(self, log, config):
        """
        Initialize the Discord notification manager
        
        Args:
            log: The logger instance
            config: Discord configuration dictionary with webhook_url
        """
        self.log = log
        self.config = config
        self.enabled = config.get("discord_notification_enabled", False)
        self.webhook_url = config.get("webhook_url", "")
        self.username = config.get("bot_username", "CDC Bot")
        self.avatar_url = config.get("avatar_url", "")
        self.log_channel_webhook = config.get("log_channel_webhook", self.webhook_url)
        self.queries_channel_webhook = config.get("queries_webhook_url", self.log_channel_webhook)
        self.reservations_webhook_url = config.get("reservations_webhook_url", self.webhook_url)
        self.store_value_webhook_url = config.get("store_value_webhook_url", self.webhook_url)
        self.error_logs_webhook_url = config.get("error_logs_webhook_url", self.webhook_url)
        self.send_queries = config.get("send_queries_to_discord", False)
        self.send_error_logs = config.get("send_error_logs_to_discord", False)
        
        # Validate configuration
        if self.enabled and not self.webhook_url:
            self.log.error("Discord notifications are enabled but webhook_url is not set")
            self.enabled = False
            
    def send_notification(self, title: str, msg: str, color: Optional[int] = None) -> bool:
        """
        Send a notification to Discord
        
        Args:
            title: The notification title
            msg: The notification message
            color: Discord embed color (optional)
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        if not self.enabled:
            return False
            
        if not color:
            color = 3447003  # Discord blue color
            
        # Format the message for Discord
        embeds = [{
            "title": title,
            "description": msg,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        payload = {
            "username": self.username,
            "embeds": embeds
        }
        
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
            
        # Send the message
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 1)
                self.log.warning(f"Discord rate limited. Retrying after {retry_after}s")
                time.sleep(retry_after)
                
                # Retry once
                response = requests.post(
                    self.webhook_url,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"}
                )
                
            if response.status_code >= 400:
                self.log.error(f"Failed to send Discord notification: {response.status_code} - {response.text}")
                return False
                
            return True
            
        except Exception as e:
            self.log.error(f"Error sending Discord notification: {e}")
            return False
    
    def _send_to_webhook(self, webhook_url: str, payload: Dict, retry_on_rate_limit: bool = True) -> bool:
        """
        Helper method to send a payload to a specific webhook URL
        
        Args:
            webhook_url: The webhook URL to send to
            payload: The JSON payload to send
            retry_on_rate_limit: Whether to retry on rate limit (429) errors
            
        Returns:
            bool: True if successfully sent, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            response = requests.post(
                webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            
            # Check for rate limiting
            if response.status_code == 429 and retry_on_rate_limit:
                retry_after = response.json().get("retry_after", 1)
                self.log.warning(f"Discord rate limited. Retrying after {retry_after}s")
                time.sleep(retry_after)
                
                # Retry once
                response = requests.post(
                    webhook_url,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"}
                )
                
            if response.status_code >= 400:
                self.log.error(f"Failed to send Discord notification: {response.status_code} - {response.text}")
                return False
                
            return True
            
        except Exception as e:
            self.log.error(f"Error sending Discord notification: {e}")
            return False
            
    def send_log(self, level: str, msg: str) -> bool:
        """
        Send a log message to the Discord log channel
        
        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            msg: The log message
            
        Returns:
            bool: True if the log was sent successfully, False otherwise
        """
        if not self.enabled or not self.config.get("send_logs_to_discord", False):
            return False
            
        # Determine color based on log level
        colors = {
            "DEBUG": 7506394,    # Light gray
            "INFO": 3066993,     # Green
            "WARNING": 16776960, # Yellow
            "ERROR": 15158332,   # Red
            "CRITICAL": 10038562 # Purple
        }
        color = colors.get(level.upper(), 7506394)
        
        # Create a simpler message for logs to avoid spam
        embeds = [{
            "description": f"**[{level.upper()}]** {msg}",
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        payload = {
            "username": f"{self.username} Logs",
            "embeds": embeds
        }
        
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
            
        # Use low-priority sending (no retry)
        return self._send_to_webhook(self.log_channel_webhook, payload, retry_on_rate_limit=False)
            
    def send_booking_alert(self, account_name: str, session_type: str, date: str, time: str) -> bool:
        """
        Send a special alert for successful bookings to the reservations channel
        
        Args:
            account_name: Name of the account that booked the session
            session_type: Type of session (practical/test)
            date: Session date
            time: Session time
            
        Returns:
            bool: True if the alert was sent successfully, False otherwise
        """
        title = f"🎉 NEW BOOKING - {account_name} 🎉"
        msg = (f"Successfully reserved a **{session_type}** session!\n\n"
               f"**Date:** {date}\n"
               f"**Time:** {time}\n\n"
               f"⚠️ **ACTION REQUIRED** ⚠️\n"
               f"Log in to CDC website to confirm this reservation!")
               
        # Use a special green color for bookings
        embeds = [{
            "title": title,
            "description": msg,
            "color": 5763719,
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        payload = {
            "username": f"{self.username} Reservations",
            "embeds": embeds
        }
        
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        
        # Send to both main webhook and specialized reservations webhook
        main_sent = self._send_to_webhook(self.webhook_url, payload)
        reservations_sent = self._send_to_webhook(self.reservations_webhook_url, payload)
        
        return main_sent or reservations_sent
        
    def send_booking_confirmation_alert(self, account_name: str, session_type: str, date: str, time: str) -> bool:
        """
        Send a special alert for successfully confirmed bookings to the reservations channel
        
        Args:
            account_name: Name of the account that confirmed the session
            session_type: Type of session (practical/test)
            date: Session date
            time: Session time
            
        Returns:
            bool: True if the alert was sent successfully, False otherwise
        """
        title = f"✅ BOOKING CONFIRMED - {account_name} ✅"
        msg = (f"Successfully confirmed a **{session_type}** session!\n\n"
               f"**Date:** {date}\n"
               f"**Time:** {time}\n\n"
               f"This session is now fully booked and confirmed. No further action required.")
               
        # Use a deeper green color for confirmed bookings
        embeds = [{
            "title": title,
            "description": msg,
            "color": 2067276,  # Darker green
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        payload = {
            "username": f"{self.username} Reservations",
            "embeds": embeds
        }
        
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        
        # Send to both main webhook and specialized reservations webhook
        main_sent = self._send_to_webhook(self.webhook_url, payload)
        reservations_sent = self._send_to_webhook(self.reservations_webhook_url, payload)
        
        return main_sent or reservations_sent
    
    def send_store_value_warning(self, account_name: str, balance: float, threshold: float) -> bool:
        """
        Send a store value warning to the dedicated channel
        
        Args:
            account_name: Name of the account with low store value
            balance: Current balance amount
            threshold: Configured threshold amount
            
        Returns:
            bool: True if the warning was sent successfully, False otherwise
        """
        title = f"⚠️ LOW STORE VALUE - {account_name} ⚠️"
        msg = (f"Your CDC store value balance for account **{account_name}** is below ${threshold:.2f}.\n\n"
               f"**Current balance:** ${balance:.2f}\n\n"
               f"Please top up your store value to ensure you can continue booking slots.")
               
        # Use a warning orange color
        embeds = [{
            "title": title,
            "description": msg,
            "color": 16744192,  # Orange
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        payload = {
            "username": f"{self.username} Store Value",
            "embeds": embeds
        }
        
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        
        # Send to both main webhook and specialized store value webhook
        main_sent = self._send_to_webhook(self.webhook_url, payload)
        store_value_sent = self._send_to_webhook(self.store_value_webhook_url, payload)
        
        return main_sent or store_value_sent
     
    def send_query_log(self, account_name: str, field_type: str, available_slots: Dict) -> bool:
        """
        Send a query log to the Discord queries channel
        
        Args:
            account_name: Name of the account checking for slots
            field_type: Type of session (practical/pt)
            available_slots: Dictionary of available slots found
            
        Returns:
            bool: True if the query log was sent successfully, False otherwise
        """
        if not self.enabled or not self.send_queries:
            return False
            
        # Determine color (blue for queries)
        color = 3447003  # Discord blue color
        
        # Create a message indicating whether slots were found
        slots_found = sum(len(times) for times in available_slots.values()) if available_slots else 0
        
        # Get current time in a readable format
        current_time = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        
        # Format the available slots information
        slots_info = ""
        if slots_found > 0:
            slots_info = "\n\n**Available slots:**\n"
            for date, times in available_slots.items():
                slots_info += f"**{date}:** {', '.join(times)}\n"
        
        description = (f"**Account:** {account_name}\n"
                     f"**Session Type:** {field_type.upper()}\n"
                     f"**Check Time:** {current_time}\n"
                     f"**Slots Found:** {slots_found}{slots_info}")
        
        # Create a simpler message for query logs
        embeds = [{
            "title": f"Slot Check - {field_type.upper()}",
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        payload = {
            "username": f"{self.username} Queries",
            "embeds": embeds
        }
        
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
            
        # Use low-priority sending (no retry)
        return self._send_to_webhook(self.queries_channel_webhook, payload, retry_on_rate_limit=False)
        
    def send_error_log(self, account_name: str, error_msg: str, error_type: str = "Error", stack_trace: str = None) -> bool:
        """
        Send a detailed error log to the Discord error logs channel
        
        Args:
            account_name: Name of the account that encountered the error
            error_msg: The error message
            error_type: Type of error (e.g. "Login Error", "Connection Error")
            stack_trace: Optional stack trace for more detailed debugging
            
        Returns:
            bool: True if the error log was sent successfully, False otherwise
        """
        if not self.enabled or not self.send_error_logs:
            return False
            
        # Use red color for errors
        color = 15158332  # Discord red color
        
        # Get current time in a readable format
        current_time = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        
        # Prepare description with error details
        description = (f"**Account:** {account_name}\n"
                      f"**Error Type:** {error_type}\n"
                      f"**Time:** {current_time}\n"
                      f"**Error Message:** {error_msg}\n")
                      
        # Add stack trace if provided, but format it as a code block
        if stack_trace:
            # Limit stack trace length to avoid Discord's message limit
            max_stack_length = 2000 - len(description) - 50  # Reserve some space for formatting
            if len(stack_trace) > max_stack_length:
                stack_trace = stack_trace[:max_stack_length] + "...(truncated)"
            
            description += f"\n**Stack Trace:**\n```\n{stack_trace}\n```"
        
        # Create the error log message
        embeds = [{
            "title": f"Error Log - {error_type}",
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }]
        
        payload = {
            "username": f"{self.username} Error Logs",
            "embeds": embeds
        }
        
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
            
        # Send with retry enabled since errors are important
        return self._send_to_webhook(self.error_logs_webhook_url, payload, retry_on_rate_limit=True) 
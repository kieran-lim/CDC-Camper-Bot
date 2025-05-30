from src.utils.notifications.discord_manager import DiscordManager


class NotificationManager:
    def __init__(self, log, discord_config: dict = None, full_config: dict = None):
        self.log = log
        self.discord_manager = False
        self.full_config = full_config or {}

        # Initialize Discord
        if discord_config and discord_config.get("discord_notification_enabled", False):
            self.discord_manager = DiscordManager(
                log=log,
                config=discord_config
            )

    def send_notification_all(self, title: str, msg: str, account_name: str = None):
        """Send notification to all enabled platforms"""
        discord_result = None
            
        if self.discord_manager:
            discord_result = self.discord_manager.send_notification(title=title, msg=msg)
            
        return discord_result

    def send_notification_discord(self, title: str, msg: str, color: int = None):
        """Send notification specifically to Discord"""
        if self.discord_manager:
            return self.discord_manager.send_notification(title=title, msg=msg, color=color)
        return None
        
    def send_log_to_discord(self, level: str, msg: str):
        """Send a log message to Discord"""
        if self.discord_manager:
            return self.discord_manager.send_log(level=level, msg=msg)
        return None
        
    def send_query_log_to_discord(self, account_name: str, field_type: str, available_slots: dict):
        """Send a query log to Discord showing slot check results"""
        if self.discord_manager:
            return self.discord_manager.send_query_log(
                account_name=account_name, 
                field_type=field_type, 
                available_slots=available_slots
            )
        return None
        
    def send_error_log_to_discord(self, account_name: str, error_msg: str, error_type: str = "Error", stack_trace: str = None):
        """Send a detailed error log to Discord error channel"""
        if self.discord_manager:
            return self.discord_manager.send_error_log(
                account_name=account_name,
                error_msg=error_msg,
                error_type=error_type,
                stack_trace=stack_trace
            )
        return None
        
    def send_booking_alert(self, account_name: str, session_type: str, date: str, time: str):
        """Send a booking alert to all platforms"""
        # Send to Discord with special formatting
        if self.discord_manager:
            self.discord_manager.send_booking_alert(
                account_name=account_name,
                session_type=session_type,
                date=date,
                time=time
            )
            
    def send_booking_confirmation_alert(self, account_name: str, session_type: str, date: str, time: str):
        """Send a booking confirmation alert to all platforms"""
        # Send to Discord with special formatting
        if self.discord_manager:
            self.discord_manager.send_booking_confirmation_alert(
                account_name=account_name,
                session_type=session_type,
                date=date,
                time=time
            )

    def send_notification_mail(self, title: str, msg: str):
        # This method is removed as per the instructions
        pass

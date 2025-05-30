# CDC-BOT

This is a [ComfortDelGro Driving Centre](https://www.cdc.sg/) camper bot that helps you to book practical lessons and practical test slots.

## ⚠️ CURRENT STATUS: CLOUDFLARE BLOCKED ⚠️

**Important Update (May 2024):** This project is currently blocked by Cloudflare's advanced anti-bot protection. Both undetected-chromedriver and FlareSolverr attempts to bypass Cloudflare have been unsuccessful. This means the bot cannot currently access the CDC website.

### Roadblocks Encountered

1. **Cloudflare Protection**
   - The CDC website uses advanced Cloudflare protection that blocks automated access
   - Attempted solutions:
     - undetected-chromedriver with profile persistence
     - FlareSolverr integration
     - Various browser fingerprinting evasion techniques
   - Current status: All automated access attempts are blocked

2. **Previous CDC Anti-Bot Measures**
   - CDC has implemented measures to detect and block botting behavior
   - Accounts flagged for botting have their "Stored Value" disabled for 5 days
   - The exact detection criteria are unknown (request frequency, CAPTCHA behavior, etc.)

### How to Continue Development

If you want to continue development, here are some potential approaches:

1. **Manual Cookie Injection**
   - Implement a hybrid approach where users manually solve Cloudflare challenges
   - Store and reuse cookies for subsequent automated requests
   - Pros: Can work temporarily
   - Cons: Not fully automated, cookies expire quickly

2. **Third-Party Scraping APIs**
   - Consider using paid services like:
     - ScraperAPI
     - Bright Data
     - ZenRows
     - ScrapingBee
   - These services specialize in bypassing anti-bot protections
   - Pros: More reliable
   - Cons: Cost money, may have rate limits

3. **Mobile App Automation**
   - The CDC mobile app might have different security measures
   - Could try automating the app using Appium
   - Pros: Different attack vector
   - Cons: More complex setup, slower

4. **Browser Profile Reuse**
   - Use a real Chrome profile that has already solved Cloudflare
   - Pros: Can work for a while
   - Cons: Not fully automated, needs manual intervention

5. **Monitor for Updates**
   - Keep an eye on:
     - [FlareSolverr GitHub](https://github.com/FlareSolverr/FlareSolverr/issues)
     - [undetected-chromedriver GitHub](https://github.com/ultrafunkamsterdam/undetected-chromedriver/issues)
   - New bypass methods might be discovered

### Original Features (Currently Blocked)

The bot was designed with these features:
  - Periodically fetch available sessions for Practical Lesson and Practical Test
  - Automatically solve CAPTCHAs
  - Compare with booked dates for each available session
  - Notify user (via Discord) if earlier session is found
  - Attempt to reserve the session if possible
  - Support for multiple CDC accounts simultaneously 
  - Comprehensive booking restrictions to avoid specific dates and times
  - Store value monitoring to alert when account balance is low

---

# Prerequisites

## Python 3
You will need Python 3, which can be installed from the [official website](https://www.python.org/downloads).

## Chrome Browser
The bot requires Google Chrome to be installed on your system. You can download it from [here](https://www.google.com/chrome/).

## Download ChromeDriver
The bot requires ChromeDriver to control Chrome browser. You need to download the version that matches your Chrome browser version.

1. Check your Chrome version:
   - Open Chrome
   - Click the three dots in the top right
   - Go to Help > About Google Chrome
   - Note your version number

2. Download ChromeDriver:
   - Go to [ChromeDriver downloads](https://chromedriver.chromium.org/downloads)
   - Download the version that matches your Chrome version
   - Extract the downloaded file

3. Place ChromeDriver in the correct location:
   - Create a `drivers` folder in the project root if it doesn't exist
   - Create a subfolder named `win` for Windows or `osx` for macOS
   - Place the ChromeDriver executable in the appropriate folder:
     - Windows: `drivers/win/chromedriver.exe`
     - macOS: `drivers/osx/chromedriver`

   > **Important for Windows Users**: The repository only includes the macOS version of ChromeDriver. You must download the Windows version separately and place it in the `drivers/win` directory. Make sure to download the version that matches your Chrome browser version.

## Initialise configurations
Create `config.yaml` from the template and fill in the required fields.
```bash
$ cp config.yaml.example config.yaml
```

### 1) TwoCaptcha
This project uses a third party API that is unfortunately a **paid** service.  
As of writing, the rates of using this API are *relatively cheap* (SGD$5 can last you for about a month of the program 
runtime). To continue using this project, head over to [2captcha.com](https://2captcha.com/)

  - Create an account
  - Top up your account with sufficient credits
  - Copy your API Token and paste it into `config.yaml`

### 2) Discord Notifications
To enable Discord notifications:
  1. Set `discord_notification_enabled` to `True` in your config.yaml
  2. Create a Discord webhook URL for your notifications:
     - Go to your Discord server settings
     - Select "Integrations" > "Webhooks"
     - Click "New Webhook"
     - Give it a name (e.g., "CDC Bot")
     - Copy the webhook URL
  3. Paste the webhook URL into the `webhook_url` field in your config.yaml
  4. (Optional) Configure additional webhook URLs for different types of notifications:
     - `queries_webhook_url`: For slot check queries
     - `reservations_webhook_url`: For successful reservations
     - `store_value_webhook_url`: For store value warnings
     - `error_logs_webhook_url`: For detailed error logs

### 3) Program Configuration
The program checks for available slots at random intervals between 3-5 minutes. 
The program will not run from 3am to 6am as it is unlikely other people will cancel their bookings during that time, 
and the user will also likely be asleep and unable to book the session. This is to reduce requests to 2captcha.

#### Account Configuration

You **must** define at least one account in the `accounts` section:

```yaml
accounts:
  - name: "MyAccount"                          # A friendly name for the account
    username: "!USERNAME_HERE!"                # CDC Username 
    password: "!PASSWORD_HERE!"                # CDC Password
    enabled: True                              # Whether this account should be monitored
    monitored_types:                           # Which session types to monitor
      practical: True                          # Monitor practical lessons
      pt: False                                # Don't monitor practical tests
```

If you have multiple accounts, you can add them like this:

```yaml
accounts:
  - name: "Account1"
    username: "!USERNAME1_HERE!"
    password: "!PASSWORD1_HERE!"
    enabled: True
    monitored_types:
      practical: True
      pt: False
  
  - name: "Account2"
    username: "!USERNAME2_HERE!"
    password: "!PASSWORD2_HERE!"
    enabled: True
    monitored_types:
      practical: False
      pt: True
```

#### Controlling Concurrent Accounts

By default, the program will run all accounts concurrently. You can limit the number of concurrent accounts by setting the `max_concurrent_accounts` parameter in `program_config`:

```yaml
program_config:
  # Other settings...
  max_concurrent_accounts: 5  # Run maximum 5 accounts at once
```

Set to `0` for unlimited concurrent accounts.

#### Store Value Monitoring

The program monitors your CDC store value balance and sends alerts when it falls below a configurable threshold (default $100). To adjust this threshold, modify the `store_value_threshold` setting in your config file:

```yaml
program_config:
  # Other settings...
  store_value_threshold: 100  # Set your desired threshold amount in dollars
```

This helps ensure you always have sufficient funds to complete bookings.

#### Booking Restrictions

You can control when and how the program books slots by configuring booking restrictions. There are two ways to set these restrictions:

1. **Global restrictions** - apply to all accounts that don't have their own specific restrictions:

```yaml
program_config:
  # Other settings...
  booking_restrictions:
    # Dates to skip completely (format: DD/MM/YYYY)
    skip_dates:
      - "25/12/2023"  # Skip Christmas
    
    # Days of week to skip completely (0=Monday, 1=Tuesday, ..., 6=Sunday)
    skip_days_of_week:
      - 0  # Skip all Mondays
    
    # Time restrictions for specific dates
    date_time_restrictions:
      - date: "06/03/2023"
        avoid_times:
          - start: "09:00"  # No morning slots on March 6th
            end: "12:00"
    
    # Time restrictions for days of week
    day_time_restrictions:
      - day: 4  # Friday
        avoid_times:
          - start: "13:00"  # No afternoon slots on Fridays
            end: "17:00"
    
    # Maximum lessons per day
    max_lessons_per_day: 2  # Book maximum 2 lessons on any day
```

2. **Account-specific restrictions** - unique restrictions for individual accounts:

```yaml
accounts:
  - name: "Account1"
    username: "your_username"
    password: "your_password"
    enabled: True
    monitored_types:
      practical: True
      pt: False
    # Account-specific restrictions that override the global settings
    booking_restrictions:
      skip_dates:
        - "23/01/2023"  # Account1 will skip this date
      skip_days_of_week:
        - 1  # Account1 will skip Tuesdays
      max_lessons_per_day: 1  # Account1 can only book 1 lesson per day
      
  - name: "Account2"
    # Basic account details...
    # Different restrictions for Account2
    booking_restrictions:
      skip_days_of_week:
        - 5  # Account2 will skip Saturdays
      max_lessons_per_day: 3  # Account2 can book up to 3 lessons per day
```

If an account doesn't have specific restrictions defined, it will use the global restrictions. If it does have specific restrictions, those will completely override the global ones (not merge with them).

The program will skip any slots that don't meet these criteria and log the reason for skipping.

# Run it!
Run the program from the working directory `cdc-bot` so that the directories are in the correct path.
```bash
$ python src/main.py
```

Note: Due to the current Cloudflare block, the bot will not be able to access the CDC website. You'll need to implement one of the workarounds mentioned above to make it functional.

## Contributing

Contributions are welcome! Here are some areas where help is needed:

1. **Cloudflare Bypass**
   - Research and implement new methods to bypass Cloudflare
   - Test different browser automation approaches
   - Experiment with different user agents and browser fingerprints

2. **Mobile App Automation**
   - Develop an alternative approach using the CDC mobile app
   - Create Appium scripts for mobile automation

3. **Cookie Management**
   - Implement robust cookie storage and reuse
   - Create a system for manual cookie injection

4. **Error Handling**
   - Improve error recovery mechanisms
   - Add better logging and debugging tools

5. **Documentation**
   - Add more detailed setup instructions
   - Document any new bypass methods discovered

## License

[Previous license section remains unchanged...]

## Acknowledgments

- Original project by [Zhannyhong](https://github.com/Zhannyhong)
- Contributors who have helped maintain and improve the project
- The open-source community for tools like undetected-chromedriver and FlareSolverr

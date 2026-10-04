# Oracle VM Deployment Guide: Delta Testnet Bot

This guide explains how to safely deploy the `delta_testnet_bot.py` script on your Oracle VM without touching your existing live money bots.

## Step 1: Upload the script
Copy `delta_testnet_bot.py` to your Oracle VM. You can put it in a new folder, for example:
```bash
mkdir -p ~/delta_bot
# Upload delta_testnet_bot.py into this folder
cd ~/delta_bot
```

## Step 2: Create the Isolated Virtual Environment (venv)
Run these exact commands in your Oracle terminal to create a sandboxed Python environment.

```bash
# 1. Create the virtual environment named "delta_env"
python3 -m venv delta_env

# 2. Activate the virtual environment
source delta_env/bin/activate

# 3. Install the required packages ONLY inside this sandbox
pip install ccxt pandas pandas-ta requests
```

## Step 3: Configure the Script
Edit `delta_testnet_bot.py` using `nano` or `vim` and fill in your keys:
1. `YOUR_TESTNET_API_KEY`
2. `YOUR_TESTNET_API_SECRET`
3. `YOUR_TELEGRAM_BOT_TOKEN`
4. `YOUR_TELEGRAM_CHAT_ID`

## Step 4: Schedule the Hourly Cron Job
To ensure the bot runs exactly at the top of every hour, we will add it to your Linux `crontab`.

```bash
# Open the cron editor
crontab -e
```

Add the following line to the bottom of the file. Notice how we explicitly use the Python interpreter from the virtual environment we created, ensuring it is perfectly isolated:

```text
0 * * * * cd /home/ubuntu/delta_bot && /home/ubuntu/delta_bot/delta_env/bin/python delta_testnet_bot.py >> bot.log 2>&1
```
*(Note: Replace `/home/ubuntu/` with your actual home directory path, e.g., `/home/opc/` depending on your Oracle Linux setup).*

## Done!
That's it. 
- You can type `deactivate` to leave the virtual environment and go back to your normal terminal.
- Every hour at minute :00, the cron job will silently wake up, run the script inside the sandbox, and shut down.
- You will receive Telegram notifications if trades are taken or errors occur.
- You can check `bot.log` or `testnet_trades.db` at any time to review history.

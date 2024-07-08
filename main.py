import os
import re
import time
import random
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler
from telegram.ext.filters import Filters
from fake_useragent import UserAgent
from colorama import Fore, init

# Initialize colorama
init()

# Constants
OWNER_ID = 6008343239
WASTE_KEYWORDS = ["forum", "google", "wikipedia", "stackoverflow", "freelancer", "quora", "facebook", "amazon", "youtube", "reddit", "ebay"]
SEARCH_ENGINES = [
    "http://www.google.co.id/search?q={dork_keywords}&num=100&start=0",
    "http://www.google.co.id/search?q={dork_keywords}&num=100&start=100",
    "http://www.google.co.id/search?q={dork_keywords}&num=100&start=200",
    "http://www.google.com/search?q={dork_keywords}&num=100&start=0",
    "http://www.google.com/search?q={dork_keywords}&num=100&start=100",
    "http://www.google.com/search?q={dork_keywords}&num=100&start=200"
]

# User-agent
ua = UserAgent(browsers=['chrome'])

# In-memory storage for authorized users and proxies
authorized_users = {}
proxies = []

# Load authorized users from file
def load_authorized_users():
    if os.path.exists('users.txt'):
        with open('users.txt', 'r') as file:
            for line in file:
                parts = line.strip().split(',')
                if len(parts) == 2:
                    user_id, expiry = parts
                    authorized_users[int(user_id)] = datetime.strptime(expiry, '%Y-%m-%d')

# Save authorized users to file
def save_authorized_users():
    with open('users.txt', 'w') as file:
        for user_id, expiry in authorized_users.items():
            file.write(f"{user_id},{expiry.strftime('%Y-%m-%d')}\n")

# Load proxies from file
def load_proxies():
    if os.path.exists('proxy.txt'):
        with open('proxy.txt', 'r') as file:
            proxies.extend(file.read().splitlines())

# Save proxies to file
def save_proxies():
    with open('proxy.txt', 'w') as file:
        file.write('\n'.join(proxies))

# Helper functions
def is_authorized(user_id):
    return user_id in authorized_users and authorized_users[user_id] >= datetime.now()

def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        update.message.reply_text("Welcome owner,\n\nYour commands: /authorize, /proxy, /dork (query)\nExample: /dork Shopify+lipstick")
    elif is_authorized(user_id):
        update.message.reply_text("Welcome sir,\n\nYour command: /dork (query)\nExample: /dork Shopify+lipstick")
    else:
        update.message.reply_text("You are not authorized to use this bot. Please ask the owner to authorize you.")

def authorize(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        try:
            new_user_id = int(context.args[0])
            days = int(context.args[1])
            expiry_date = datetime.now() + timedelta(days=days)
            authorized_users[new_user_id] = expiry_date
            save_authorized_users()
            update.message.reply_text(f"User {new_user_id} has been authorized for {days} days.")
        except (IndexError, ValueError):
            update.message.reply_text("Usage: /authorize <user_id> <days>")
    else:
        update.message.reply_text("You are not authorized to use this command.")

def proxy(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        new_proxies = ' '.join(context.args).split(',')
        proxies.extend(new_proxies)
        save_proxies()
        update.message.reply_text("Proxies have been updated.")
    else:
        update.message.reply_text("You are not authorized to use this command.")

def dork(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        update.message.reply_text("You are not authorized to use this bot.")
        return

    query = ' '.join(context.args)
    if not query:
        update.message.reply_text("Usage: /dork <query>")
        return

    result = []
    try:
        for search_engine in SEARCH_ENGINES:
            proxy = None
            if proxies:
                proxy = {'http': random.choice(proxies)}
            req = requests.get(search_engine.replace('{dork_keywords}', query), headers={'User-Agent': ua.random}, proxies=proxy).text
            if 'captcha' in req:
                update.message.reply_text("Error: Captcha Detected. Please change your IP using VPN or use good proxies.")
                return
            regx = re.findall('https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', req)
            if regx:
                result.extend(regx)
        cleaned_links = list(dict.fromkeys(result))
        filtered_links = [link for link in cleaned_links if not any(keyword in link.lower() for keyword in WASTE_KEYWORDS)]
        
        if filtered_links:
            file_name = f"dork_results_{user_id}.txt"
            with open(file_name, 'w', encoding='utf8') as file:
                file.write('\n'.join(filtered_links))
            update.message.reply_document(open(file_name, 'rb'))
        else:
            update.message.reply_text("No valid links found.")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {e}")

def main():
    # Load authorized users and proxies from file
    load_authorized_users()
    load_proxies()
    
    updater = Updater("7280917209:AAGVxQ-cLURLfVIvLSwJCsWyAAUCIE0Su4o", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("authorize", authorize))
    dp.add_handler(CommandHandler("proxy", proxy))
    dp.add_handler(CommandHandler("dork", dork))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

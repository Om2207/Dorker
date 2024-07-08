import os
import re
import time
import random
import requests
from datetime import datetime, timedelta
from telegram import Update, InputFile
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from fake_useragent import UserAgent
from colorama import Fore, init

# Initialize colorama
init()

# Constants
OWNER_ID = 6008343239
WASTE_KEYWORDS = ["forum", "google", "wikipedia", "stackoverflow", "freelancer", "quora", "facebook", "amazon", "youtube", "reddit", "ebay"]
SEARCH_ENGINES = [
    "https://duckduckgo.com/?q={dork_keywords}&t=h_&ia=web",
    "http://www.bing.com/search?q={dork_keywords}&count=50&first=0",
    "http://www.bing.com/search?q={dork_keywords}&count=50&first=50",
    "http://www.bing.com/search?q={dork_keywords}&count=50&first=100",
    "https://search.yahoo.com/search?p={dork_keywords}&b=1",
    "https://search.yahoo.com/search?p={dork_keywords}&b=101",
    "https://search.yahoo.com/search?p={dork_keywords}&b=201",
    "http://www.google.com/search?q={dork_keywords}&num=100&start=0",
    "http://www.google.com/search?q={dork_keywords}&num=100&start=100",
    "http://www.google.com/search?q={dork_keywords}&num=100&start=200",
    "http://www.google.co.id/search?q={dork_keywords}&num=100&start=0",
    "http://www.google.co.id/search?q={dork_keywords}&num=100&start=100",
    "http://www.google.co.id/search?q={dork_keywords}&num=100&start=200"
]

# User-agent
ua = UserAgent()

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

# Remove all proxies
def remove_proxies():
    if os.path.exists('proxy.txt'):
        os.remove('proxy.txt')
    proxies.clear()

# Helper functions
def is_authorized(user_id):
    return user_id in authorized_users and authorized_users[user_id] >= datetime.now()

def escape_markdown(text):
    escape_chars = r"\-._>#+=|{}()[]`~"
    return ''.join([f'\\{c}' if c in escape_chars else c for c in text])

def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        welcome_message = (
            "👋 *Welcome to the Bot*\n\n"
            "Here are your available commands:\n"
            "• /dork `<query>`\n"
            "• /gates `<file>`\n"
            "• /id\n\n"
            "*Example:* `/dork Shopify+lipstick`\n\n"
            "*Owner commands:*\n"
            "• /authorize `<user_id>` `<days>`\n"
            "• /proxy `<proxy1>,<proxy2>,...`\n"
            "• /remove\n"
        )
    elif is_authorized(user_id):
        welcome_message = (
            "👋 *Welcome to the Bot*\n\n"
            "Here are your available commands:\n"
            "• /dork `<query>`\n"
            "• /gates `<file>`\n"
            "• /id\n\n"
            "*Example:* `/dork Shopify+lipstick`\n"
        )
    else:
        welcome_message = "You are not authorized to use this bot. Please ask the owner to authorize you."

    update.message.reply_text(escape_markdown(welcome_message), parse_mode='MarkdownV2')

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
            update.message.reply_text("Usage: /authorize `<user_id>` `<days>`")
    else:
        update.message.reply_text("You are not authorized to use this command.")

def proxy(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        new_proxies = ' '.join(context.args).split(',')
        for proxy in new_proxies:
            # Adjust the proxy if needed
            parts = proxy.split(':')
            if len(parts) == 4:
                proxy = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            proxies.append(proxy)
        save_proxies()
        update.message.reply_text("Proxies have been updated.")
    else:
        update.message.reply_text("You are not authorized to use this command.")

def remove(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        remove_proxies()
        update.message.reply_text("All proxies have been removed.")
    else:
        update.message.reply_text("You are not authorized to use this command.")

def dork(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        update.message.reply_text("You are not authorized to use this bot.")
        return

    query = ' '.join(context.args)
    if not query:
        update.message.reply_text("Usage: /dork `<query>`")
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

def gates(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        update.message.reply_text("You are not authorized to use this bot.")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        update.message.reply_text("Please reply to a file with /gates command.")
        return

    file_id = update.message.reply_to_message.document.file_id
    file = context.bot.get_file(file_id)
    file_path = file.download()

    with open(file_path, 'r') as f:
        urls = f.read().splitlines()

    results = []
    for url in urls:
        try:
            response = requests.get(f"https://api.adwadev.com/api/gate.php?url={url}", headers={'User-Agent': ua.random})
            response_json = response.json()
            site = response_json.get('Site', 'N/A')
            status = response_json.get('Status', 'N/A')
            gateway = response_json.get('Gateway', 'N/A')
            platform = response_json.get('Platform', 'N/A')
            captcha = response_json.get('Captcha', 'N/A')
            cloudflare = response_json.get('Cloudflare', 'N/A')
            graphql = response_json.get('GraphQL', 'N/A')
            result = (
                f"----------------------------------\n"
                f"URL: {site}\n"
                f"Status: {status}\n"
                f"Gateway: {gateway}\n"
                f"Platform: {platform}\n"
                f"Captcha: {captcha}\n"
                f"Cloudflare: {cloudflare}\n"
                f"GraphQL: {graphql}\n"
            )
            results.append(result)
        except (requests.exceptions.RequestException, ValueError) as e:
            results.append(f"Error processing {url}: {e}")

    results_text = "\n".join(results)
    result_file = "gate_results.txt"
    with open(result_file, 'w', encoding='utf8') as file:
        file.write(results_text)

    update.message.reply_document(open(result_file, 'rb'))

def user_info(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in authorized_users:
        expiry_date = authorized_users[user_id].strftime('%Y-%m-%d')
        update.message.reply_text(f"Your user ID: {user_id}\nAuthorized until: {expiry_date}")
    else:
        update.message.reply_text(f"Your user ID: {user_id}\nYou are not authorized to use this bot.")

def main():
    # Load authorized users and proxies from file
    load_authorized_users()
    load_proxies()
    
    updater = Updater("7280917209:AAGVxQ-cLURLfVIvLSwJCsWyAAUCIE0Su4o", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("authorize", authorize))
    dp.add_handler(CommandHandler("proxy", proxy))
    dp.add_handler(CommandHandler("remove", remove))
    dp.add_handler(CommandHandler("dork", dork))
    dp.add_handler(CommandHandler("gates", gates))
    dp.add_handler(CommandHandler("id", user_info))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
            

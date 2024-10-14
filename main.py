import os
import re
import time
import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from fake_useragent import UserAgent
from aiohttp import ClientSession
from bs4 import BeautifulSoup

# Constants
OWNER_ID = 6008343239
WASTE_KEYWORDS = ["forum", "google", "wikipedia", "stackoverflow", "freelancer", "quora", "facebook", "amazon", "youtube", "reddit", "ebay", "Yahoo", "bing", "duckduckgo"]
SEARCH_ENGINES = [
    "https://duckduckgo.com/?q={dork_keywords}&t=h_&ia=web",
    "http://www.bing.com/search?q={dork_keywords}&count=50&first=0",
    "https://search.yahoo.com/search?p={dork_keywords}&b=1",
    "http://www.google.com/search?q={dork_keywords}&num=100&start=0",
]

# User-agent
ua = UserAgent()

# In-memory storage for authorized users and proxies
authorized_users = {}
proxies = []

# Emojis for better visual appeal
EMOJI_ROCKET = "🚀"
EMOJI_LOCK = "🔒"
EMOJI_UNLOCK = "🔓"
EMOJI_GEAR = "⚙️"
EMOJI_SEARCH = "🔍"
EMOJI_CHART = "📊"
EMOJI_ID = "🆔"

# Load and save functions (unchanged)
def load_authorized_users():
    if os.path.exists('users.txt'):
        with open('users.txt', 'r') as file:
            for line in file:
                parts = line.strip().split(',')
                if len(parts) == 2:
                    user_id, expiry = parts
                    authorized_users[int(user_id)] = datetime.strptime(expiry, '%Y-%m-%d')

def save_authorized_users():
    with open('users.txt', 'w') as file:
        for user_id, expiry in authorized_users.items():
            file.write(f"{user_id},{expiry.strftime('%Y-%m-%d')}\n")

def load_proxies():
    if os.path.exists('proxy.txt'):
        with open('proxy.txt', 'r') as file:
            proxies.extend(file.read().splitlines())

def save_proxies():
    with open('proxy.txt', 'w') as file:
        file.write('\n'.join(proxies))

def remove_proxies():
    if os.path.exists('proxy.txt'):
        os.remove('proxy.txt')
    proxies.clear()

# Helper functions
def is_authorized(user_id):
    return user_id in authorized_users and authorized_users[user_id] >= datetime.now()

def create_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(f"{EMOJI_SEARCH} Dork", callback_data='dork'),
         InlineKeyboardButton(f"{EMOJI_CHART} Gates", callback_data='gates')],
        [InlineKeyboardButton(f"{EMOJI_ID} My ID", callback_data='id')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        welcome_message = f"{EMOJI_ROCKET} *Welcome, Master!*\n\nWhat would you like to do today?"
    elif is_authorized(user_id):
        welcome_message = f"{EMOJI_ROCKET} *Welcome to DorkMaster 3000!*\n\nWhat would you like to do today?"
    else:
        welcome_message = f"{EMOJI_LOCK} You are not authorized to use this bot. Please contact the owner."
        await update.message.reply_text(welcome_message)
        return

    await update.message.reply_text(welcome_message, reply_markup=create_menu_keyboard(), parse_mode='Markdown')

async def menu_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'dork':
        await query.message.reply_text(f"{EMOJI_SEARCH} Please enter your dork query:\n\nExample: `/dork Shopify+lipstick`", parse_mode='Markdown')
    elif query.data == 'gates':
        await query.message.reply_text(f"{EMOJI_CHART} Please upload a file with URLs to check, then reply to it with /gates")
    elif query.data == 'id':
        await user_info(update, context)

async def authorize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        try:
            new_user_id = int(context.args[0])
            days = int(context.args[1])
            expiry_date = datetime.now() + timedelta(days=days)
            authorized_users[new_user_id] = expiry_date
            save_authorized_users()
            await update.message.reply_text(f"{EMOJI_UNLOCK} User {new_user_id} has been authorized for {days} days.")
        except (IndexError, ValueError):
            await update.message.reply_text("Usage: /authorize `<user_id>` `<days>`")
    else:
        await update.message.reply_text(f"{EMOJI_LOCK} You are not authorized to use this command.")

async def proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        new_proxies = ' '.join(context.args).split(',')
        for proxy in new_proxies:
            parts = proxy.split(':')
            if len(parts) == 4:
                proxy = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            proxies.append(proxy)
        save_proxies()
        await update.message.reply_text(f"{EMOJI_GEAR} Proxies have been updated.")
    else:
        await update.message.reply_text(f"{EMOJI_LOCK} You are not authorized to use this command.")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        remove_proxies()
        await update.message.reply_text(f"{EMOJI_GEAR} All proxies have been removed.")
    else:
        await update.message.reply_text(f"{EMOJI_LOCK} You are not authorized to use this command.")

# Fetch URL and process search engine functions (unchanged)
async def fetch_url(session, url, proxy=None):
    try:
        async with session.get(url, headers={'User-Agent': ua.random}, proxy=proxy, timeout=10) as response:
            return await response.text()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

async def process_search_engine(session, search_engine, query, proxy=None):
    url = search_engine.replace('{dork_keywords}', query)
    html = await fetch_url(session, url, proxy)
    if html:
        if 'captcha' in html.lower():
            return None
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=True)
        return [link['href'] for link in links if link['href'].startswith('http')]
    return []

async def dork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"{EMOJI_LOCK} You are not authorized to use this bot.")
        return

    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text(f"{EMOJI_SEARCH} Usage: /dork `<query>`")
        return

    progress_message = await update.message.reply_text(f"{EMOJI_GEAR} Dorking in progress. Please wait...")

    result = []
    async with ClientSession() as session:
        tasks = []
        for search_engine in SEARCH_ENGINES:
            proxy = random.choice(proxies) if proxies else None
            tasks.append(process_search_engine(session, search_engine, query, proxy))
        
        results = await asyncio.gather(*tasks)
        for links in results:
            if links:
                result.extend(links)

    cleaned_links = list(dict.fromkeys(result))
    filtered_links = [link for link in cleaned_links if not any(keyword in link.lower() for keyword in WASTE_KEYWORDS)]

    if filtered_links:
        file_name = f"dork_results_{user_id}.txt"
        with open(file_name, 'w', encoding='utf8') as file:
            file.write('\n'.join(filtered_links))
        await update.message.reply_document(open(file_name, 'rb'), caption=f"{EMOJI_ROCKET} Here are your dork results!")
        os.remove(file_name)
    else:
        await update.message.reply_text(f"{EMOJI_SEARCH} No valid links found.")

    await progress_message.delete()

# Check functions (unchanged)
async def check_gateway(html):
    gateway_patterns = {
        'Stripe': r'stripe\.com|stripe\.js',
        'PayPal': r'paypal\.com|paypal-sdk',
        'Square': r'squareup\.com|square\.js',
        'Braintree': r'braintreegateway\.com|braintree-sdk',
        'Authorize.Net': r'authorize\.net|AcceptUI',
        'Adyen': r'adyen\.com|adyen\.js',
        'Worldpay': r'worldpay\.com|worldpay\.js',
        'Cybersource': r'cybersource\.com',
        'Shopify Payments': r'shopify\.com/payment',
        '2Checkout': r'2checkout\.com',
    }
    
    detected_gateways = []
    for gateway, pattern in gateway_patterns.items():
        if re.search(pattern, html, re.IGNORECASE):
            detected_gateways.append(gateway)
    
    return ', '.join(detected_gateways) if detected_gateways else 'Not detected'

async def check_graphql(html, url):
    graphql_patterns = [
        r'/graphql',
        r'graphql\.php',
        r'graphql-endpoint',
        r'ApolloClient',
        r'apollo-client',
        r'graphql-tag',
    ]
    
    for pattern in graphql_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return 'Detected'
    
    async with ClientSession() as session:
        try:
            graphql_url = f"{url.rstrip('/')}/graphql"
            async with session.post(graphql_url, json={"query": "{__schema{types{name}}}"}, timeout=5) as response:
                if response.status == 200:
                    return 'Detected (Active Endpoint)'
        except:
            pass
    
    return 'Not detected'

async def check_cloudflare(html):
    cloudflare_patterns = [
        r'cloudflare-nginx',
        r'__cfduid',
        r'cf-ray',
        r'cloudflare.com',
    ]
    
    for pattern in cloudflare_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return 'Yes'
    
    return 'No'

async def check_captcha(html):
    captcha_patterns = [
        r'recaptcha',
        r'hcaptcha',
        r'captcha\.js',
        r'captcha-api',
    ]
    
    for pattern in captcha_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return 'Yes'
    
    return 'No'

async def process_url(session, url):
    try:
        html = await fetch_url(session, url)
        if html:
            gateway = await check_gateway(html)
            graphql = await check_graphql(html, url)
            cloudflare = await check_cloudflare(html)
            captcha = await check_captcha(html)
            
            return (
                f"URL: {url}\n"
                f"Status: {'Active' if html else 'Inactive'}\n"
                f"Gateway: {gateway}\n"
                f"GraphQL: {graphql}\n"
                f"Cloudflare: {cloudflare}\n"
                f"Captcha: {captcha}\n"
                f"{'=' * 30}\n"
            )
        else:
            return f"Error processing {url}: Unable to fetch content\n{'=' * 30}\n"
    except Exception as e:
        return f"Error processing {url}: {str(e)}\n{'=' * 30}\n"

async def gates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"{EMOJI_LOCK} You are not authorized to use this bot.")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text(f"{EMOJI_CHART} Please reply to a file with /gates command.")
        return

    file = await context.bot.get_file(update.message.reply_to_message.document.file_id)
    file_path = await file.download_to_drive()

    with open(file_path, 'r') as f:
        urls = f.read().splitlines()

    progress_message = await update.message.reply_text(f"{EMOJI_GEAR} Processing gates. Please wait...")

    async with ClientSession() as session:
        tasks = [process_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    results_text = "".join(results)
    result_file = f"gate_results_{user_id}.txt"
    with open(result_file, 'w', encoding='utf8') as file:
        file.write(results_text)

    await update.message.reply_document(open(result_file, 'rb'), caption=f"{EMOJI_ROCKET} Here are your gate results!")
    os.remove(result_file)
    os.remove(file_path)
    await progress_message.delete()

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in authorized_users:
        expiry_date =   authorized_users[user_id].strftime('%Y-%m-%d')
        await update.message.reply_text(f"{EMOJI_ID} Your user ID: {user_id}\nAuthorized until: {expiry_date}")
    else:
        await update.message.reply_text(f"{EMOJI_ID} Your user ID: {user_id}\n{EMOJI_LOCK} You are not authorized to use this bot.")

def main():
    load_authorized_users()
    load_proxies()

    application = Application.builder().token("7280917209:AAFH8KViP6T3fqd92QKtMjtTwxH6EBre0qQ").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("authorize", authorize))
    application.add_handler(CommandHandler("proxy", proxy))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("dork", dork))
    application.add_handler(CommandHandler("gates", gates))
    application.add_handler(CommandHandler("id", user_info))
    application.add_handler(CallbackQueryHandler(menu_actions))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
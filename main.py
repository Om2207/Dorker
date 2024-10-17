import os
import re
import time
import random
import asyncio
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from fake_useragent import UserAgent
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote_plus

# Bot token (easy to change)
BOT_TOKEN = "7280917209:AAFH8KViP6T3fqd92QKtMjtTwxH6EBre0qQ"

# Constants
OWNER_ID = 6008343239
WASTE_KEYWORDS = [
    "google", "yahoo", "bing", "duckduckgo", "baidu", "yandex", "ask", "aol", "excite", "dogpile", "webcrawler",
    "search", "engine", "query", "results", "serp", "facebook", "twitter", "instagram", "linkedin", "youtube", 
    "tiktok", "reddit", "pinterest", "tumblr", "quora", "medium", "wordpress", "blogger", "amazon", "ebay", "etsy", 
    "alibaba", "shopify", "walmart", "target", "bestbuy", "paypal", "stripe", "square", "adyen", "worldpay", 
    "authorize.net", "2checkout", "skrill", "payoneer", "wepay", "amazon pay", "google pay", "apple pay", "venmo", 
    "transferwise", "paymentwall", "bluesnap", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", 
    "json", "xml", "microsoft", "apple", "ibm", "oracle", "salesforce", "adobe", "cisco", "intel", "dell", "hp",
    "advertisement", "sponsored", "promotion", "offer", "deal", "discount", "free", "trial", "copyright", "trademark", 
    "legal", "policy", "guidelines", "rules", "error", "404", "not found", "maintenance", "update", "upgrade",
    "mobile", "desktop", "app", "software", "hardware", "device",
]

SEARCH_ENGINES = [
    "https://duckduckgo.com/?q={dork_keywords}&t=h_&ia=web",
    "http://www.bing.com/search?q={dork_keywords}&count=50&first={page}",
    "https://search.yahoo.com/search?p={dork_keywords}&b={page}",
    "http://www.google.com/search?q={dork_keywords}&num=100&start={page}",
]

# User-agent
ua = UserAgent()

# Emojis for better visual appeal
EMOJI_ROCKET = "🚀"
EMOJI_LOCK = "🔒"
EMOJI_UNLOCK = "🔓"
EMOJI_GEAR = "⚙️"
EMOJI_SEARCH = "🔍"
EMOJI_CHART = "📊"
EMOJI_ID = "🆔"
EMOJI_COPY = "📋"

# Database setup
def setup_database():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expiry_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proxy TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Database operations
def add_user(user_id, expiry_date):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, expiry_date) VALUES (?, ?)', (user_id, expiry_date.strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT expiry_date FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0]:
        try:
            return datetime.strptime(result[0], '%Y-%m-%d')
        except ValueError:
            return None
    return None

def add_proxy(proxy):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO proxies (proxy) VALUES (?)', (proxy,))
    conn.commit()
    conn.close()

def get_proxies():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT proxy FROM proxies')
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

def remove_all_proxies():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM proxies')
    conn.commit()
    conn.close()

# Helper functions
def is_authorized(user_id):
    expiry_date = get_user(user_id)
    return expiry_date and expiry_date >= datetime.now()

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
        welcome_message = f"{EMOJI_ROCKET} <b>Welcome, Master!</b>\n\nWhat would you like to do today?"
    elif is_authorized(user_id):
        welcome_message = f"{EMOJI_ROCKET} <b>Welcome to DorkMaster 3000!</b>\n\nWhat would you like to do today?"
    else:
        welcome_message = f"{EMOJI_LOCK} You are not authorized to use this bot. Please contact the owner."
        await update.message.reply_text(welcome_message, parse_mode='HTML')
        return

    await update.message.reply_text(welcome_message, reply_markup=create_menu_keyboard(), parse_mode='HTML')

async def menu_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'dork':
        await query.message.reply_text(f"{EMOJI_SEARCH} Please enter your dork query:\n\nExample: <code>/dork Shopify+lipstick</code>", parse_mode='HTML')
    elif query.data == 'gates':
        await query.message.reply_text(f"{EMOJI_CHART} Please upload a file with URLs to check, then reply to it with /gates")
    elif query.data == 'id':
        await user_info(update, context, is_callback=True)

async def authorize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        try:
            new_user_id = int(context.args[0])
            days = int(context.args[1])
            expiry_date = datetime.now() + timedelta(days=days)
            add_user(new_user_id, expiry_date)
            await update.message.reply_text(f"{EMOJI_UNLOCK} User {new_user_id} has been authorized for {days} days.")
            
            # Notify the authorized user
            try:
                await context.bot.send_message(
                    chat_id=new_user_id,
                    text=f"{EMOJI_UNLOCK} You have been authorized to use DorkMaster 3000 for {days} days! Use /start to begin.",
                    parse_mode='HTML'
                )
            except Exception as e:
                await update.message.reply_text(f"Authorized successfully, but failed to notify the user: {str(e)}")
        except (IndexError, ValueError):
            await update.message.reply_text("Usage: /authorize <user_id> <days>")
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}")
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
            add_proxy(proxy)
        await update.message.reply_text(f"{EMOJI_GEAR} Proxies have been updated.")
    else:
        await update.message.reply_text(f"{EMOJI_LOCK} You are not authorized to use this command.")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == OWNER_ID:
        remove_all_proxies()
        await update.message.reply_text(f"{EMOJI_GEAR} All proxies have been removed.")
    else:
        await update.message.reply_text(f"{EMOJI_LOCK} You are not authorized to use this command.")

async def fetch_url(session, url, proxy=None):
    try:
        async with session.get(url, headers={'User-Agent': ua.random}, proxy=proxy, timeout=10) as response:
            return await response.text()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

async def process_search_engine(session, search_engine, query, page, proxy=None):
    url = search_engine.replace('{dork_keywords}', quote_plus(query)).replace('{page}', str(page))
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
        await update.message.reply_text(f"{EMOJI_SEARCH} Usage: /dork <query>")
        return

    progress_message = await update.message.reply_text(f"{EMOJI_GEAR} Dorking in progress. Please wait...")

    result = []
    async with ClientSession() as session:
        tasks = []
        proxies = get_proxies()
        for search_engine in SEARCH_ENGINES:
            for page in range(0, 300, 10):  # Adjusted to potentially get up to 3000 links (100 per page * 30 pages)
                proxy = random.choice(proxies) if proxies else None
                tasks.append(process_search_engine(session, search_engine, query, page, proxy))
        
        results = await asyncio.gather(*tasks)
        for links in results:
            if links:
                result.extend(links)
                if len(result) >= 3000:
                    break
        result = result[:3000]  # Ensure we don't exceed 3000 links

    cleaned_links = list(dict.fromkeys(result))
    
    # More stringent filtering
    filtered_links = []
    for link in cleaned_links:
        if not any(keyword in link.lower() for keyword in WASTE_KEYWORDS):
            parsed_url = urlparse(link)
            if parsed_url.scheme in ['http', 'https'] and parsed_url.netloc:
                if not any(search_domain in parsed_url.netloc for search_domain in ['google', 'yahoo', 'bing', 'duckduckgo']):
                    filtered_links.append(link)

    if filtered_links:
        file_name = f"dork_results_{user_id}.txt"
        with open(file_name, 'w', encoding='utf8') as file:
            file.write('\n'.join(filtered_links))
        await update.message.reply_document(open(file_name, 'rb'), caption=f"{EMOJI_ROCKET} Here are your filtered dork results ({len(filtered_links)} links)!")
        os.remove(file_name)
    else:
        await update.message.reply_text(f"{EMOJI_SEARCH} No valid links found after filtering.")

    await progress_message.delete()

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
        'USAePay': r'usaepay\.com',
        'Epoch': r'epoch\.com',
        'RocketPay': r'rocketpay\.com',
        'CCBill': r'ccbill\.com',
        'Skrill': r'skrill\.com',
        'BlueSnap': r'bluesnap\.com',
        'Paysafe': r'paysafe\.com',
        'Wirecard': r'wirecard\.com',
        'Klarna': r'klarna\.com',
        'Sage Pay': r'sagepay\.com',
        'Nets': r'nets\.eu',
        'Elavon': r'elavon\.com',
        'First Data': r'firstdata\.com',
        'Global Payments': 

 r'globalpayments\.com',
        'Ingenico': r'ingenico\.com',
        'Verifone': r'verifone\.com',
        'Cardstream': r'cardstream\.com',
        'Checkout.com': r'checkout\.com',
        'Dwolla': r'dwolla\.com',
        'GoCardless': r'gocardless\.com',
        'Mollie': r'mollie\.com',
        'Payoneer': r'payoneer\.com',
        'Paysera': r'paysera\.com',
        'Razorpay': r'razorpay\.com',
        'Stripe Connect': r'stripe\.com/connect',
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

    if update.message.reply_to_message and update.message.reply_to_message.document:
        # Process file
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
    else:
        # Process single URL
        url = ' '.join(context.args)
        if not url:
            await update.message.reply_text(f"{EMOJI_CHART} Please provide a URL to check. Usage: /gates <url>")
            return

        progress_message = await update.message.reply_text(f"{EMOJI_GEAR} Processing gate. Please wait...")

        async with ClientSession() as session:
            result = await process_url(session, url)

        await update.message.reply_text(result, parse_mode='HTML')
        await progress_message.delete()

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    if is_callback:
        user_id = update.callback_query.from_user.id
        message = update.callback_query.message
    else:
        user_id = update.message.from_user.id
        message = update.message

    expiry_date = get_user(user_id)
    if expiry_date:
        await message.reply_text(
            f"{EMOJI_ID} Your user ID: <code>{user_id}</code>\n"
            f"Authorized until: {expiry_date.strftime('%Y-%m-%d')}\n\n"
            f"{EMOJI_COPY} Copy your ID by tapping the code above.",
            parse_mode='HTML'
        )
    else:
        await message.reply_text(
            f"{EMOJI_ID} Your user ID: <code>{user_id}</code>\n"
            f"{EMOJI_LOCK} You are not authorized to use this bot.\n\n"
            f"{EMOJI_COPY} Copy your ID by tapping the code above.",
            parse_mode='HTML'
        )

def main():
    setup_database()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("authorize", authorize))
    application.add_handler(CommandHandler("proxy", proxy))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("dork", dork))
    application.add_handler(CommandHandler("gates", gates))
    application.add_handler(CommandHandler("id", lambda update, context: user_info(update, context, is_callback=False)))
    application.add_handler(CallbackQueryHandler(menu_actions))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
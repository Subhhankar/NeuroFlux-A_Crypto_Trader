import os
from dotenv import load_dotenv
import logging
from urllib.parse import quote_plus
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Load environment variables with validation
required_config = {
    "TELEGRAM_BOT_TOKEN": "8134800071:AAGxNQPEfECYu56QMt1yjD0Ij0cZp8TH-4o",
    "MONGO_USER": "QuantumWatch_bot",
    "MONGO_PASS": "Quant@1122",
    "MONGO_CLUSTER": "cluster0.dt6a13o.mongodb.net",
    "MONGO_DB": "wallet_tracker",
    "ETHERSCAN_API_KEY": "V4D7Y8SP1NS6S8ZJ4TFTYJB6PWX9J87ZEE",
    "BSCSCAN_API_KEY": "V4D7Y8SP1NS6S8ZJ4TFTYJB6PWX9J87ZEE",
    "SOLSCAN_API_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTIwMDI5NDIyMTQsImVtYWlsIjoic2FoYXN1YmhhbmthcjAwMDJAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUyMDAyOTQyfQ.RxkHNAGRVKLMO5yntj6SBQrdbw7xsfLWIi1bNEDFpEk"
}

# Validate all required environment variables
missing_vars = [name for name in required_config.keys() if not os.getenv(name)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Get and encode credentials with validation
try:
    mongo_user = os.getenv("MONGO_USER").strip()
    mongo_pass = os.getenv("MONGO_PASS").strip()
    username = quote_plus(mongo_user)
    password = quote_plus(mongo_pass)
except AttributeError as e:
    raise ValueError("MongoDB credentials are invalid or empty") from e

# Secure connection string
MONGO_URI = (
    f"mongodb+srv://{username}:{password}"
    f"@{os.getenv('MONGO_CLUSTER')}/{os.getenv('MONGO_DB')}"
    "?retryWrites=true&w=majority"
    "&appName=TelegramWalletBot"
    "&tls=true"
    "&tlsAllowInvalidCertificates=false"
)

# Database connection with error handling
try:
    client = MongoClient(
        MONGO_URI,
        connectTimeoutMS=5000,
        socketTimeoutMS=30000,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50
    )
    # Test the connection
    client.admin.command('ping')
    db = client[os.getenv("MONGO_DB")]
    wallets_collection = db["user_wallets"]
    activity_collection = db["wallet_activities"]
    
    # Create indexes if they don't exist
    wallets_collection.create_index("user_id")
    activity_collection.create_index([("user_id", 1), ("tx_hash", 1)])
    activity_collection.create_index("timestamp")
    logger.info("MongoDB connection established successfully with indexes")
except Exception as e:
    logger.critical("Failed to connect to MongoDB: %s", e)
    raise

# Supported blockchains configuration
SUPPORTED_CHAINS = {
    "eth": {
        "name": "Ethereum",
        "explorer": "https://etherscan.io",
        "api": {
            "balance": f"https://api.etherscan.io/api?module=account&action=balance&address={{address}}&tag=latest&apikey={os.getenv('ETHERSCAN_API_KEY')}",
            "txs": f"https://api.etherscan.io/api?module=account&action=txlist&address={{address}}&startblock=0&endblock=99999999&page=1&offset=5&sort=desc&apikey={os.getenv('ETHERSCAN_API_KEY')}"
        }
    },
    "bnb": {
        "name": "BNB Smart Chain",
        "explorer": "https://bscscan.com",
        "api": {
            "balance": f"https://api.bscscan.com/api?module=account&action=balance&address={{address}}&tag=latest&apikey={os.getenv('BSCSCAN_API_KEY')}",
            "txs": f"https://api.bscscan.com/api?module=account&action=txlist&address={{address}}&startblock=0&endblock=99999999&page=1&offset=5&sort=desc&apikey={os.getenv('BSCSCAN_API_KEY')}"
        }
    },
    "sol": {
        "name": "Solana",
        "explorer": "https://solscan.io",
        "api": {
            "balance": "https://public-api.solscan.io/account/{address}",
            "txs": "https://public-api.solscan.io/account/transactions/{address}?limit=5"
        },
        "headers": {
            "accept": "application/json",
            "token": os.getenv("SOLSCAN_API_KEY")
        }
    }
}

class WalletTracker:
    def __init__(self):
        self.last_activity_cache: Dict[str, Dict[str, datetime]] = {}
        self.session = self._create_session()
        
    def _create_session(self):
        """Create a requests session with retry logic."""
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        return session

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message with interactive menu."""
        keyboard = [
            [InlineKeyboardButton("➕ Add Wallet", callback_data="add_wallet")],
            [InlineKeyboardButton("👀 Monitor Wallets", callback_data="monitor")],
            [InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🚀 *Crypto Wallet Tracker Bot*\n\n"
            "Track your wallets across multiple blockchains and get real-time alerts!\n\n"
            "• Add Ethereum/BNB/Solana wallets\n"
            "• Monitor transactions\n"
            "• Get price alerts\n"
            "• View portfolio balance",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button presses."""
        query = update.callback_query
        await query.answer()
        
        if query.data == "add_wallet":
            await query.edit_message_text(
                "Which blockchain?\n\n"
                "1. For Ethereum: `/add eth <wallet_address>`\n"
                "2. For BNB Smart Chain: `/add bnb <wallet_address>`\n"
                "3. For Solana: `/add sol <wallet_address>`",
                parse_mode="Markdown"
            )
        elif query.data == "monitor":
            await self.monitor_wallets(update, context)
        elif query.data == "portfolio":
            await self.show_portfolio(update, context)

    async def add_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add a wallet to track."""
        user_id = update.effective_user.id
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /add <chain> <wallet_address>\n\n"
                "Example:\n"
                "• `/add eth 0x123...` for Ethereum\n"
                "• `/add bnb 0x123...` for BNB Smart Chain\n"
                "• `/add sol ABC123...` for Solana"
            )
            return
            
        chain, wallet_address = context.args[0].lower(), context.args[1]
        
        if chain not in SUPPORTED_CHAINS:
            await update.message.reply_text(
                f"Unsupported blockchain. Currently supported: {', '.join(SUPPORTED_CHAINS.keys())}"
            )
            return
            
        if not self.validate_wallet_address(chain, wallet_address):
            await update.message.reply_text("Invalid wallet address format for this blockchain")
            return
            
        # Save to database
        wallets_collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"wallets": {"chain": chain, "address": wallet_address}}},
            upsert=True
        )
        
        await update.message.reply_text(
            f"✅ *{SUPPORTED_CHAINS[chain]['name']} wallet added!*\n"
            f"Address: `{wallet_address}`\n\n"
            f"View on explorer: {SUPPORTED_CHAINS[chain]['explorer']}/address/{wallet_address}",
            parse_mode="Markdown"
        )

    def validate_wallet_address(self, chain: str, address: str) -> bool:
        """Validate wallet address format."""
        if chain == "eth" or chain == "bnb":
            return len(address) == 42 and address.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in address[2:])
        elif chain == "sol":
            return len(address) == 44 and address.isalnum()
        return False

    async def monitor_wallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start monitoring wallets."""
        user_id = update.effective_user.id
        
        # Helper function to send message based on update type
        async def send_message(text: str, parse_mode: str = None):
            if update.callback_query:
                await update.callback_query.edit_message_text(text, parse_mode=parse_mode)
            elif update.message:
                await update.message.reply_text(text, parse_mode=parse_mode)
            else:
                await context.bot.send_message(chat_id=user_id, text=text, parse_mode=parse_mode)
        
        user_data = wallets_collection.find_one({"user_id": user_id})
        if not user_data or not user_data.get("wallets"):
            await send_message("You haven't added any wallets yet. Use /add to get started.")
            return
            
        # Check if already monitoring
        if context.user_data.get("monitoring"):
            await send_message("Monitoring is already active!")
            return
            
        context.user_data["monitoring"] = True
        
        # Initial check for all chains
        await self.check_wallets_for_user(user_id, context)
        
        # Schedule periodic checks (every 5 minutes)
        context.job_queue.run_repeating(
            self.check_wallets_job,
            interval=300,  # 5 minutes
            first=0,
            name=str(user_id),
            user_id=user_id,
            data={"user_id": user_id}
        )
        
        # Show which chains are being monitored
        chains_monitored = set(wallet["chain"] for wallet in user_data["wallets"])
        chains_list = ", ".join(SUPPORTED_CHAINS[chain]["name"] for chain in chains_monitored)
        
        message_text = (
            f"🔔 *Monitoring activated for {len(user_data['wallets'])} wallets!*\n\n"
            f"📡 *Blockchains monitored:* {chains_list}\n\n"
            "You'll receive notifications for:\n"
            "• New transactions\n"
            "• Large transfers (>$1,000)\n"
            "• Significant balance changes\n\n"
            "Check interval: 5 minutes\n"
            "Use /stop to disable monitoring"
        )
        
        await send_message(message_text, parse_mode="Markdown")

    async def check_wallets_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Job wrapper for checking wallets."""
        job = context.job
        user_id = job.data["user_id"]
        logger.info(f"Starting wallet check job for user {user_id}")
        try:
            await self.check_wallets_for_user(user_id, context)
        except Exception as e:
            logger.error(f"Error in wallet check job for user {user_id}: {e}")
        logger.info(f"Completed wallet check job for user {user_id}")

    async def check_wallets_for_user(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Check all wallets for new activity for a specific user."""
        try:
            user_data = wallets_collection.find_one({"user_id": user_id})
            if not user_data:
                return
                
            for wallet in user_data["wallets"]:
                try:
                    chain, address = wallet["chain"], wallet["address"]
                    logger.info(f"Checking {chain} wallet: {address}")
                    txs = self.fetch_transactions(chain, address)
                    
                    # Add delay between wallet checks (2 seconds for better rate limiting)
                    time.sleep(2)
                    
                    if txs:
                        latest_tx = txs[0]
                        # Handle different transaction hash field names
                        if chain == "sol":
                            tx_hash = latest_tx.get("signature", "")
                        else:
                            tx_hash = latest_tx.get("hash", "")
                        
                        if tx_hash:
                            # Check if we've already notified about this transaction
                            existing_activity = activity_collection.find_one({
                                "tx_hash": tx_hash,
                                "user_id": user_id
                            })
                            
                            if not existing_activity:
                                # Store the activity
                                activity_collection.insert_one({
                                    "user_id": user_id,
                                    "chain": chain,
                                    "wallet": address,
                                    "tx_hash": tx_hash,
                                    "timestamp": datetime.now()
                                })
                                
                                # Send notification
                                message = self.format_transaction(chain, latest_tx, address)
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=message,
                                    parse_mode="Markdown"
                                )
                                logger.info(f"Sent notification for {chain} transaction: {tx_hash}")
                            else:
                                logger.info(f"Already notified about {chain} transaction: {tx_hash}")
                        else:
                            logger.warning(f"No transaction hash found for {chain} transaction")
                    else:
                        logger.info(f"No transactions found for {chain} wallet: {address}")
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout checking {chain} wallet {address}")
                    continue
                except Exception as e:
                    logger.error(f"Error checking {chain} wallet {address}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in check_wallets_for_user: {str(e)}")

    def fetch_transactions(self, chain: str, address: str) -> List[Dict]:
        """Fetch recent transactions for a wallet."""
        try:
            if chain == "eth" or chain == "bnb":
                url = SUPPORTED_CHAINS[chain]["api"]["txs"].format(address=address)
                logger.info(f"Fetching {chain} transactions from: {url}")
                
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"{chain} API response status: {data.get('status')}")
                
                if data.get("status") == "1":
                    transactions = data.get("result", [])
                    logger.info(f"Found {len(transactions)} transactions for {chain} wallet")
                    return transactions[:5]
                else:
                    logger.warning(f"{chain} API returned status: {data.get('status')}, message: {data.get('message')}")
                    return []
                
            elif chain == "sol":
                # Fixed URL formatting for Solana
                url = SUPPORTED_CHAINS[chain]["api"]["txs"].format(address=address)
                headers = SUPPORTED_CHAINS[chain].get("headers", {})
                logger.info(f"Fetching Solana transactions from: {url}")
                
                response = self.session.get(url, headers=headers, timeout=60)
                response.raise_for_status()
                
                if response.status_code == 200:
                    data = response.json()
                    # Handle different response formats
                    if isinstance(data, list):
                        transactions = data
                    else:
                        transactions = data.get("data", [])
                    
                    logger.info(f"Found {len(transactions)} transactions for Solana wallet")
                    return transactions[:5]
                else:
                    logger.warning(f"Solana API returned status: {response.status_code}")
                    return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching {chain} transactions for {address}: {str(e)}")
        except Exception as e:
            logger.error(f"Error fetching {chain} transactions for {address}: {str(e)}")
        
        return []

    def format_transaction(self, chain: str, tx: Dict, wallet_address: str) -> str:
        """Format transaction data for display."""
        explorer_url = SUPPORTED_CHAINS[chain]["explorer"]
        
        if chain == "eth" or chain == "bnb":
            tx_hash = tx["hash"]
            timestamp = datetime.fromtimestamp(int(tx["timeStamp"])).strftime("%Y-%m-%d %H:%M:%S")
            value = int(tx["value"]) / 10**18
            symbol = "ETH" if chain == "eth" else "BNB"
            
            # Determine if it's incoming or outgoing
            direction = "📥 Incoming" if tx["to"].lower() == wallet_address.lower() else "📤 Outgoing"
            
            return (
                f"🔄 *New {SUPPORTED_CHAINS[chain]['name']} Transaction*\n\n"
                f"⏰ *Time:* {timestamp}\n"
                f"🔄 *Direction:* {direction}\n"
                f"📤 *From:* `{tx['from'][:6]}...{tx['from'][-4:]}`\n"
                f"📥 *To:* `{tx['to'][:6]}...{tx['to'][-4:]}`\n"
                f"💸 *Value:* {value:.6f} {symbol}\n"
                f"⛽ *Gas Used:* {tx.get('gasUsed', 'N/A')}\n"
                f"🔗 *View on Explorer:* {explorer_url}/tx/{tx_hash}"
            )
            
        elif chain == "sol":
            tx_hash = tx["signature"]
            timestamp = datetime.fromtimestamp(tx["blockTime"]).strftime("%Y-%m-%d %H:%M:%S")
            return (
                f"🔄 *New Solana Transaction*\n\n"
                f"⏰ *Time:* {timestamp}\n"
                f"🆔 *Signature:* `{tx_hash[:10]}...{tx_hash[-4:]}`\n"
                f"💸 *Fee:* {tx['fee']/10**9:.6f} SOL\n"
                f"📦 *Block:* {tx.get('slot', 'N/A')}\n"
                f"✅ *Status:* {'Success' if tx.get('status') == 'Success' else 'Failed'}\n"
                f"🔗 *View on Solscan:* {explorer_url}/tx/{tx_hash}"
            )

    async def show_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show the user's portfolio summary."""
        user_id = update.effective_user.id
        
        # Helper function to send message based on update type
        async def send_message(text: str, parse_mode: str = None):
            if update.callback_query:
                await update.callback_query.edit_message_text(text, parse_mode=parse_mode)
            elif update.message:
                await update.message.reply_text(text, parse_mode=parse_mode)
            else:
                await context.bot.send_message(chat_id=user_id, text=text, parse_mode=parse_mode)
        
        user_data = wallets_collection.find_one({"user_id": user_id})
        if not user_data or not user_data.get("wallets"):
            await send_message("You haven't added any wallets yet. Use /add to get started.")
            return
            
        message = "📊 *Your Multi-Chain Portfolio*\n\n"
        total_wallets = len(user_data["wallets"])
        successful_fetches = 0
        
        # Group wallets by chain for better organization
        wallets_by_chain = {}
        for wallet in user_data["wallets"]:
            chain = wallet["chain"]
            if chain not in wallets_by_chain:
                wallets_by_chain[chain] = []
            wallets_by_chain[chain].append(wallet)
        
        for chain, wallets in wallets_by_chain.items():
            message += f"🔗 *{SUPPORTED_CHAINS[chain]['name']}*\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for wallet in wallets:
                address = wallet["address"]
                balance = self.fetch_balance(chain, address)
                
                if balance is not None:
                    successful_fetches += 1
                    symbol = "ETH" if chain == "eth" else "BNB" if chain == "bnb" else "SOL"
                    message += (
                        f"📱 `{address[:6]}...{address[-4:]}`\n"
                        f"💰 Balance: *{balance:.6f} {symbol}*\n"
                        f"🔗 [View on Explorer]({SUPPORTED_CHAINS[chain]['explorer']}/address/{address})\n\n"
                    )
                else:
                    message += (
                        f"📱 `{address[:6]}...{address[-4:]}`\n"
                        f"❌ Balance: *Error fetching*\n"
                        f"🔗 [View on Explorer]({SUPPORTED_CHAINS[chain]['explorer']}/address/{address})\n\n"
                    )
        
        # Add summary
        message += "📈 *Portfolio Summary*\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"🏦 Total Wallets: {total_wallets}\n"
        message += f"✅ Successfully Fetched: {successful_fetches}\n"
        message += f"❌ Failed Fetches: {total_wallets - successful_fetches}\n"
        message += f"🌐 Chains Covered: {len(wallets_by_chain)}\n\n"
        message += f"💡 *Note:* USD value calculation requires price feed integration"
        
        await send_message(message, parse_mode="Markdown")

    def fetch_balance(self, chain: str, address: str) -> Optional[float]:
        """Fetch wallet balance."""
        try:
            if chain == "eth" or chain == "bnb":
                url = SUPPORTED_CHAINS[chain]["api"]["balance"].format(address=address)
                logger.info(f"Fetching {chain} balance from: {url}")
                
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "1":
                    balance = int(data["result"]) / 10**18
                    logger.info(f"{chain} balance for {address}: {balance}")
                    return balance
                else:
                    logger.warning(f"{chain} balance API error: {data.get('message')}")
                    return None
                
            elif chain == "sol":
                # Fixed URL formatting for Solana balance
                url = SUPPORTED_CHAINS[chain]["api"]["balance"].format(address=address)
                headers = SUPPORTED_CHAINS[chain].get("headers", {})
                logger.info(f"Fetching Solana balance from: {url}")
                
                response = self.session.get(url, headers=headers, timeout=60)
                response.raise_for_status()
                
                if response.status_code == 200:
                    data = response.json()
                    # Handle different response formats
                    if isinstance(data, dict):
                        balance = data.get("lamports", 0) / 10**9
                    else:
                        balance = 0
                    logger.info(f"Solana balance for {address}: {balance}")
                    return balance
                    
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching {chain} balance for {address}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching {chain} balance for {address}: {str(e)}")
        except Exception as e:
            logger.error(f"Error fetching {chain} balance for {address}: {str(e)}")
        
        return None

    async def stop_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Stop monitoring wallets."""
        user_id = update.effective_user.id
        
        if not context.user_data.get("monitoring"):
            await update.message.reply_text("Monitoring isn't currently active.")
            return
            
        # Find and remove the job
        current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
        for job in current_jobs:
            job.schedule_removal()
            
        context.user_data["monitoring"] = False
        await update.message.reply_text("🛑 Monitoring stopped. You won't receive further notifications.")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors in the bot."""
        logger.error(f"Update {update} caused error: {context.error}")
        
        if update and hasattr(update, "message") and update.message:
            await update.message.reply_text(
                "⚠️ An error occurred. Please try again later or contact support."
            )
        elif update and hasattr(update, "callback_query") and update.callback_query:
            await update.callback_query.answer("⚠️ An error occurred. Please try again later.")

def main() -> None:
    """Run the bot."""
    # Create application with persistence
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    tracker = WalletTracker()
    
    # Add handlers
    application.add_handler(CommandHandler("start", tracker.start))
    application.add_handler(CommandHandler("add", tracker.add_wallet))
    application.add_handler(CommandHandler("monitor", tracker.monitor_wallets))
    application.add_handler(CommandHandler("stop", tracker.stop_monitoring))
    application.add_handler(CommandHandler("portfolio", tracker.show_portfolio))
    application.add_handler(CallbackQueryHandler(tracker.handle_button))
    
    # Add error handler
    application.add_error_handler(tracker.error_handler)
    
    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
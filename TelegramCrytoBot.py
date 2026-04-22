import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, Set, List, Optional, Tuple
import logging
from dataclasses import dataclass
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Supported chains configuration
SUPPORTED_CHAINS = {
    1: {
        'name': 'Ethereum Mainnet',
        'symbol': 'ETH',
        'explorer': 'https://etherscan.io'
    },
    56: {
        'name': 'BNB Smart Chain',
        'symbol': 'BNB',
        'explorer': 'https://bscscan.com'
    },
    137: {
        'name': 'Polygon Mainnet',
        'symbol': 'MATIC',
        'explorer': 'https://polygonscan.com'
    },
    42161: {
        'name': 'Arbitrum One',
        'symbol': 'ETH',
        'explorer': 'https://arbiscan.io'
    },
    42170: {
        'name': 'Arbitrum Nova',
        'symbol': 'ETH',
        'explorer': 'https://nova.arbiscan.io'
    },
    43114: {
        'name': 'Avalanche C-Chain',
        'symbol': 'AVAX',
        'explorer': 'https://snowtrace.io'
    },
    33139: {
        'name': 'ApeChain Mainnet',
        'symbol': 'APE',
        'explorer': 'https://apescan.io/'
    },
    8453: {
        'name': 'Base Mainnet',
        'symbol': 'BASE',
        'explorer': 'https://basescan.org/'
    },
    80094: {
        'name': 'Berachain Mainnet',
        'symbol': 'BERA',
        'explorer': 'https://berascan.com/'
    },
    199: {
        'name': 'BitTorrent Chain Mainnet',
        'symbol': 'BTT',
        'explorer': 'https://bttcscan.com/'
    },
    81457: {
        'name': 'Blast Mainnet',
        'symbol': 'BLAST',
        'explorer': 'https://blastscan.io/'
    },
    42220: {
        'name': 'Celo Mainnet',
        'symbol': 'CELO',
        'explorer': 'https://celoscan.io/'
    },
    25: {
        'name': 'Cronos Mainnet',
        'symbol': 'CRO',
        'explorer': 'https://cronoscan.com/'
    },
    252: {
        'name': 'Fraxtal Mainnet',
        'symbol': 'frxETH',
        'explorer': 'https://etherscan.io'
    },
    100: {
        'name': 'Gnosis',
        'symbol': 'GNO',
        'explorer': 'https://etherscan.io'
    },
    999: {
        'name': 'HyperEVM',
        'symbol': 'HYPE',
        'explorer': 'https://hyperevmscan.io/'
    },
    59144: {
        'name': 'Linea Mainnet',
        'symbol': 'LIN',
        'explorer': 'https://etherscan.io'
    },
    5000: {
        'name': 'Mantle Mainnet',
        'symbol': 'MNT',
        'explorer': 'https://mantlescan.xyz/'
    },
    4352: {
        'name': 'Memecore Mainnet',
        'symbol': 'MEME',
        'explorer': 'https://memecorescan.io/'
    },
    1284: {
        'name': 'Moonbeam Mainnet',
        'symbol': 'GLMR',
        'explorer': 'https://moonscan.io/'
    },
    1285: {
        'name': 'Moonriver Mainnet',
        'symbol': 'MOVR',
        'explorer': 'https://moonriver.moonscan.io/'
    },
    10: {
        'name': 'OP Mainnet',
        'symbol': 'OP',
        'explorer': 'https://optimistic.etherscan.io/'
    },
    747474: {
        'name': 'Katana Mainnet',
        'symbol': 'KAT',
        'explorer': 'https://etherscan.io'
    },
    534352: {
        'name': 'Scroll Mainnet',
        'symbol': 'SCR',
        'explorer': 'https://scrollscan.com/'
    },
    146: {
        'name': 'Sonic Mainnet',
        'symbol': 'S',
        'explorer': 'https://sonicscan.org/'
    },
    50104: {
        'name': 'Sophon Mainnet',
        'symbol': 'SOPH',
        'explorer': 'https://etherscan.io'
    },
    1923: {
        'name': 'Swellchain Mainnet',
        'symbol': 'SW',
        'explorer': 'https://swellchainscan.io/'
    },
    167000: {
        'name': 'Taiko Mainnet',
        'symbol': 'TK',
        'explorer': 'https://taikoscan.io/'
    },
    130: {
        'name': 'Unichain Mainnet',
        'symbol': 'UNI',
        'explorer': 'https://etherscan.io'
    },
    1111: {
        'name': 'WEMIX3.0 Mainnet',
        'symbol': 'WEMIX',
        'explorer': 'https://wemixscan.com/'
    },
    480: {
        'name': 'World Mainnet',
        'symbol': 'WORLD',
        'explorer': 'https://worldscan.org/'
    },
    660279: {
        'name': 'Xai Mainnet',
        'symbol': 'XAI',
        'explorer': 'https://xaiscan.io/'
    },
    324: {
        'name': 'zkSync Mainnet',
        'symbol': 'ZKS',
        'explorer': 'https://etherscan.io'
    },
    204: {
        'name': 'opBNB Mainnet',
        'symbol': 'opBNB',
        'explorer': 'https://opbnbscan.com/'
    },
    'solana': {
        'name': 'Solana',
        'symbol': 'SOL',
        'explorer': 'https://explorer.solana.com',
        'chain_id': 'solana'
    }

}

@dataclass
class Transaction:
    hash: str
    from_address: str
    to_address: str
    value: str
    token_symbol: str
    token_name: str
    token_decimal: int
    gas_used: str
    gas_price: str
    timestamp: int
    block_number: str
    is_token_transfer: bool
    chain_id: str
    contract_address: str = ""

class MultiChainEtherscanAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = {
            "ethereum":"https://api.etherscan.io",
            "solana":"https://pro-api.solscan.io/v2.0"
        }
        self.session = None
    
    async def create_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    def get_chain_info(self, chain_id: int) -> Dict:
        """Get chain information"""
        return SUPPORTED_CHAINS.get(chain_id, SUPPORTED_CHAINS[1])
    
    async def get_latest_transactions(self, address: str, chain_id: int = 1, limit: int = 10) -> List[Transaction]:
        """Get latest normal transactions for an address on specified chain"""
        await self.create_session()
        
        # For Ethereum mainnet, use the original API
        if chain_id == 1:
            url = f"{self.base_url}/api"
        else:
            url = f"{self.base_url}/v2/api"
        
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': address,
            'startblock': 0,
            'endblock': 99999999,
            'page': 1,
            'offset': limit,
            'sort': 'desc',
            'apikey': self.api_key
        }
        
        # Add chainid for v2 API
        if chain_id != 1:
            params['chainid'] = chain_id
        
        try:
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                
                if data['status'] == '1':
                    transactions = []
                    chain_info = self.get_chain_info(chain_id)
                    
                    for tx in data['result']:
                        # Convert from wei to native token (ETH, BNB, MATIC, etc.)
                        value = str(int(tx['value']) / 10**18) if tx['value'] else "0"
                        
                        transactions.append(Transaction(
                            hash=tx['hash'],
                            from_address=tx['from'],
                            to_address=tx['to'],
                            value=value,
                            token_symbol=chain_info['symbol'],
                            token_name=chain_info['name'],
                            token_decimal=18,
                            gas_used=tx['gasUsed'],
                            gas_price=tx['gasPrice'],
                            timestamp=int(tx['timeStamp']),
                            block_number=tx['blockNumber'],
                            is_token_transfer=False,
                            chain_id=chain_id
                        ))
                    return transactions
                return []
        except Exception as e:
            logger.error(f"Error fetching transactions for chain {chain_id}: {e}")
            return []
    
    async def get_token_transactions(self, address: str, chain_id: int = 1, limit: int = 10) -> List[Transaction]:
        """Get latest token transactions for an address on specified chain"""
        await self.create_session()
        
        # For Ethereum mainnet, use the original API
        if chain_id == 1:
            url = f"{self.base_url}/api"
        else:
            url = f"{self.base_url}/v2/api"
        
        params = {
            'module': 'account',
            'action': 'tokentx',
            'address': address,
            'startblock': 0,
            'endblock': 99999999,
            'page': 1,
            'offset': limit * 2,  # Get more to ensure we don't miss any
            'sort': 'desc',
            'apikey': self.api_key
        }
        
        # Add chainid for v2 API
        if chain_id != 1:
            params['chainid'] = chain_id
        
        try:
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                
                if data['status'] == '1':
                    transactions = []
                    for tx in data['result']:
                        decimal = int(tx['tokenDecimal']) if tx['tokenDecimal'] else 18
                        value = int(tx['value']) / (10 ** decimal) if tx['value'] else 0
                        
                        transactions.append(Transaction(
                            hash=tx['hash'],
                            from_address=tx['from'],
                            to_address=tx['to'],
                            value=str(value),
                            token_symbol=tx['tokenSymbol'],
                            token_name=tx['tokenName'],
                            token_decimal=decimal,
                            gas_used=tx['gasUsed'],
                            gas_price=tx['gasPrice'],
                            timestamp=int(tx['timeStamp']),
                            block_number=tx['blockNumber'],
                            is_token_transfer=True,
                            chain_id=chain_id,
                            contract_address=tx['contractAddress']
                        ))
                    return transactions
                return []
        except Exception as e:
            logger.error(f"Error fetching token transactions for chain {chain_id}: {e}")
            return []
    
    async def get_all_transactions(self, address: str, chain_id: int = 1, limit: int = 10) -> List[Transaction]:
        """Get both normal and token transactions, prioritizing token transfers"""
        normal_txs = await self.get_latest_transactions(address, chain_id, limit)
        token_txs = await self.get_token_transactions(address, chain_id, limit)
        
        # Create a dict to group transactions by hash
        tx_by_hash = {}
        
        # First, add token transactions (they have more relevant info)
        for tx in token_txs:
            tx_by_hash[tx.hash] = tx
        
        # Then add normal transactions only if no token transaction exists for that hash
        for tx in normal_txs:
            if tx.hash not in tx_by_hash:
                tx_by_hash[tx.hash] = tx
        
        # Convert back to list and sort by timestamp
        all_txs = list(tx_by_hash.values())
        all_txs.sort(key=lambda x: x.timestamp, reverse=True)
        
        return all_txs[:limit]

class MultiChainWalletMonitor:
    def __init__(self, bot_token: str, etherscan_api_key: str, solscan_api_key: str):
        self.application = Application.builder().token(bot_token).build()
        self.etherscan = MultiChainEtherscanAPI(etherscan_api_key)
        self.solscan_api_key = solscan_api_key
        # Structure: chat_id -> {(address, chain_id): True}
        self.monitored_wallets: Dict[str, Dict[Tuple[str, int], bool]] = {}
        # Structure: (address, chain_id) -> latest_tx_hash
        self.last_transactions: Dict[Tuple[str, int], str] = {}
        self.monitoring_active = False
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("add", self.add_wallet))
        self.application.add_handler(CommandHandler("remove", self.remove_wallet))
        self.application.add_handler(CommandHandler("list", self.list_wallets))
        self.application.add_handler(CommandHandler("check", self.check_wallet))
        self.application.add_handler(CommandHandler("chains", self.list_chains))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        chat_id = str(update.effective_chat.id)
        
        chains_list = "\n".join([f"{info['name']}" for info in SUPPORTED_CHAINS.values()])
        
        welcome_message = f"""
🤖 **Multi-Chain Wallet Monitor Bot**

I can monitor wallet addresses across multiple blockchains and notify you of any transactions (including token transfers).

**Supported Chains:**
{chains_list}

**Commands:**
/add <address> [chain_id] - Add a wallet address to monitor
/remove <address> [chain_id] - Remove a wallet address from monitoring
/list - Show all monitored wallets
/check <address> [chain_id] - Check recent transactions for an address
/chains - Show all supported chains and their IDs
/help - Show this help message

**Examples:**
```
/add 0x1234567890abcdef1234567890abcdef12345678
/add 0x1234567890abcdef1234567890abcdef12345678 56
/check 0x1234567890abcdef1234567890abcdef12345678 137
```

**Default Chain:** Ethereum Mainnet (ID: 1)

Let's start monitoring! 🚀
        """
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        
        # Initialize monitoring for this chat
        if chat_id not in self.monitored_wallets:
            self.monitored_wallets[chat_id] = {}
    
    async def list_chains(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all supported chains"""
        chains_text = "🔗 **Supported Blockchain Networks:**\n\n"
        
        for chain_id, info in SUPPORTED_CHAINS.items():
            chains_text += f"**{info['name']}**\n"
            chains_text += f"   • Chain ID: `{chain_id}`\n"
            chains_text += f"   • Native Token: {info['symbol']}\n"
            chains_text += f"   • Explorer: {info['explorer']}\n\n"
        
        chains_text += "**Usage:**\n"
        chains_text += "• `/add <address>` - Monitors on Ethereum (default)\n"
        chains_text += "• `/add <address> 56` - Monitors on BNB Smart Chain\n"
        chains_text += "• `/add <address> 137` - Monitors on Polygon\n"
        
        await update.message.reply_text(chains_text, parse_mode='Markdown')
    
    async def add_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add a wallet address to monitor across all supported chains"""
        chat_id = str(update.effective_chat.id)
        
        if not context.args:
            await update.message.reply_text(
                "Please provide a wallet address.\n\n"
                "**Example:**\n"
                "• `/add 0x1234567890abcdef1234567890abcdef12345678` (will monitor across all chains)\n\n"
                "The address will be monitored on all supported networks simultaneously.",
                parse_mode='Markdown'
            )
            return
        
        address = context.args[0].lower()
        
        # Validate address format
        if not address.startswith('0x') or len(address) != 42:
            await update.message.reply_text("❌ Invalid address format. Address should start with 0x and be 42 characters long.")
            return
        
        # Initialize chat monitoring if not exists
        if chat_id not in self.monitored_wallets:
            self.monitored_wallets[chat_id] = {}
        
        # Add address to ALL supported chains
        added_chains = []
        already_monitored = []
        
        for chain_id in SUPPORTED_CHAINS.keys():
            wallet_key = (address, chain_id)
            
            if wallet_key in self.monitored_wallets[chat_id]:
                already_monitored.append(SUPPORTED_CHAINS[chain_id]['name'])
            else:
                self.monitored_wallets[chat_id][wallet_key] = True
                added_chains.append(SUPPORTED_CHAINS[chain_id]['name'])
                
                # Set baseline transaction for each chain
                try:
                    token_txs = await self.etherscan.get_token_transactions(address, chain_id, 1)
                    normal_txs = await self.etherscan.get_latest_transactions(address, chain_id, 1)
                    
                    latest_tx = None
                    if token_txs and normal_txs:
                        latest_tx = token_txs[0] if token_txs[0].timestamp > normal_txs[0].timestamp else normal_txs[0]
                    elif token_txs:
                        latest_tx = token_txs[0]
                    elif normal_txs:
                        latest_tx = normal_txs[0]
                    
                    if latest_tx:
                        self.last_transactions[wallet_key] = latest_tx.hash
                except Exception as e:
                    logger.error(f"Error getting initial transaction for chain {chain_id}: {e}")
        
        # Build response message
        message = f"✅ **Multi-Chain Monitoring Setup**\n\n"
        message += f"📍 **Address:** `{address}`\n\n"
        
        if added_chains:
            message += f"🆕 **Added to {len(added_chains)} chains:**\n"
            for chain_name in added_chains:
                chain_info = next(info for info in SUPPORTED_CHAINS.values() if info['name'] == chain_name)
                message += f"   {chain_name}\n"
        
        if already_monitored:
            message += f"\n✅ **Already monitoring on {len(already_monitored)} chains:**\n"
            for chain_name in already_monitored:
                chain_info = next(info for info in SUPPORTED_CHAINS.values() if info['name'] == chain_name)
                message += f"   {chain_name}\n"
        
        message += f"\n🔔 **Total chains monitoring:** {len(SUPPORTED_CHAINS)}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
        # Start monitoring if not already active
        if not self.monitoring_active:
            asyncio.create_task(self.monitor_loop())
    
    async def remove_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove a wallet address from monitoring"""
        chat_id = str(update.effective_chat.id)
        
        if not context.args:
            await update.message.reply_text(
                "Please provide a wallet address and optionally a chain ID.\n\n"
                "**Examples:**\n"
                "• `/remove 0x1234567890abcdef1234567890abcdef12345678` (Ethereum)\n"
                "• `/remove 0x1234567890abcdef1234567890abcdef12345678 56` (BNB Smart Chain)",
                parse_mode='Markdown'
            )
            return
        
        address = context.args[0].lower()
        chain_id = int(context.args[1]) if len(context.args) > 1 else 1
        
        wallet_key = (address, chain_id)
        
        if chat_id not in self.monitored_wallets or wallet_key not in self.monitored_wallets[chat_id]:
            chain_info = self.etherscan.get_chain_info(chain_id)
            await update.message.reply_text(
                f"❌ Address not found in monitoring list:\n"
                f"📍 **Address:** `{address}`\n"
                f"{chain_info['emoji']} **Chain:** {chain_info['name']} (ID: {chain_id})",
                parse_mode='Markdown'
            )
            return
        
        del self.monitored_wallets[chat_id][wallet_key]
        
        # Clean up last transaction records if no one is monitoring this address
        if not any(wallet_key in wallets for wallets in self.monitored_wallets.values()):
            self.last_transactions.pop(wallet_key, None)
        
        chain_info = self.etherscan.get_chain_info(chain_id)
        await update.message.reply_text(
            f"✅ Removed wallet address from monitoring:\n"
            f"📍 **Address:** `{address}`\n"
            f"{chain_info['emoji']} **Chain:** {chain_info['name']} (ID: {chain_id})",
            parse_mode='Markdown'
        )
    
    async def list_wallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all monitored wallets"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id not in self.monitored_wallets or not self.monitored_wallets[chat_id]:
            await update.message.reply_text(
                "📝 No wallets are currently being monitored.\n\n"
                "Use `/add <address> [chain_id]` to start monitoring a wallet.\n"
                "Use `/chains` to see supported networks.",
                parse_mode='Markdown'
            )
            return
        
        # Group wallets by chain
        chains_wallets = {}
        for (address, chain_id) in self.monitored_wallets[chat_id].keys():
            if chain_id not in chains_wallets:
                chains_wallets[chain_id] = []
            chains_wallets[chain_id].append(address)
        
        message = f"📝 **Monitored Wallets ({len(self.monitored_wallets[chat_id])}):**\n\n"
        
        for chain_id, addresses in chains_wallets.items():
            chain_info = self.etherscan.get_chain_info(chain_id)
            message += f"{chain_info['name']} ({len(addresses)} wallet{'s' if len(addresses) > 1 else ''})**\n"
            for addr in addresses:
                message += f"   • `{addr}`\n"
            message += "\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def check_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check recent transactions for a wallet"""
        if not context.args:
            await update.message.reply_text(
                "Please provide a wallet address and optionally a chain ID.\n\n"
                "**Examples:**\n"
                "• `/check 0x1234567890abcdef1234567890abcdef12345678` (Ethereum)\n"
                "• `/check 0x1234567890abcdef1234567890abcdef12345678 56` (BNB Smart Chain)",
                parse_mode='Markdown'
            )
            return
        
        address = context.args[0].lower()
        chain_id = int(context.args[1]) if len(context.args) > 1 else 1
        
        # Validate address format
        if not address.startswith('0x') or len(address) != 42:
            await update.message.reply_text("❌ Invalid address format.")
            return
        
        # Validate chain ID
        if chain_id not in SUPPORTED_CHAINS:
            supported_ids = ", ".join(str(id) for id in SUPPORTED_CHAINS.keys())
            await update.message.reply_text(f"❌ Unsupported chain ID: {chain_id}\n\nSupported chain IDs: {supported_ids}")
            return
        
        chain_info = self.etherscan.get_chain_info(chain_id)
        await update.message.reply_text(
            f"🔍 Checking recent transactions for `{address}` on {chain_info['emoji']} {chain_info['name']}...",
            parse_mode='Markdown'
        )
        
        try:
            transactions = await self.etherscan.get_all_transactions(address, chain_id, 5)
            
            if not transactions:
                await update.message.reply_text(
                    f"📭 No recent transactions found for `{address}` on {chain_info['name']}",
                    parse_mode='Markdown'
                )
                return
            
            for tx in transactions:
                message = self.format_transaction_message(tx, address)
                await update.message.reply_text(message, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error checking wallet: {e}")
            await update.message.reply_text("❌ Error checking wallet transactions. Please try again later.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message"""
        chains_list = "\n".join([f"   • {info['emoji']} {info['name']} (ID: {chain_id})" for chain_id, info in SUPPORTED_CHAINS.items()])
        
        help_text = f"""
🤖 **Multi-Chain Wallet Monitor Bot Help**

**Commands:**
/start - Start the bot and show welcome message
/add <address> [chain_id] - Add a wallet address to monitor
/remove <address> [chain_id] - Remove a wallet address from monitoring
/list - Show all monitored wallets
/check <address> [chain_id] - Check recent transactions for an address
/chains - Show all supported chains and their IDs
/help - Show this help message

**Supported Chains:**
{chains_list}

**Features:**
• Monitor multiple wallet addresses across different chains
• Real-time transaction notifications
• Support for both native tokens and token transfers
• Detailed transaction information
• Easy management of monitored addresses

**Example Usage:**
```
/add 0x1234567890abcdef1234567890abcdef12345678
/add 0x1234567890abcdef1234567890abcdef12345678 56
/check 0x1234567890abcdef1234567890abcdef12345678 137
/remove 0x1234567890abcdef1234567890abcdef12345678 42161
```

**Default Chain:** If no chain ID is provided, Ethereum Mainnet (ID: 1) is used.

**Transaction Details Include:**
• Transaction hash
• From/To addresses
• Amount and token type
• Timestamp
• Contract address (for tokens)
• Blockchain network

Need help? Contact support or check the documentation.
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'refresh':
            # Refresh functionality can be added here
            await query.edit_message_text("🔄 Refreshing...", parse_mode='Markdown')
    
    def format_transaction_message(self, tx: Transaction, monitored_address: str) -> str:
        """Format transaction data into a readable message"""
        timestamp = datetime.fromtimestamp(tx.timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
        chain_info = self.etherscan.get_chain_info(tx.chain_id)
        
        # Determine direction
        is_incoming = tx.to_address.lower() == monitored_address.lower()
        direction = "📥 INCOMING" if is_incoming else "📤 OUTGOING"
        
        # Format value and token information
        if tx.is_token_transfer:
            # Format token amount properly
            try:
                amount = float(tx.value)
                if amount == 0:
                    value_str = f"0 {tx.token_symbol}"
                elif amount < 0.000001:
                    value_str = f"{amount:.10f} {tx.token_symbol}"
                elif amount < 1:
                    value_str = f"{amount:.6f} {tx.token_symbol}"
                else:
                    value_str = f"{amount:,.2f} {tx.token_symbol}"
            except:
                value_str = f"{tx.value} {tx.token_symbol}"
            
            token_info = f"\n📄 **Token:** {tx.token_name} ({tx.token_symbol})"
            if tx.contract_address:
                token_info += f"\n🏠 **Contract:** `{tx.contract_address}`"
            
            # Add token type indicator
            token_type = "🪙"
            if tx.token_symbol in ['USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'FRAX']:
                token_type = "💵"  # Stablecoin
            elif tx.token_symbol in ['WETH', 'WBTC', 'WBNB', 'WMATIC', 'WAVAX']:
                token_type = "🔄"  # Wrapped token
            elif tx.token_symbol in ['UNI', 'AAVE', 'COMP', 'LINK', 'SUSHI', 'CRV']:
                token_type = "🏛️"  # DeFi token
            elif tx.token_symbol in ['DOGE', 'SHIB', 'PEPE', 'FLOKI']:
                token_type = "🐕"  # Meme token
            
            token_info = f"\n{token_type} **Token:** {tx.token_name} ({tx.token_symbol})" + token_info[token_info.find('\n🏠'):]
        else:
            # Native token transaction
            try:
                amount = float(tx.value)
                if amount == 0:
                    value_str = f"0 {tx.token_symbol}"
                else:
                    value_str = f"{amount:.6f} {tx.token_symbol}"
            except:
                value_str = f"{tx.value} {tx.token_symbol}"
            token_info = ""
        
        # Calculate gas fee
        try:
            gas_fee = int(tx.gas_used) * int(tx.gas_price) / 10**18
            gas_fee_str = f"{gas_fee:.6f} {chain_info['symbol']}"
        except:
            gas_fee_str = "N/A"
        
        # Transaction type emoji
        tx_emoji = "🔔"
        if tx.is_token_transfer:
            tx_emoji = "🪙"
        
        # Get appropriate explorer URL
        explorer_url = f"{chain_info['explorer']}/tx/{tx.hash}"
        
        message = f"""
{tx_emoji} **NEW TRANSACTION DETECTED**

**Network:** {chain_info['name']}
{direction}
💰 **Amount:** {value_str}
🏠 **From:** `{tx.from_address}`
🏠 **To:** `{tx.to_address}`
🔗 **Hash:** `{tx.hash}`
🕒 **Time:** {timestamp}{token_info}

[View on Explorer]({explorer_url})
        """
        
        return message.strip()
    
    async def send_transaction_notification(self, address: str, chain_id: int, tx: Transaction):
        """Send transaction notification to all monitoring chats"""
        wallet_key = (address, chain_id)
        
        for chat_id, wallets in self.monitored_wallets.items():
            if wallet_key in wallets:
                try:
                    message = self.format_transaction_message(tx, address)
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.error(f"Error sending notification to chat {chat_id}: {e}")
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        self.monitoring_active = True
        logger.info("Starting multi-chain wallet monitoring loop...")
        
        while self.monitoring_active:
            try:
                # Get all unique (address, chain_id) pairs being monitored
                all_wallets = set()
                for wallets in self.monitored_wallets.values():
                    all_wallets.update(wallets.keys())
                
                if not all_wallets:
                    await asyncio.sleep(5)  # Wait before checking again
                    continue
                
                # Check each wallet for new transactions
                for address, chain_id in all_wallets:
                    try:
                        wallet_key = (address, chain_id)
                        
                        # Get both token and normal transactions separately to ensure we catch everything
                        token_txs = await self.etherscan.get_token_transactions(address, chain_id, 5)
                        normal_txs = await self.etherscan.get_latest_transactions(address, chain_id, 5)
                        
                        # Get all transactions and sort by timestamp
                        all_txs = []
                        
                        # Add token transactions
                        for tx in token_txs:
                            all_txs.append(tx)
                        
                        # Add normal transactions (but avoid duplicates)
                        token_hashes = {tx.hash for tx in token_txs}
                        for tx in normal_txs:
                            if tx.hash not in token_hashes:
                                all_txs.append(tx)
                        
                        # Sort by timestamp (newest first)
                        all_txs.sort(key=lambda x: x.timestamp, reverse=True)
                        
                        # Process new transactions
                        for tx in all_txs:
                            # Check if this is a new transaction
                            if wallet_key not in self.last_transactions:
                                # First time monitoring this wallet, set baseline
                                self.last_transactions[wallet_key] = tx.hash
                                continue
                            
                            # If this transaction is newer than our last recorded one
                            if tx.hash != self.last_transactions[wallet_key]:
                                # Check if we've seen this transaction before by comparing timestamps
                                # This helps avoid duplicate notifications when the API returns the same tx
                                should_notify = True
                                
                                # Find the last recorded transaction to compare timestamps
                                for prev_tx in all_txs:
                                    if prev_tx.hash == self.last_transactions[wallet_key]:
                                        # Only notify if this transaction is newer
                                        if tx.timestamp <= prev_tx.timestamp:
                                            should_notify = False
                                        break
                                
                                if should_notify:
                                    # Send notification
                                    await self.send_transaction_notification(address, chain_id, tx)
                                    
                                    # Update the last transaction for this wallet
                                    self.last_transactions[wallet_key] = tx.hash
                                    
                                    # Log the transaction
                                    chain_info = self.etherscan.get_chain_info(chain_id)
                                    logger.info(f"New transaction detected: {tx.hash} on {chain_info['name']} for {address}")
                                    
                                    # Small delay to avoid spam
                                    await asyncio.sleep(1)
                                break
                    
                    except Exception as e:
                        logger.error(f"Error monitoring address {address} on chain {chain_id}: {e}")
                    
                    # Small delay between address checks to avoid rate limiting
                    await asyncio.sleep(2)
                
                # Wait before next monitoring cycle
                await asyncio.sleep(5)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def run(self):
        """Run the bot"""
        try:
            await self.application.initialize()
            await self.application.start()
            
            logger.info("Multi-Chain Wallet Monitor Bot started successfully!")
            logger.info(f"Monitoring {len(SUPPORTED_CHAINS)} blockchain networks:")
            for chain_id, info in SUPPORTED_CHAINS.items():
                logger.info(f"  • {info['name']} (ID: {chain_id})")
            
            # Start polling
            await self.application.updater.start_polling()
            
            # Keep the bot running
            await asyncio.Event().wait()
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
        finally:
            await self.etherscan.close_session()
            await self.application.stop()

# Configuration
BOT_TOKEN = "8134800071:AAGxNQPEfECYu56QMt1yjD0Ij0cZp8TH-4o"
ETHERSCAN_API_KEY = "V4D7Y8SP1NS6S8ZJ4TFTYJB6PWX9J87ZEE"
SOLSCAN_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTI1NzkwMzUyNzMsImVtYWlsIjoicXVhbnRzZW50cml4QGdtYWlsLmNvbSIsImFjdGlvbiI6InRva2VuLWFwaSIsImFwaVZlcnNpb24iOiJ2MiIsImlhdCI6MTc1MjU3OTAzNX0.lASyrlGI8-TLokOLhtbf-JalKsqgfPFoRJHpXs0Mx7Y"

async def main():
    """Main function to run the bot"""
    monitor = MultiChainWalletMonitor(BOT_TOKEN, ETHERSCAN_API_KEY, SOLSCAN_API_KEY)
    await monitor.run()

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
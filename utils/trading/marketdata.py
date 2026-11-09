# marketdata.py
import threading
import time
import asyncio
from ib_insync import IB, Stock

class IBMarketData:
    def __init__(self, host='192.168.4.73', port=7497, clientId=100,
                 symbol='AAPL', exchange='SMART', currency='USD'):
        self.ib = None  # We'll create this in the event loop thread
        self.host = host
        self.port = port
        self.clientId = clientId
        
        # Contract info
        self.symbol = symbol
        self.exchange = exchange
        self.currency = currency
        self.primary_exchange = 'NASDAQ'  # Default
        
        # Data structures
        self.contract = None
        self.ticker = None
        self.latest_data = {'bid': None, 'ask': None, 'last': None}
        self.running = False
        self.ib_thread = None
        self.data_lock = threading.Lock()

    def _run_ib_loop(self):
        """Run IB event loop in this thread"""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create and connect IB instance
        self.ib = IB()
        try:
            print(f"Connecting with clientId: {self.clientId}")
            self.ib.connect(self.host, self.port, clientId=self.clientId)
            print(f"Connected with clientId: {self.clientId}")
            
            # Create and qualify contract
            self.contract = Stock(self.symbol, self.exchange, self.currency)
            self.contract.primaryExchange = self.primary_exchange
            qualified_contracts = self.ib.qualifyContracts(self.contract)
            
            if qualified_contracts:
                self.contract = qualified_contracts[0]
                # Request market data
                self.ticker = self.ib.reqMktData(self.contract)
                print(f"Market data requested for {self.symbol}")
                
                # Start updating data
                def on_pending_tickers(tickers):
                    for ticker in tickers:
                        if ticker.contract.symbol == self.symbol:
                            with self.data_lock:
                                self.latest_data = {
                                    'bid': ticker.bid,
                                    'ask': ticker.ask,
                                    'last': ticker.last,
                                    'volume': ticker.volume,
                                    'high': ticker.high,
                                    'low': ticker.low
                                }
                
                # Register callback
                self.ib.pendingTickersEvent += on_pending_tickers
                
                # Run the IB event loop
                self.running = True
                self.ib.run()
            else:
                print(f"Failed to qualify contract for {self.symbol}")
        
        except Exception as e:
            print(f"API connection failed for {self.symbol}: {e}")
            self.running = False
            if self.ib.isConnected():
                self.ib.disconnect()

    def connect(self):
        """Start the IB connection in a separate thread"""
        if self.ib_thread and self.ib_thread.is_alive():
            print(f"Already connected for {self.symbol}")
            return
        
        # Start IB in its own thread with its own event loop
        self.ib_thread = threading.Thread(target=self._run_ib_loop, daemon=True)
        self.ib_thread.start()
        
        # Wait a bit for connection to be established
        time.sleep(0.5)

    def get_data(self):
        """Get the latest market data"""
        with self.data_lock:
            return dict(self.latest_data)

    def disconnect(self):
        """Disconnect from IB"""
        self.running = False
        
        # Signal the IB thread to stop
        if self.ib and self.ib.isConnected():
            try:
                if self.ticker:
                    self.ib.cancelMktData(self.ticker)
                self.ib.disconnect()
            except Exception as e:
                print(f"Error disconnecting from IB for {self.symbol}: {e}")
        
        # Wait for thread to end
        if self.ib_thread and self.ib_thread.is_alive():
            self.ib_thread.join(timeout=2)
        
        print(f"Disconnected market data for {self.symbol}")
from binance.client import Client
import pandas as pd
import numpy as np
import pandas_ta as ta
import time
from datetime import datetime


class BinanceFuturesTrader:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.symbol = 'BTCUSDT'
        self.timeframe = '5m'
        self.leverage = 20
        self.stop_loss_percent = 2  # 2% stop loss
        self.take_profit_percent = 3  # 3% take profit

    def setup_futures_account(self):
        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self.client.futures_change_margin_type(symbol=self.symbol, marginType='ISOLATED')
        except Exception as e:
            print(f"Futures account setup error: {e}")

    def get_historical_data(self):
        klines = self.client.futures_klines(symbol=self.symbol, interval=self.timeframe, limit=100)
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
                                           'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                                           'taker_buy_quote', 'ignored'])
        df['close'] = pd.to_numeric(df['close'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        return df

    def calculate_signals(self, df):
        df['EMA9'] = ta.ema(df['close'], length=9)
        df['EMA21'] = ta.ema(df['close'], length=21)
        df['RSI'] = ta.rsi(df['close'], length=14)
        macd = ta.macd(df['close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_Signal'] = macd['MACDs_12_26_9']
        bb = ta.bbands(df['close'], length=20)
        df['BB_Upper'] = bb['BBU_20_2.0']
        df['BB_Middle'] = bb['BBM_20_2.0']
        df['BB_Lower'] = bb['BBL_20_2.0']

        df['signal'] = 0
        long_condition = (df['EMA9'] > df['EMA21']) & (df['RSI'] < 70) & (df['MACD'] > df['MACD_Signal'])
        short_condition = (df['EMA9'] < df['EMA21']) & (df['RSI'] > 30) & (df['MACD'] < df['MACD_Signal'])

        df.loc[long_condition, 'signal'] = 1
        df.loc[short_condition, 'signal'] = -1
        return df

    def calculate_position_size(self):
        modal = 3  # Modal per trade $3
        ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
        current_price = float(ticker['price'])

        position_size = round((modal * self.leverage) / current_price, 4)
        return position_size

    def close_position(self, side, position_size):
        try:
            order_side = 'SELL' if side == 'BUY' else 'BUY'
            self.client.futures_create_order(
                symbol=self.symbol,
                type='MARKET',
                side=order_side,
                quantity=abs(float(position_size))
            )
            print(f"Closed {side} position with size {position_size}")
        except Exception as e:
            print(f"Error closing position: {e}")

    def execute_trade(self, signal):
        try:
            position_size = self.calculate_position_size()
            current_price = float(self.client.futures_symbol_ticker(symbol=self.symbol)['price'])

            if signal == 1:  # Long
                stop_loss = current_price * (1 - self.stop_loss_percent / 100)
                take_profit = current_price * (1 + self.take_profit_percent / 100)

                order = self.client.futures_create_order(
                    symbol=self.symbol,
                    type='MARKET',
                    side='BUY',
                    quantity=position_size
                )

                print(f"Opened LONG position, size: {position_size}, SL: {stop_loss}, TP: {take_profit}")

            elif signal == -1:  # Short
                stop_loss = current_price * (1 + self.stop_loss_percent / 100)
                take_profit = current_price * (1 - self.take_profit_percent / 100)

                order = self.client.futures_create_order(
                    symbol=self.symbol,
                    type='MARKET',
                    side='SELL',
                    quantity=position_size
                )

                print(f"Opened SHORT position, size: {position_size}, SL: {stop_loss}, TP: {take_profit}")

        except Exception as e:
            print(f"Trade execution error: {e}")

    def get_open_position(self):
        positions = self.client.futures_position_information(symbol=self.symbol)
        for position in positions:
            if float(position['positionAmt']) != 0:
                return position
        return None

    def run_bot(self):
        self.setup_futures_account()

        while True:
            try:
                df = self.get_historical_data()
                df = self.calculate_signals(df)
                current_signal = df['signal'].iloc[-1]
                open_position = self.get_open_position()

                if open_position:
                    position_side = 'BUY' if float(open_position['positionAmt']) > 0 else 'SELL'
                    position_size = open_position['positionAmt']

                    if (current_signal == 1 and position_side == 'SELL') or (current_signal == -1 and position_side == 'BUY'):
                        self.close_position(position_side, position_size)

                if not open_position and current_signal != 0:
                    self.execute_trade(current_signal)

                time.sleep(30)

            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(30)


if __name__ == "__main__":
    api_key = '02xHeGi8NAZjhLuvdsPl78PxT9gPj4jo2ih2vwAIWwhQpasbsRdY7hPNDU2nD4et'
    api_secret = '2gEqFpcpxfLBsgATX5fRFag8NozV7I2efEl4vaFCvqrObshBvt9AlgCtoN6s8VPz'

    trader = BinanceFuturesTrader(api_key, api_secret)
    trader.run_bot()

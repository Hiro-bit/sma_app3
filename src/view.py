from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from yahoo_finance_api2 import share
from yahoo_finance_api2.exceptions import YahooFinanceError
import requests
import lxml.html
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stocks.db'
db = SQLAlchemy(app)

# データベースモデルの定義
class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.Integer, unique=True, nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    closing_place = db.Column(db.Float, nullable=False)
    dividend_yield = db.Column(db.Float, nullable=False)
    sma_data = db.Column(db.String(500), nullable=False)

    def __repr__(self):
        return f"<Stock {self.stock_code}>"

# ルートの定義
@app.route('/')
def index():
    data = []
    max_sma_values = {}  # 銘柄ごとのSMAデータの最大値を保持する辞書
    # stock_codesの定義を削除し、代わりにこの部分で銘柄コードを直接指定する
    stock_codes = [ # 1343, 1489, 1723, 1835, 1928, 1951, 2003, 2124, 2169, 2296, 2393, 3076, 3817, 3834, 4008, 4041, 4042, 4220, 4502, 4641, 4743, 4748] #, \
            #    4832, 5011, 5334, 5388, 5464, 6073, 6322, 6454, 6539, 6745, 6957, 7820, 7921, 7931, 7995, 8031, 8058, 8130, 8306, 8316, 8584] #, \
               8591, 8593, 8750, 8766, 9069, 9142, 9303, 9368, 9432, 9433, 9436, 9513, 9769, 9795, 9882, 9960, 9986]
    for stock_code in stock_codes:
        stock_data = get_stock_data(stock_code)
        if stock_data['sma_data']:  # SMAデータが空でない場合のみ最大値を計算して保存
            max_sma_values[stock_code] = float(max(stock_data['sma_data'].values()))
        data.append(stock_data)

    return render_template('index.html', data=data, max_sma_values=max_sma_values)

# データベースに株式データを保存する関数
def save_stock_to_db(stock_data):
    stock = Stock(stock_code=stock_data['stock_code'], company_name=stock_data['company_name'], closing_place=stock_data['closing_place'], dividend_yield=stock_data['dividend_yield'], sma_data=str(stock_data['sma_data']))
    db.session.add(stock)
    db.session.commit()

# その他の関数の定義
def get_stock_data(stock_code):
    chart_url = f"https://minkabu.jp/stock/{stock_code}/chart"
    try:
        chart_html = requests.get(chart_url)
        chart_html.raise_for_status()
        chart_dom_tree = lxml.html.fromstring(chart_html.content)
        closing_place = parse_dom_tree(chart_dom_tree, '//*[@id="stock_header_contents"]/div[1]/div/div[1]/div/div/div[1]/div[2]/div/div[2]/div/text()', '', '')
        dividend_yield = parse_dom_tree2(chart_dom_tree, '//*[@id="contents"]/div[3]/div[1]/div/div/div[2]/div/div[2]//tr[3]/td[1]', '%', '')
        company_name = parse_dom_tree3(chart_dom_tree, '//*[@id="stock_header_contents"]/div[1]/div/div[1]/div/div/div[1]/div[1]/h2/a/p')

        # SMAデータを取得
        sma_data = get_sma_data(chart_dom_tree, stock_code)

        # データが取得できなかった場合の処理を追加
        if closing_place is None or closing_place == '---':
            closing_place = 0
        if dividend_yield is None or dividend_yield == '---':
            dividend_yield = 0

        return {'stock_code': stock_code, 'company_name': company_name, 'closing_place': float(closing_place), 'dividend_yield': float(dividend_yield), 'sma_data': sma_data}
    except Exception as e:
        print(f"Error fetching data for stock code {stock_code}: {e}")
        return {'stock_code': stock_code, 'company_name': '', 'closing_place': 0, 'dividend_yield': 0, 'sma_data': {}}

def get_sma_data(dom_tree, stock_code):
    sma_data = {}

    # SMA計算用のデータフレームを作成
    symbol_data_day = get_historical_data(stock_code, share.PERIOD_TYPE_YEAR, 100, share.FREQUENCY_TYPE_DAY, 1)
    df_day = pd.DataFrame(symbol_data_day)
    symbol_data_week = get_historical_data(stock_code, share.PERIOD_TYPE_YEAR, 100, share.FREQUENCY_TYPE_WEEK, 1)
    df_week = pd.DataFrame(symbol_data_week)
    symbol_data_month = get_historical_data(stock_code, share.PERIOD_TYPE_YEAR, 100, share.FREQUENCY_TYPE_MONTH, 1)
    df_month = pd.DataFrame(symbol_data_month)

    # SMAを計算
    df_day, sma_day_columns = sma_day(df_day)
    df_week, sma_week_columns = sma_week(df_week)
    df_month, sma_month_columns = sma_month(df_month)

    # SMAデータを辞書に追加
    for column in sma_day_columns:
        sma_data[column] = df_day[column].iloc[-1]
    for column in sma_week_columns:
        sma_data[column] = df_week[column].iloc[-1]
    for column in sma_month_columns:
        sma_data[column] = df_month[column].iloc[-1]

    return sma_data

def get_historical_data(stock_code, period_type, period, frequency_type, frequency):
    try:
        stock = share.Share(str(stock_code) + '.T')
        symbol_data = stock.get_historical(period_type=period_type, period=period, frequency_type=frequency_type, frequency=frequency)
        return symbol_data
    except YahooFinanceError as e:
        print(f"Error fetching historical data for stock code {stock_code}: {e}")
        return []

def sma_day(df_day):
    df_day["sma_day_025"] = df_day["close"].rolling(window=25).mean().round(2)
    df_day["sma_day_075"] = df_day["close"].rolling(window=75).mean().round(2)
    df_day["sma_day_100"] = df_day["close"].rolling(window=100).mean().round(2)
    df_day["sma_day_200"] = df_day["close"].rolling(window=200).mean().round(2)
    sma_day_columns = [col for col in df_day.columns if col.startswith('sma_day_')]
    return df_day, sma_day_columns

def sma_week(df_week):
    df_week["sma_week_025"] = df_week["close"].rolling(window=25).mean().round(2)
    df_week["sma_week_075"] = df_week["close"].rolling(window=75).mean().round(2)
    df_week["sma_week_100"] = df_week["close"].rolling(window=100).mean().round(2)
    df_week["sma_week_200"] = df_week["close"].rolling(window=200).mean().round(2)
    sma_week_columns = [col for col in df_week.columns if col.startswith('sma_week_')]
    return df_week, sma_week_columns

def sma_month(df_month):
    df_month["sma_month_012"] = df_month["close"].rolling(window=12).mean().round(2)
    df_month["sma_month_024"] = df_month["close"].rolling(window=24).mean().round(2)
    df_month["sma_month_060"] = df_month["close"].rolling(window=60).mean().round(2)
    df_month["sma_month_100"] = df_month["close"].rolling(window=100).mean().round(2)
    df_month["sma_month_200"] = df_month["close"].rolling(window=200).mean().round(2)
    sma_month_columns = [col for col in df_month.columns if col.startswith('sma_month_')]
    return df_month, sma_month_columns

def parse_dom_tree(dom_tree, xpath, replace_pattern, replace_value):
    element = dom_tree.xpath(xpath)
    if element:
        text = element[0].strip()
        if text == '---':
            return None
        if replace_pattern:
            text = re.sub(replace_pattern, replace_value, text)
        # カンマを取り除く
        text = text.replace(',', '')
        return text
    else:
        return None

def parse_dom_tree2(dom_tree, xpath, replace_pattern, replace_value):
    element = dom_tree.xpath(xpath)
    if element:
        text = element[0].text.strip()
        if text == '---':
            return None
        if replace_pattern:
            text = re.sub(replace_pattern, replace_value, text)
        return text
    else:
        return None

def parse_dom_tree3(dom_tree, xpath):
    element = dom_tree.xpath(xpath)
    if element:
        return element[0].text.strip()
    else:
        return None

# Flaskアプリケーションのエントリーポイント
if __name__ == '__main__':
    app.run(debug=True)

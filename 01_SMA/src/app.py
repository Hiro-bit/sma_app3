from flask import Flask, render_template
import pandas as pd
from yahoo_finance_api2 import share
from yahoo_finance_api2.exceptions import YahooFinanceError
import requests
import lxml.html
import re

app = Flask(__name__)

# # 複数の株式コードに対応するためのリスト
# stock_codes = [1343, 1489, 1723, 1835, 1951, 2003, 2124, 2296, 2393, 3076, 3817, 3834, 4008, 4041, 4042, 4220, 4502, 4641, 4743, 4748, 4832, 5011, 5334, 5464, 6073, 6322, 6454, 6539, 6745, 6957, 7820, 7921, 7931, 7995, 8031, 8058, 8130, 8306, 8316, 8584, 8591, 8593, 8750, 8766, 9069, 9142, 9303, 9368, 9432, 9433, 9436, 9513, 9769, 9795, 9882, 9960, 9986]

# 複数の株式コードに対応するためのリスト
stock_codes = [1343, 1489, 1723, 1835, 1928, 1951, 2003, 2124, 2296, 2393, 3076, 3817, 3834, 4008, 4041, 4042, 4220, 4502, 4641, 4743, 4748, \
               4832, 5011, 5334, 5464, 6073, 6322, 6454, 6539, 6745, 6957, 7820, 7921, 7931, 7995, 8031, 8058, 8130, 8306, 8316, 8584, \
               8591, 8593, 8750, 8766, 9069, 9142, 9303, 9368, 9432, 9433, 9436, 9513, 9769, 9795, 9882, 9960, 9986]

# @app.route('/')
# def index():
#     data = []
#     max_sma_values = {}  # 銘柄ごとのSMAデータの最大値を保持する辞書
#     for stock_code in stock_codes:
#         stock_data = get_stock_data(stock_code)
#         data.append(stock_data)
#         max_sma_values[stock_code] = max(stock_data['sma_data'].values())  # SMAデータの最大値を計算して保存

#     return render_template('index.html', data=data, max_sma_values=max_sma_values)


@app.route('/')
def index():
    data = []
    max_sma_values = {}  # 銘柄ごとのSMAデータの最大値を保持する辞書
    for stock_code in stock_codes:
        stock_data = get_stock_data(stock_code)
        if stock_data['sma_data']:  # SMAデータが空でない場合のみ最大値を計算して保存
            max_sma_values[stock_code] = max(stock_data['sma_data'].values())
        data.append(stock_data)

    return render_template('index.html', data=data, max_sma_values=max_sma_values)


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
        if closing_place is None:
            closing_place = 0
        if dividend_yield is None:
            dividend_yield = 0

        return {'stock_code': stock_code, 'company_name': company_name, 'closing_place': closing_place, 'dividend_yield': dividend_yield, 'sma_data': sma_data}
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
    sma_data.update({col: df_day[col].iloc[-1] for col in sma_day_columns})
    sma_data.update({col: df_week[col].iloc[-1] for col in sma_week_columns})
    sma_data.update({col: df_month[col].iloc[-1] for col in sma_month_columns})

    return sma_data

def get_historical_data(stock_code, period_type, period, frequency_type, frequency_period):
    try:
        my_share = share.Share(f'{stock_code}.T')
        symbol_data = my_share.get_historical(period_type, period, frequency_type, frequency_period)
        return symbol_data
    except YahooFinanceError as e:
        print(e.message)
        return []

def sma_day(df_day):
    df_day["sma_day_025"] = df_day["close"].rolling(window=25).mean().round(2)
    df_day["sma_day_075"] = df_day["close"].rolling(window=75).mean().round(2)
    df_day["sma_day_100"] = df_day["close"].rolling(window=100).mean().round(2)
    df_day["sma_day_200"] = df_day["close"].rolling(window=200).mean().round(2)
    sma_day_columns = [col for col in df_day.columns if col.startswith('sma_day_')]
    return df_day, sma_day_columns

def sma_week(df_week):
    df_week["sma_week_013"] = df_week["close"].rolling(window=13).mean().round(2)
    df_week["sma_week_026"] = df_week["close"].rolling(window=26).mean().round(2)
    df_week["sma_week_052"] = df_week["close"].rolling(window=52).mean().round(2)
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

def parse_dom_tree(dom_tree, xpath, source, destination):
    raw_data = dom_tree.xpath(xpath)
    data = [int(re.sub(r'[^\d]', '', s)) for s in raw_data if re.sub(r'[^\d]', '', s)]
    if data == []:
        data = [0]
    return data

def util_replace(text, source, destination):
    if text.find(source) > 0:
        tmp = text.replace(',','')
        return float(tmp.replace(source, destination))
    else:
        return None

def parse_dom_tree2(dom_tree, xpath, source, destination):
    raw_data = dom_tree.xpath(xpath)
    data = util_replace(raw_data[0].text,source,destination)
    return data

def parse_dom_tree3(dom_tree, xpath):
    raw_data = dom_tree.xpath(xpath)
    return raw_data[0].text.strip() if raw_data else None

if __name__ == '__main__':
    app.run(debug=True)

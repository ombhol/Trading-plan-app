import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import numpy as np
from datetime import date
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Trading Plan Pro V7.5", layout="wide", page_icon="🦅")

# --- 1. FUNGSI UTILITAS & INDIKATOR ---
def sesuaikan_fraksi_bei(harga):
    """Membulatkan harga ke fraksi harga resmi Bursa Efek Indonesia."""
    harga = int(harga)
    if harga < 50: return 50
    elif harga < 200: fraksi = 1
    elif harga < 500: fraksi = 2
    elif harga < 2000: fraksi = 5
    elif harga < 5000: fraksi = 10
    else: fraksi = 25
    
    return round(harga / fraksi) * fraksi

def calculate_daily_atr(df_1d):
    """Menghitung nilai ATR (Average True Range) berbasis grafik Harian."""
    if df_1d.empty or len(df_1d) < 15:
        return 0
    hl = df_1d['High'] - df_1d['Low']
    hc = np.abs(df_1d['High'] - df_1d['Close'].shift())
    lc = np.abs(df_1d['Low'] - df_1d['Close'].shift())
    atr_daily = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return atr_daily.iloc[-1]

def calculate_indicators(df):
    """Kalkulasi indikator teknikal (EMA, VWAP Reset Harian, RSI Epsilon, ATR)."""
    if df.empty:
        return df
        
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['Date'] = df.index.date
    
    # Intraday VWAP (Reset setiap hari)
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TP_Vol'] = df['TP'] * df['Volume']
    df['Cum_Vol'] = df.groupby('Date')['Volume'].cumsum()
    df['Cum_TP_Vol'] = df.groupby('Date')['TP_Vol'].cumsum()
    df['VWAP'] = df['Cum_TP_Vol'] / df['Cum_Vol'].replace(0, np.nan)
    
    # RSI dengan epsilon untuk menghindari zero division error
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=14).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=14).mean()
    rs = gain / (loss + 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR Intraday (untuk visualisasi chart)
    hl = df['High'] - df['Low']
    hc = np.abs(df['High'] - df['Close'].shift())
    lc = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    return df

# --- 2. FUNGSI AUTO-SCANNER ---
@st.cache_data(ttl=300)
def scan_top_saham(watchlist):
    hasil_scan = []
    for ticker in watchlist:
        try:
            df = yf.download(f"{ticker}.JK", period="5d", interval="5m", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            df = calculate_indicators(df)
            df_clean = df.dropna(subset=['VWAP', 'EMA20', 'RSI'])
            if df_clean.empty: continue
            
            curr = df_clean.iloc[-1]
            
            # Skoring (Max: 90)
            skor = 0
            if curr['Close'] > curr['VWAP']: skor += 30
            if curr['Close'] > curr['EMA20']: skor += 20
            if 40 < curr['RSI'] < 65: skor += 20
            elif curr['RSI'] >= 70: skor -= 20
            if curr['Volume'] > curr['Vol_MA20']: skor += 20
            
            if skor >= 60:
                hasil_scan.append({
                    "ticker": ticker, "skor": skor, "harga": curr['Close'], "vwap": curr['VWAP']
                })
        except Exception:
            continue
    return sorted(hasil_scan, key=lambda x: x['skor'], reverse=True)[:3]

# --- 3. FUNGSI DATA KORPORASI & BERITA ---
@st.cache_data(ttl=1800)
def ambil_berita_indonesia(ticker):
    daftar_berita = []
    try:
        query = urllib.parse.quote(f"{ticker} saham")
        url = f"https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            root = ET.fromstring(response.read())
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            if " - " in title: title = title.rsplit(" - ", 1)[0]
            source = item.find('source').text if item.find('source') is not None else "Media"
            pub_date = item.find('pubDate').text[:16] if item.find('pubDate') is not None else ""
            daftar_berita.append({"title": title, "link": item.find('link').text, "source": source, "date": pub_date})
    except Exception: pass
    return daftar_berita

@st.cache_data(ttl=3600)
def ambil_dividen_akurat(ticker_code):
    try:
        ticker_obj = yf.Ticker(ticker_code)
        hist_div = ticker_obj.dividends
        if hist_div.empty: return {"ada": False}
        hist_div.index = pd.to_datetime(hist_div.index).tz_localize(None)
        today = pd.Timestamp(date.today())
        info_dividen = {"ada": True, "status_upcoming": False, "terakhir": None, "upcoming": None}
        
        def format_dividen(ex_date, nominal):
            cum_date = ex_date - pd.offsets.BDay(1)
            rec_date = ex_date + pd.offsets.BDay(1)
            return {
                "nominal": f"Rp {nominal:,.2f}", "cum_date": cum_date.strftime('%d %b %Y'),
                "ex_date": ex_date.strftime('%d %b %Y'), "rec_date": rec_date.strftime('%d %b %Y'),
                "tanggal_asli": ex_date
            }
        data_akhir = format_dividen(hist_div.index[-1], float(hist_div.iloc[-1]))
        if data_akhir["tanggal_asli"] >= today:
            info_dividen["status_upcoming"] = True
            info_dividen["upcoming"] = data_akhir
            if len(hist_div) > 1: info_dividen["terakhir"] = format_dividen(hist_div.index[-2], float(hist_div.iloc[-2]))
        else:
            info_dividen["terakhir"] = data_akhir
        return info_dividen
    except Exception: return {"ada": False}

@st.cache_data(ttl=3600)
def scan_kalender_dividen(watchlist):
    upcoming_list = []
    today = pd.Timestamp(date.today())
    for ticker in watchlist:
        try:
            hist_div = yf.Ticker(f"{ticker}.JK").dividends
            if not hist_div.empty:
                hist_div.index = pd.to_datetime(hist_div.index).tz_localize(None)
                future_divs = hist_div[hist_div.index >= today]
                for ex_date, nominal in future_divs.items():
                    cum_date = ex

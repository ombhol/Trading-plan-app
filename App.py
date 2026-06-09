import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import numpy as np
from datetime import date
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import concurrent.futures
import requests

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Trading Plan Pro V7.9", layout="wide", page_icon="🦅")

# --- INIT SESSION (ANTI IP-BAN) ---
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

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
    """Menghitung nilai ATR (Average True Range) harian."""
    if df_1d.empty or len(df_1d) < 15: return 0
    hl = df_1d['High'] - df_1d['Low']
    hc = np.abs(df_1d['High'] - df_1d['Close'].shift())
    lc = np.abs(df_1d['Low'] - df_1d['Close'].shift())
    atr_daily = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return atr_daily.iloc[-1]

def calculate_indicators(df):
    """Kalkulasi indikator teknikal utama dengan reset harian VWAP."""
    if df.empty: return df
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['Date'] = df.index.date
    
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TP_Vol'] = df['TP'] * df['Volume']
    df['Cum_Vol'] = df.groupby('Date')['Volume'].cumsum()
    df['Cum_TP_Vol'] = df.groupby('Date')['TP_Vol'].cumsum()
    df['VWAP'] = df['Cum_TP_Vol'] / df['Cum_Vol'].replace(0, np.nan)
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=14).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    
    hl = df['High'] - df['Low']
    hc = np.abs(df['High'] - df['Close'].shift())
    lc = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    return df

# --- 2. FUNGSI AUTO-SCANNER (MULTI-THREADING ENGINE) ---
def proses_satu_saham(ticker):
    try:
        df = yf.download(f"{ticker}.JK", period="5d", interval="5m", progress=False, session=session)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        df = calculate_indicators(df)
        df_clean = df.dropna(subset=['VWAP', 'EMA20', 'RSI', 'Vol_MA20'])
        if df_clean.empty: return None
        
        curr = df_clean.iloc[-1]
        
        if curr['Close'] <= 50 or curr['Vol_MA20'] < 1000:
            return None
            
        skor = 0
        if curr['Close'] > curr['VWAP']: skor += 30
        if curr['Close'] > curr['EMA20']: skor += 20
        if 40 < curr['RSI'] < 65: skor += 20
        elif curr['RSI'] >= 70: skor -= 20
        if curr['Volume'] > curr['Vol_MA20']: skor += 20
        
        if skor >= 60:
            return {"ticker": ticker, "skor": skor, "harga": curr['Close'], "vwap": curr['VWAP']}
    except Exception:
        pass
    return None

@st.cache_data(ttl=120)
def scan_top_saham(watchlist):
    hasil_scan = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(proses_satu_saham, ticker): ticker for ticker in watchlist}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                hasil_scan.append(result)
                
    return sorted(hasil_scan, key=lambda x: x['skor'], reverse=True)[:3]

# --- 3. FUNGSI DATA KORPORASI ---
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

@st.cache_data(ttl=120)
def get_market_data(ticker):
    try:
        df_5m = yf.download(f"{ticker}.JK", period="5d", interval="5m", progress=False, session=session)
        df_1d = yf.download(f"{ticker}.JK", period="3mo", interval="1d", progress=False, session=session)
        if not df_5m.empty and isinstance(df_5m.columns, pd.MultiIndex): df_5m.columns = df_5m.columns.get_level_values(0)
        if not df_1d.empty and isinstance(df_1d.columns, pd.MultiIndex): df_1d.columns = df_1d.columns.get_level_values(0)
        return df_5m, df_1d
    except Exception: return pd.DataFrame(), pd.DataFrame()

# --- 4. UI SIDEBAR PENGATURAN ---
with st.sidebar:
    st.markdown("### ⚙️ Parameter Trading (Real Market)")
    ticker_utama = st.text_input("Analisis Saham Spesifik:", "PSAB").upper()
    modal_trading = st.number_input("Total Portofolio (Rp):", value=10000000, step=1000000)
    risiko_persen = st.slider("Risiko per Trade (%):", 0.1, 5.0, 1.0) / 100
    fee_broker = st.number_input("Total Fee Jual+Beli (%):", value=0.4, step=0.1) / 100
    
    st.markdown("---")
    st.markdown("### 📋 Daftar Pantauan (Scanner)")
    saham_input_user = st.text_input("Daftar Saham:", value="PTBA, ADRO, BRMS, PANI, AMMN, BBCA, BMRI, ASII, PSAB")
    daftar_pantauan = [s.strip().upper() for s in saham_input_user.split(",") if s.strip()]

# --- 5. UI MAIN: TOP REKOMENDASI ---
st.title("🦅 TRADING PLAN PRO V7.9 (Day Trading)")
st.subheader("🏆 Top 3 Sinyal (Anti-Gocap & Likuid)")
with st.spinner("Memindai anomali volume & akumulasi secara paralel (Asynchronous)..."):
    top_3 = scan_top_saham(daftar_pantauan)

if top_3:
    cols_top = st.columns(3)
    for i, data in enumerate(top_3):
        warna_skor = "#10B981" if data['skor'] >= 70 else "#FBBF24"
        with cols_top[i]:
            st.markdown(f"""
            <div style="background-color: #1f2937; padding: 20px; border-radius: 12px; border-top: 5px solid {warna_skor}; text-align: center;">
                <h2 style="margin: 0; color: white;">{data['ticker']}</h2>
                <h1 style="margin: 5px 0; color: {warna_skor};">{data['skor']} / 90</h1>
                <p style="margin: 0; color: #9CA3AF; font-size: 14px;">Skor Logika Pasar</p>
                <hr style="border-color: #374151; margin: 10px 0;">
                <p style="margin: 0; color: white; font-weight: bold;">Harga: Rp {data['harga']:,.0f}</p>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Scanner Kosong: Belum ada saham yang likuid & memenuhi syarat struktur uptrend saat ini.")
st.markdown("---")

# --- 6. UI MAIN: DEEP DIVE ANALISIS ---
st.subheader(f"🔎 Deep Dive Analisis: {ticker_utama}")
df_5m, df_1d = get_market_data(ticker_utama)

if not df_5m.empty and not df_1d.empty:
    df_5m = calculate_indicators(df_5m)
    df_clean = df_5m.dropna(subset=['VWAP', 'EMA20', 'RSI', 'Vol_MA20'])
    
    if df_clean.empty:
        st.warning("Data kurang (kemungkinan saham baru IPO atau suspen panjang).")
    else:
        curr_5m = df_clean.iloc[-1]
        entry = curr_5m['Close']
        
        if entry <= 50:
            st.error("🚨 SAHAM GOCAP (Rp 50): Analisis teknikal tidak valid untuk saham tidur. Harap hindari.")
            st.stop()
            
        ma20_daily = df_1d['Close'].rolling(20).mean().iloc[-1]
        tren_harian = "UPTREND 🟢" if df_1d['Close'].iloc[-1] > ma20_daily else "DOWNTREND 🔴"
        
        close_kemarin = df_1d['Close'].iloc[-2] if len(df_1d) > 1 else entry
        persen_kenaikan = ((entry - close_kemarin) / close_kemarin) * 100 if close_kemarin > 0 else 0
        jarak_vwap_persen = ((entry - curr_5m['VWAP']) / curr_5m['VWAP']) * 100
        
        atr_daily = calculate_daily_atr(df_1d)
        atr_final = atr_daily if atr_daily > 0 else (curr_5m['ATR'] * 5)
        
        sl_mentah = entry - (atr_final * 1.5)
        tp_mentah = entry + (atr_final * 3.0)
        
        sl = sesuaikan_fraksi_bei(sl_mentah)
        tp = sesuaikan_fraksi_bei(tp_mentah)
        
        jarak_sl_rp = entry - sl
        lot_by_risk = int(((modal_trading * risiko_persen) / max(1, jarak_sl_rp)) / 100) if jarak_sl_rp > 0 else 0
        
        rata_volume_pasar_lot = curr_5m['Vol_MA20'] / 100
        lot_by_liquidity = int(rata_volume_pasar_lot * 0.05)
        total_lot = min(lot_by_risk, lot_by_liquidity)
        
        target_bruto_persen = ((tp - entry) / entry)
        peringatan_fee = True if target_bruto_persen <= fee_broker else False

        skor_utama = 0
        if entry > curr_5m['VWAP']: skor_utama += 30
        if entry > curr_5m['EMA20']: skor_utama += 20
        if 40 < curr_5m['RSI'] < 65: skor_utama += 20
        elif curr_5m['RSI'] >= 70: skor_utama -= 20
        if curr_5m['Volume'] > curr_5m['Vol_MA20']: skor_utama += 20
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tren (Daily)", tren_harian)
        c2.metric("Posisi Thd VWAP", f"Rp {curr_5m['VWAP']:,.0f}", f"{jarak_vwap_persen:+.2f}%", delta_color="normal" if entry > curr_5m['VWAP'] else "inverse")
        c3.metric("Harga Saat Ini", f"Rp {entry:,.0f}", f"{persen_kenaikan:+.2f}%")
        
        with c4:
            alasan_lot = "Dibatasi Likuiditas Pasar" if lot_by_liquidity < lot_by_risk else "Berdasarkan Profil Risiko"
            st.metric("Safe Lot Size", f"{total_lot} Lot", alasan_lot, delta_color="off")
            st.metric("Skor Saham (Max 90)", f"{skor_utama} / 90", delta_color="normal" if skor_utama >= 60 else "inverse")
        
        tab1, tab2 = st.tabs(["📊 Eksekusi Order", "📰 Sentimen & Berita"])
        
        with tab1:
            col_plan, col_rules = st.columns([1.5, 1])
            entry_cicil_1 = sesuaikan_fraksi_bei(entry)
            entry_cicil_2 = sesuaikan_fraksi_bei(curr_5m['VWAP'])
            if entry_cicil_2 >= entry_cicil_1: entry_cicil_2 = sesuaikan_fraksi_bei(curr_5m['EMA20'])

            with col_plan:
                st.markdown("### 🎯 Skenario Entry Anti-Guyur")
                if persen_kenaikan > 5.5 or jarak_vwap_persen > 2.5:
                    st.warning(f"🚨 **RAWAN GUYURAN:** Harga lari {jarak_vwap_persen:.1f}% di atas modal institusi (VWAP).")
                    st.write(f"🔹 **Tranche 1 (Test Water - 30%):** Rp {entry_cicil_1}")
                    st.write(f"🔥 **Tranche 2 (Area Pullback - 70%):** Rp {entry_cicil_2}")
                else:
                    st.success("✅ **ZONA AKUMULASI AMAN:** Deviasi normal terhadap VWAP.")
                    st.write(f"🔹 **Tranche 1 (Masuk Awal - 50%):** Rp {entry_cicil_1}")
                    st.write(f"🔹 **Tranche 2 (Jaring Bawah - 50%):** Rp {entry_cicil_2}")

                st.markdown("---")
                st.markdown("### 🛡️ Kalkulasi Target Nett")
                
                if peringatan_fee:
                    st.error(f"📉 **TAKE PROFIT (Rp {tp:,.0f}):** Target terlalu dekat! Profit kotor hanya {target_bruto_persen*100:.2f}%, tidak menutup Fee Broker ({fee_broker*100:.2f}%).")
                else:
                    st.success(f"📈 **TAKE PROFIT:** Rp {tp:,.0f} *(Menutup Fee Broker + Profit)*")
                    
                st.error(f"📉 **STOP LOSS STRICT:** Rp {sl:,.0f}")
                
            with col_rules:
                st.markdown("### 📝 Validasi Real Market (Day Trading)")
                if tren_harian == "DOWNTREND 🔴" and skor_utama >= 60:
                    st.warning("⚠️ **REBOUND PLAY (Scalping Only):** Tren makro turun, tapi ada momentum *mark-up* intraday. Wajib *Fast In, Fast Out* (Hit & Run). Dilarang keras menahan barang sampai besok!")
                elif tren_harian == "DOWNTREND 🔴": 
                    st.error("❌ **Trend Hancur & Tanpa Momentum:** Melawan arus tanpa ada tanda perlawanan intraday. Skip!")
                elif lot_by_liquidity < 100:
                    st.error("❌ **Saham Sepi (Illiquid):** Transaksi sangat tipis. Rawan tidak bisa jualan (nyangkut) jika masuk barang.")
                elif persen_kenaikan > 8.0: 
                    st.error("❌ **Ekstrem FOMO:** Harga sudah terbang. Hindari menjadi \"Exit Liquidity\" (tempat jualan) bandar di pucuk.")
                else: 
                    st.success("🚀 **Clear for Takeoff:** Trend besar mendukung, akumulasi intraday aktif, likuiditas memadai.")
                    
            st.markdown("---")
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df_5m.index, open=df_5m['Open'], high=df_5m['High'], low=df_5m['Low'], close=df_5m['Close'], name="Harga"))
            fig.add_trace(go.Scatter(x=df_5m.index, y=df_5m['VWAP'], line=dict(color='#3b82f6', width=2), name='VWAP'))
            fig.update_layout(template="plotly_dark", height=400, xaxis_rangeslider_visible=False, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader(f"📰 Katalis Media: {ticker_utama}")
            berita_lokal = ambil_berita_indonesia(ticker_utama)
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔹 **[{item['title']}]({item['link']})**")
                    st.caption(f"🗞️ Sumber: {item['source']} | 🕒 {item['date']}")
            else:
                st.info("Market sedang hening. Tidak ada katalis berita utama.")
else:
    st.error("Gagal menarik data. Pastikan format ticker benar (contoh: BBCA).")

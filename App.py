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
st.set_page_config(page_title="Trading Plan Pro V7.2", layout="wide", page_icon="🦅")

# --- 1. FUNGSI INDIKATOR (CORE ENGINE) ---
def calculate_indicators(df):
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    df['Date'] = df.index.date
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TP_Vol'] = df['TP'] * df['Volume']
    df['Cum_Vol'] = df.groupby('Date')['Volume'].cumsum()
    df['Cum_TP_Vol'] = df.groupby('Date')['TP_Vol'].cumsum()
    df['VWAP'] = df['Cum_TP_Vol'] / df['Cum_Vol']
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=14).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    hl, hc, lc = df['High']-df['Low'], np.abs(df['High']-df['Close'].shift()), np.abs(df['Low']-df['Close'].shift())
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
            curr = df.iloc[-1]
            
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
        except: continue
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
    except Exception:
        pass
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
            if len(hist_div) > 1:
                info_dividen["terakhir"] = format_dividen(hist_div.index[-2], float(hist_div.iloc[-2]))
        else:
            info_dividen["terakhir"] = data_akhir
        return info_dividen
    except: return {"ada": False}

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
                    cum_date = ex_date - pd.offsets.BDay(1)
                    upcoming_list.append({
                        "Emiten": ticker, "Cum Date": cum_date.strftime('%d %b %Y'),
                        "Ex Date": ex_date.strftime('%d %b %Y'), "Nominal": f"Rp {nominal:,.0f}"
                    })
        except: continue
    if upcoming_list:
        df = pd.DataFrame(upcoming_list)
        df['SortDate'] = pd.to_datetime(df['Ex Date'])
        return df.sort_values(by='SortDate').drop(columns=['SortDate'])
    return pd.DataFrame()

@st.cache_data(ttl=300)
def get_market_data(ticker):
    try:
        df_5m = yf.download(f"{ticker}.JK", period="5d", interval="5m", progress=False)
        df_1d = yf.download(f"{ticker}.JK", period="3mo", interval="1d", progress=False)
        if not df_5m.empty and isinstance(df_5m.columns, pd.MultiIndex): df_5m.columns = df_5m.columns.get_level_values(0)
        if not df_1d.empty and isinstance(df_1d.columns, pd.MultiIndex): df_1d.columns = df_1d.columns.get_level_values(0)
        return df_5m, df_1d
    except: return pd.DataFrame(), pd.DataFrame()

# --- 4. UI SIDEBAR PENGATURAN ---
with st.sidebar:
    st.markdown("### ⚙️ Parameter Trading")
    ticker_utama = st.text_input("Analisis Saham Spesifik:", "PSAB").upper()
    modal_trading = st.number_input("Total Modal (Rp):", value=10000000, step=1000000)
    risiko_persen = st.slider("Risiko per Trade (%):", 0.1, 5.0, 1.0) / 100
    
    st.markdown("---")
    st.markdown("### 📋 Daftar Pantauan (Scanner)")
    st.caption("Ketik kode saham dipisahkan dengan koma (,):")
    
    saham_input_user = st.text_input(
        "Daftar Saham:", 
        value="PTBA, ADRO, BRMS, PANI, AMMN, BBCA, BMRI, ASII, PSAB"
    )
    daftar_pantauan = [s.strip().upper() for s in saham_input_user.split(",") if s.strip()]

# --- 5. UI MAIN: TOP REKOMENDASI ---
st.title("🦅 TRADING PLAN PRO V7.2")

st.subheader("🏆 Top 3 Rekomendasi Setup Hari Ini (5-Min)")
st.caption("Memindai saham di Watchlist yang diakumulasi di atas VWAP (Update tiap 5 menit)")

with st.spinner("Memindai setup probabilitas tinggi dari daftar pantauan Anda..."):
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
                <p style="margin: 0; color: #9CA3AF; font-size: 14px;">Skor VWAP & Momentum</p>
                <hr style="border-color: #374151; margin: 10px 0;">
                <p style="margin: 0; color: white; font-weight: bold;">Harga: Rp {data['harga']:,.0f}</p>
                <p style="margin: 0; color: #60A5FA; font-size: 13px;">Garis VWAP: Rp {data['vwap']:,.0f}</p>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Market sedang tidak bersahabat atau konsolidasi. Belum ada setup ideal (Skor > 60) dari Watchlist Anda.")

st.markdown("---")

# --- 6. UI MAIN: DEEP DIVE ANALISIS ---
st.subheader(f"🔎 Deep Dive Analisis: {ticker_utama}")

df_5m, df_1d = get_market_data(ticker_utama)
dividen_data = ambil_dividen_akurat(f"{ticker_utama}.JK")

if not df_5m.empty and not df_1d.empty:
    df_5m = calculate_indicators(df_5m)
    curr_5m = df_5m.iloc[-1]
    
    ma20_daily = df_1d['Close'].rolling(20).mean().iloc[-1]
    tren_harian = "UPTREND 🟢" if df_1d['Close'].iloc[-1] > ma20_daily else "DOWNTREND 🔴"
    
    entry, atr = curr_5m['Close'], curr_5m['ATR']
    sl, tp = entry - (atr * 1.5), entry + (atr * 3.0)
    
    jarak_sl = entry - sl
    total_lot = int(((modal_trading * risiko_persen) / jarak_sl) / 100) if jarak_sl > 0 else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tren (Daily)", tren_harian)
    c2.metric("Posisi Thd VWAP", f"Rp {curr_5m['VWAP']:,.0f}", "BULLISH" if entry > curr_5m['VWAP'] else "BEARISH", delta_color="normal" if entry > curr_5m['VWAP'] else "inverse")
    c3.metric("Harga Saat Ini", f"Rp {entry:,.0f}")
    c4.metric("Rekomendasi Max Lot", f"{total_lot} Lot")
    
    tab1, tab2, tab3 = st.tabs(["📊 Chart & Berita", "📋 Setup Eksekusi", "💰 Kalender Dividen"])
    
    with tab1:
        # Menampilkan Grafik
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df_5m.index, open=df_5m['Open'], high=df_5m['High'], low=df_5m['Low'], close=df_5m['Close'], name="Harga"))
        fig.add_trace(go.Scatter(x=df_5m.index, y=df_5m['VWAP'], line=dict(color='#3b82f6', width=2), name='VWAP'))
        fig.add_trace(go.Scatter(x=df_5m.index, y=df_5m['EMA20'], line=dict(color='#fbbf24', width=1.5, dash='dot'), name='EMA 20'))
        fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Menampilkan Berita Fundamental
        st.subheader(f"📰 Sentimen & Berita Terbaru: {ticker_utama}")
        with st.spinner(f"Menarik berita terkini untuk {ticker_utama}..."):
            berita_lokal = ambil_berita_indonesia(ticker_utama)
            
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔹 **[{item['title']}]({item['link']})**")
                    st.caption(f"🗞️ Sumber: {item['source']} | 🕒 {item['date']}")
            else:
                st.info("Tidak ada katalis berita utama yang ditemukan untuk emiten ini dalam waktu dekat.")

    with tab2:
        col_plan, col_rules = st.columns([1.5, 1])
        with col_plan:
            st.success(f"🎯 **TAKE PROFIT:** Rp {tp:,.0f}")
            st.error(f"🛑 **STOP LOSS:** Rp {sl:,.0f} (Potensi Rugi: Rp {modal_trading * risiko_persen:,.0f})")
        with col_rules:
            if tren_harian == "DOWNTREND 🔴": st.error("⚠️ Hindari transaksi (Tren turun kuat).")
            elif entry < curr_5m['VWAP']: st.warning("⏳ Wait & See (Harga di bawah rata-rata institusi).")
            else: st.success("🔥 Setup Ideal (Harga > VWAP & Uptrend).")

    with tab3:
        st.subheader("📅 Jadwal Dividen Mendatang (Dari Watchlist)")
        with st.spinner("Menarik data jadwal aksi korporasi..."):
            df_kalender = scan_kalender_dividen(daftar_pantauan)
            if not df_kalender.empty:
                st.dataframe(df_kalender.style.set_properties(**{'background-color': '#1f2937', 'color': '#10B981'}), use_container_width=True, hide_index=True)
            else:
                st.info("Tidak ada jadwal dividen terdekat untuk saham di dalam Watchlist Anda.")
                
        st.markdown("---")
        
        st.subheader(f"ℹ️ Status Dividen Spesifik: {ticker_utama}")
        if dividen_data["ada"]:
            if dividen_data["status_upcoming"]:
                u = dividen_data["upcoming"]
                st.success(f"**📢 AKAN DATANG:** {u['nominal']} | Cum: {u['cum_date']} | Ex: {u['ex_date']}")
            if dividen_data["terakhir"]:
                t = dividen_data["terakhir"]
                st.markdown(f"**🕰️ Riwayat Terakhir:** {t['nominal']} (Ex-Date: {t['ex_date']})")
        else:
            st.warning("Tidak ada riwayat pembagian dividen yang tercatat.")
else:
    st.error("Gagal menarik data detail. Pastikan format ticker benar.")

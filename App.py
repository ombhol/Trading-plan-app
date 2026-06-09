import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import concurrent.futures
import requests
import math
import time
from bs4 import BeautifulSoup

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Trading Plan Pro V8.2", layout="wide", page_icon="🦅")

# --- 1. FUNGSI REAL-TIME GOOGLE FINANCE (HANYA UNTUK DEEP DIVE) ---
def ambil_harga_realtime_google(ticker):
    """Mengambil harga saham BEI real-time dari Google Finance secara aman (Single Request)."""
    url = f"https://www.google.com/finance/quote/{ticker}:IDX"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            elemen_harga = soup.find('div', {'class': 'ymr60b'})
            if elemen_harga:
                harga_teks = elemen_harga.text.replace("Rp", "").replace(".", "").replace(",", "").strip()
                return float(harga_teks)
    except Exception:
        pass
    return None

# --- 2. FUNGSI UTILITAS & LOGIKA LAPANGAN BEI ---
def sesuaikan_fraksi_bei(harga, tipe='normal'):
    harga = int(round(harga))
    if harga < 50: return 50
    elif harga < 200: fraksi = 1
    elif harga < 500: fraksi = 2
    elif harga < 2000: fraksi = 5
    elif harga < 5000: fraksi = 10
    else: fraksi = 25
    
    if tipe in ['sl', 'tp']:
        return math.floor(harga / fraksi) * fraksi
    else:
        return round(harga / fraksi) * fraksi

def hitung_batas_ara_arb(close_kemarin):
    if close_kemarin < 200:
        limit = 0.35 
    elif close_kemarin <= 5000:
        limit = 0.25 
    else:
        limit = 0.20 
        
    ara = sesuaikan_fraksi_bei(close_kemarin * (1 + limit))
    arb = sesuaikan_fraksi_bei(close_kemarin * (1 - limit))
    
    if arb < 50: arb = 50 
    return ara, arb

def calculate_daily_atr(df_1d):
    if df_1d.empty or len(df_1d) < 15: return 0
    hl = df_1d['High'] - df_1d['Low']
    hc = np.abs(df_1d['High'] - df_1d['Close'].shift())
    lc = np.abs(df_1d['Low'] - df_1d['Close'].shift())
    atr_daily = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return atr_daily.iloc[-1]

def clean_yfinance_columns(df):
    """Pembersihan paksa MultiIndex dari yfinance versi 0.2.40+"""
    if not df.empty and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def calculate_indicators(df):
    if df.empty: return df
    
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['Date'] = df.index.date
    
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TP_Vol'] = df['TP'] * df['Volume']
    df['Cum_Vol'] = df.groupby('Date')['Volume'].cumsum()
    df['Cum_TP_Vol'] = df.groupby('Date')['TP_Vol'].cumsum()
    df['VWAP'] = df['Cum_TP_Vol'] / df['Cum_Vol'].replace(0, np.nan)
    
    # Proteksi NaN pada Wilder's Smoothing RSI
    delta = df['Close'].diff().fillna(0)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=1, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=1, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    hl = df['High'] - df['Low']
    hc = np.abs(df['High'] - df['Close'].shift())
    lc = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['Turnover_5m'] = df['Volume'] * df['Close']
    df['Turnover_MA20'] = df['Turnover_5m'].rolling(20).mean()
    
    return df

# --- 3. FUNGSI AUTO-SCANNER ---
def proses_satu_saham(ticker):
    try:
        # Tanpa session global untuk mencegah ConnectionResetError pada Threading
        df = yf.download(f"{ticker}.JK", period="5d", interval="5m", progress=False)
        df = clean_yfinance_columns(df)
        if df.empty: return None
        
        df = calculate_indicators(df)
        df_clean = df.dropna(subset=['VWAP', 'EMA20', 'Turnover_MA20'])
        if df_clean.empty: return None
        
        curr = df_clean.iloc[-1]
        if curr['Close'] <= 50 or curr['Turnover_MA20'] < 100000000:
            return None
            
        skor = 0
        if curr['Close'] > curr['VWAP']: skor += 30
        if curr['Close'] > curr['EMA20']: skor += 20
        if 40 < curr['RSI'] < 65: skor += 20
        elif curr['RSI'] >= 70: skor -= 20
        
        if curr['Volume'] > (curr['Vol_MA20'] * 3): skor += 30
        elif curr['Volume'] > curr['Vol_MA20']: skor += 10
        
        if skor >= 60:
            return {"ticker": ticker, "skor": skor, "harga": float(curr['Close']), "vwap": float(curr['VWAP'])}
    except Exception:
        pass
    return None

@st.cache_data(ttl=60) 
def scan_top_saham(watchlist):
    hasil_scan = []
    # Membatasi thread menjadi 5 agar yfinance tidak IP Ban (Rate limit: 2000 req/hour)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(proses_satu_saham, ticker): ticker for ticker in watchlist}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                hasil_scan.append(result)
    return sorted(hasil_scan, key=lambda x: x['skor'], reverse=True)[:3]

# --- 4. FUNGSI DATA KORPORASI ---
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

@st.cache_data(ttl=60)
def get_market_data(ticker):
    try:
        df_5m = yf.download(f"{ticker}.JK", period="5d", interval="5m", progress=False)
        df_1d = yf.download(f"{ticker}.JK", period="3mo", interval="1d", progress=False)
        
        df_5m = clean_yfinance_columns(df_5m)
        df_1d = clean_yfinance_columns(df_1d)
            
        return df_5m, df_1d
    except Exception: 
        return pd.DataFrame(), pd.DataFrame()

def cek_waktu_trading():
    waktu_sekarang = datetime.utcnow() + timedelta(hours=7)
    jam = waktu_sekarang.hour
    if 9 <= jam < 10: return "Pagi (High Probability - Volatilitas Tinggi) 🔥", "success"
    elif 10 <= jam < 14: return "Siang (Low Probability - Rawan Jebakan / Sideways) ⚠️", "warning"
    else: return "Sore (Fase Penutupan / Mark-up Bandar) 📊", "info"

# --- 5. UI SIDEBAR PENGATURAN ---
with st.sidebar:
    st.markdown("### ⚙️ Parameter Trading (Real Market)")
    ticker_utama = st.text_input("Analisis Saham Spesifik:", "PSAB").upper()
    modal_trading = st.number_input("Total Portofolio (Rp):", value=1000000, step=1000000)
    risiko_persen = st.slider("Risiko per Trade (%):", 0.1, 5.0, 2.0) / 100
    fee_broker = st.number_input("Total Fee Jual+Beli (%):", value=0.4, step=0.1) / 100
    
    st.markdown("---")
    st.markdown("### 📋 Daftar Pantauan (Scanner)")
    saham_input_user = st.text_input("Daftar Saham:", value="MPMX, ASGR, LPPF, ROTI, CNMA, RALS, TAPG, UNIC, KKGI, CITA, PTBA, UNVR, SPTO, FWCT, LPIN, TLDN, BSSR, ADRO, MARK, TPMA, SGRO, TOTL, ARNA, POWR, HRXA, NRCA, MSTI, EAST, ACES, TOTO, SIDO, AUTO, TLKM")
    daftar_pantauan = [s.strip().upper() for s in saham_input_user.split(",") if s.strip()]

# --- 6. UI MAIN: TOP REKOMENDASI ---
st.title("🦅 TRADING PLAN PRO V8.2 (Street Smart Edition)")

status_waktu, warna_waktu = cek_waktu_trading()
getattr(st, warna_waktu)(f"🕒 **Sesi Trading BEI Saat Ini:** {status_waktu}")

st.subheader("🏆 Top 3 Sinyal (Real Turnover > 100 Jt/5 Menit)")
with st.spinner("Memindai radar uang pintar secara paralel..."):
    top_3 = scan_top_saham(daftar_pantauan)

if top_3:
    cols_top = st.columns(3)
    for i, data in enumerate(top_3):
        warna_skor = "#10B981" if data['skor'] >= 70 else "#FBBF24"
        with cols_top[i]:
            st.markdown(f"""
            <div style="background-color: #1f2937; padding: 20px; border-radius: 12px; border-top: 5px solid {warna_skor}; text-align: center;">
                <h2 style="margin: 0; color: white;">{data['ticker']}</h2>
                <h1 style="margin: 5px 0; color: {warna_skor};">{data['skor']} / 100</h1>
                <hr style="border-color: #374151; margin: 10px 0;">
                <p style="margin: 0; color: white; font-weight: bold;">Harga Indikatif: Rp {data['harga']:,.0f}</p>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Scanner Kosong: Belum ada saham yang memenuhi kriteria.")
st.markdown("---")

# --- 7. UI MAIN: DEEP DIVE ANALISIS ---
st.subheader(f"🔎 Deep Dive Analisis: {ticker_utama}")

df_5m, df_1d = get_market_data(ticker_utama)

if not df_5m.empty and not df_1d.empty:
    
    # [CRITICAL FIX] Injeksi Google Finance HANYA di bagian ini untuk 1 emiten
    harga_realtime_deep = ambil_harga_realtime_google(ticker_utama)
    if harga_realtime_deep and harga_realtime_deep > 0:
        # Menimpa bar terakhir menggunakan index .loc agar aman secara struktur
        df_5m.loc[df_5m.index[-1], 'Close'] = harga_realtime_deep
        st.success(f"⚡ **Real-time Engine Active:** Terhubung ke Google Finance (Harga Live: Rp {harga_realtime_deep:,.0f})")
    else:
        st.warning("⚠️ **Mode Delay Active:** Gagal sinkronisasi Google. Menggunakan data yfinance (Delay 15 Menit).")
        
    df_5m = calculate_indicators(df_5m)
    df_clean = df_5m.dropna(subset=['VWAP', 'EMA20', 'Turnover_MA20'])
    
    if df_clean.empty:
        st.warning("Data kurang atau saham baru IPO/Suspen.")
    else:
        curr_5m = df_clean.iloc[-1]
        entry = float(curr_5m['Close'])
        
        if entry <= 50:
            st.error("🚨 SAHAM GOCAP (Rp 50): Sistem dihentikan demi keselamatan portofolio.")
            st.stop()
            
        ma20_daily = df_1d['Close'].rolling(20).mean().iloc[-1]
        tren_harian = "UPTREND 🟢" if df_1d['Close'].iloc[-1] > ma20_daily else "DOWNTREND 🔴"
        
        close_kemarin = float(df_1d['Close'].iloc[-2]) if len(df_1d) > 1 else entry
        persen_kenaikan = ((entry - close_kemarin) / close_kemarin) * 100 if close_kemarin > 0 else 0
        
        # Batas ARA / ARB
        batas_ara, batas_arb = hitung_batas_ara_arb(close_kemarin)
        
        atr_daily = calculate_daily_atr(df_1d)
        atr_final = atr_daily if atr_daily > 0 else (float(curr_5m['ATR']) * 5)
        
        # Stop Loss & Take Profit logic
        sl_mentah = entry - (atr_final * 1.0)
        sl = sesuaikan_fraksi_bei(sl_mentah, 'sl')
        if sl <= batas_arb: sl = batas_arb
            
        batas_tp_min = entry * (1 + fee_broker + 0.005) 
        tp1_mentah = entry + (float(curr_5m['ATR']) * 3.0) 
        if tp1_mentah < batas_tp_min: tp1_mentah = batas_tp_min
        
        tp2_mentah = entry + (atr_final * 0.5) 
        if tp2_mentah <= tp1_mentah: tp2_mentah = tp1_mentah + (float(curr_5m['ATR']) * 3.0)
            
        tp1 = sesuaikan_fraksi_bei(tp1_mentah, 'tp')
        tp2 = sesuaikan_fraksi_bei(tp2_mentah, 'tp')
        
        if tp1 > batas_ara: tp1 = batas_ara
        if tp2 > batas_ara: tp2 = batas_ara
        
        # Safe Lot Management
        jarak_sl_rp = entry - sl
        lot_by_risk = int(((modal_trading * risiko_persen) / max(1, jarak_sl_rp)) / 100) if jarak_sl_rp > 0 else 0
        
        rata_volume_pasar_lot = float(curr_5m['Vol_MA20']) / 100
        lot_by_liquidity = int(rata_volume_pasar_lot * 0.05) 
        total_lot = min(lot_by_risk, lot_by_liquidity)
        
        turnover_5m_rata_rata = float(curr_5m['Turnover_MA20'])
        
        skor_utama = 0
        if entry > curr_5m['VWAP']: skor_utama += 30
        if entry > curr_5m['EMA20']: skor_utama += 20
        if 40 < curr_5m['RSI'] < 65: skor_utama += 20
        elif curr_5m['RSI'] >= 70: skor_utama -= 20
        
        if curr_5m['Volume'] > (curr_5m['Vol_MA20'] * 3): skor_utama += 30
        elif curr_5m['Volume'] > curr_5m['Vol_MA20']: skor_utama += 10
        
        vwap_val = float(curr_5m['VWAP']) if pd.notnull(curr_5m['VWAP']) else 0
        jarak_vwap_persen = ((entry - vwap_val) / vwap_val * 100) if vwap_val > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tren (Daily)", tren_harian)
        c2.metric("Harga VWAP", f"Rp {vwap_val:,.0f}", f"{jarak_vwap_persen:+.2f}%", delta_color="normal" if entry > vwap_val else "inverse")
        c3.metric("Harga Saat Ini", f"Rp {entry:,.0f}", f"{persen_kenaikan:+.2f}%")
        
        with c4:
            alasan_lot = "Dibatasi Likuiditas" if lot_by_liquidity < lot_by_risk else "Sesuai Risk Profile"
            st.metric("Safe Lot Size", f"{total_lot} Lot", alasan_lot)
            st.metric("Skor Saham", f"{skor_utama} / 100")
        
        tab1, tab2, tab3 = st.tabs(["📊 Eksekusi Order & Net PnL", "📰 Sentimen & Berita", "Rules"])
        
        with tab1:
            col_plan, col_rules = st.columns([1.5, 1])
            entry_cicil_1 = sesuaikan_fraksi_bei(entry)
            entry_cicil_2 = sesuaikan_fraksi_bei(vwap_val) if vwap_val > 0 else entry
            if entry_cicil_2 >= entry_cicil_1: entry_cicil_2 = sesuaikan_fraksi_bei(float(curr_5m['EMA20']))

            with col_plan:
                st.markdown("### 🎯 Skenario Entry Anti-Guyur")
                if persen_kenaikan > 5.5 or jarak_vwap_persen > 2.5:
                    st.warning(f"🚨 **RAWAN GUYURAN:** Harga sudah melesat jauh dari rata-rata modal bandar (VWAP).")
                    st.write(f"🔹 **Tranche 1 (Test Water - 30%):** Rp {entry_cicil_1}")
                    st.write(f"🔥 **Tranche 2 (Pullback - 70%):** Rp {entry_cicil_2}")
                else:
                    st.success("✅ **ZONA AKUMULASI AMAN:** Harga merapat ke ekuilibrium market harian.")
                    st.write(f"🔹 **Tranche 1 (Masuk Awal - 50%):** Rp {entry_cicil_1}")
                    st.write(f"🔹 **Tranche 2 (Jaring Bawah - 50%):** Rp {entry_cicil_2}")

                st.markdown("---")
                st.markdown("### 🛡️ Target Realisasi Cuan")
                
                modal_terpakai = entry * total_lot * 100
                if modal_terpakai > 0:
                    jual_tp1_val = tp1 * total_lot * 100
                    estimasi_fee_tp1 = (modal_terpakai + jual_tp1_val) * fee_broker
                    net_rp_tp1 = (jual_tp1_val - modal_terpakai) - estimasi_fee_tp1
                    net_persen_tp1 = (net_rp_tp1 / modal_terpakai) * 100
                    
                    jual_tp2_val = tp2 * total_lot * 100
                    estimasi_fee_turn = (modal_terpakai + jual_tp2_val) * fee_broker
                    net_rp_tp2 = (jual_tp2_val - modal_terpakai) - estimasi_fee_turn
                    net_persen_tp2 = (net_rp_tp2 / modal_terpakai) * 100
                    
                    if net_persen_tp1 <= 0:
                        st.error(f"⚠️ **TP1 (Rp {tp1:,}):** Margin dihabiskan oleh fee broker.")
                    else:
                        st.success(f"🎯 **TP1 (Quick Scalp 50%): Rp {tp1:,}** | Nett: {net_persen_tp1:.1f}% (~Rp {net_rp_tp1:,.0f})")
                        
                    st.info(f"🚀 **TP2 (Swing Intraday): Rp {tp2:,}** | Nett: {net_persen_tp2:.1f}% (~Rp {net_rp_tp2:,.0f})")
                else:
                    st.warning("Lot size 0. Jarak Stop Loss terlalu lebar atau Likuiditas mati.")
                    
                st.error(f"📉 **STOP LOSS STRICT:** Rp {sl:,.0f} *(Batas ARB Hari Ini: Rp {batas_arb:,.0f})*")
                
            with col_rules:
                st.markdown("### 📝 Validasi Real Market")
                if turnover_5m_rata_rata < 100000000:
                    st.error(f"❌ **Saham Ilusi (Low Turnover):** Omset 5 mnt hanya Rp {turnover_5m_rata_rata/1000000:,.1f} Jt. Rawan manipulasi Bid/Offer!")
                elif tren_harian == "DOWNTREND 🔴" and skor_utama >= 60:
                    st.warning("⚠️ **REBOUND PLAY:** Spekulatif pantulan cepat. Wajib Hit & Run!")
                elif tren_harian == "DOWNTREND 🔴": 
                    st.error("❌ **Trend Hancur:** Market membuang emiten ini. Jangan menahan pisau jatuh.")
                elif persen_kenaikan > 8.0: 
                    st.error("❌ **Ekstrem FOMO:** Hindari masuk di zona pucuk harian.")
                else: 
                    st.success("🚀 **Clear for Takeoff:** Momentum dan struktur uptrend valid.")
                    
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
                st.info("Market hening. Tidak ada sentimen berita penggerak.")
                
        with tab3:
            st.subheader("⚠️ SOP Day Trader BEI")
            st.markdown("""
            * **Keamanan Anti-Ban:** Sistem telah menggunakan eksekusi asinkronus (yfinance) untuk *Scanner* guna mengamankan server dari blokir IP, sementara bagian analisa mendalam (Deep Dive) di-*inject* presisi *real-time* lewat Google Finance.
            * **Disiplin Cut Loss:** Eksekusi Stop-Loss tanpa ampun bila harga menyentuh angka 'Stop Loss Strict'.
            """)
else:
    st.error("Gagal menarik data. Pastikan format ticker benar (contoh: BBCA) dan koneksi server aktif.")

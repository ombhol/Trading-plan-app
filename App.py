import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import numpy as np
from datetime import date

# Konfigurasi Layout
st.set_page_config(page_title="Trading Plan Pro V5.1", layout="wide", page_icon="🦅")

# --- FUNGSI DIVIDEN AKURAT ---
@st.cache_data(ttl=3600)
def ambil_dividen_akurat(ticker_code):
    try:
        ticker_obj = yf.Ticker(ticker_code)
        hist_div = ticker_obj.dividends
        
        if hist_div.empty:
            return {"ada": False}
            
        # HAPUS Timezone agar komparasi tanggal tidak meleset dengan jam lokal
        hist_div.index = pd.to_datetime(hist_div.index).tz_localize(None)
        today = pd.Timestamp(date.today())
        
        info_dividen = {"ada": True, "status_upcoming": False, "terakhir": None, "upcoming": None}
        
        def format_dividen(ex_date, nominal):
            # Cum date 1 Hari Kerja sebelum Ex-Date
            cum_date = ex_date - pd.offsets.BDay(1)
            # Recording date 1 Hari Kerja setelah Ex-Date
            recording_date = ex_date + pd.offsets.BDay(1)
            
            return {
                "nominal": f"Rp {nominal:,.2f}",
                "cum_date": cum_date.strftime('%d %b %Y'),
                "ex_date": ex_date.strftime('%d %b %Y'),
                "rec_date": recording_date.strftime('%d %b %Y'),
                "tanggal_asli": ex_date
            }

        last_ex_date = hist_div.index[-1]
        last_nominal = float(hist_div.iloc[-1])
        data_paling_akhir = format_dividen(last_ex_date, last_nominal)
        
        # Logika Upcoming vs History
        if data_paling_akhir["tanggal_asli"] >= today:
            info_dividen["status_upcoming"] = True
            info_dividen["upcoming"] = data_paling_akhir
            if len(hist_div) > 1:
                prev_ex_date = hist_div.index[-2]
                prev_nominal = float(hist_div.iloc[-2])
                info_dividen["terakhir"] = format_dividen(prev_ex_date, prev_nominal)
        else:
            info_dividen["terakhir"] = data_paling_akhir
            
        return info_dividen
    except Exception as e:
        return {"ada": False, "error": str(e)}

# --- FUNGSI PENGAMBILAN DATA (MULTI-TIMEFRAME) ---
@st.cache_data(ttl=300)
def get_market_data(ticker):
    try:
        df_5m = yf.download(f"{ticker}.JK", period="5d", interval="5m", progress=False)
        df_1d = yf.download(f"{ticker}.JK", period="3mo", interval="1d", progress=False)
        
        if not df_5m.empty and isinstance(df_5m.columns, pd.MultiIndex):
            df_5m.columns = df_5m.columns.get_level_values(0)
        if not df_1d.empty and isinstance(df_1d.columns, pd.MultiIndex):
            df_1d.columns = df_1d.columns.get_level_values(0)
            
        return df_5m, df_1d
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

def calculate_advanced_indicators(df):
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # VWAP
    df['Date'] = df.index.date
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TP_Volume'] = df['Typical_Price'] * df['Volume']
    df['Cum_Volume'] = df.groupby('Date')['Volume'].cumsum()
    df['Cum_TP_Volume'] = df.groupby('Date')['TP_Volume'].cumsum()
    df['VWAP'] = df['Cum_TP_Volume'] / df['Cum_Volume']
    
    # ATR
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    return df

# --- UI SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Parameter Trading")
    ticker = st.text_input("Kode Saham (Contoh: BBCA):", "BBCA").upper()
    modal_trading = st.number_input("Total Modal (Rp):", value=10000000, step=1000000)
    risiko_persen = st.slider("Risiko per Trade (%):", 0.1, 5.0, 1.0) / 100
    st.markdown("---")
    st.caption("🟢 Harga > VWAP = Bullish")
    st.caption("🔴 Harga < VWAP = Bearish")

# --- MAIN LOGIC ---
st.title(f"🦅 {ticker} - Professional Trading Dashboard")

df_5m, df_1d = get_market_data(ticker)
dividen_data = ambil_dividen_akurat(f"{ticker}.JK")

if not df_5m.empty and not df_1d.empty:
    df_5m = calculate_advanced_indicators(df_5m)
    curr_5m = df_5m.iloc[-1]
    
    ma20_daily = df_1d['Close'].rolling(20).mean().iloc[-1]
    tren_harian = "UPTREND 🟢" if df_1d['Close'].iloc[-1] > ma20_daily else "DOWNTREND 🔴"
    
    entry = curr_5m['Close']
    sl = entry - (curr_5m['ATR'] * 1.5)
    tp = entry + (curr_5m['ATR'] * 3.0)
    jarak_sl = entry - sl
    
    jumlah_rupiah_risiko = modal_trading * risiko_persen
    total_lot = int((jumlah_rupiah_risiko / jarak_sl) / 100) if jarak_sl > 0 else 0
    
    # --- METRIK UTAMA ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tren Harian (Daily)", tren_harian)
    c2.metric("Posisi Thd VWAP", f"Rp {curr_5m['VWAP']:,.0f}", "Diatas Rata-rata Institusi" if entry > curr_5m['VWAP'] else "Dibawah Rata-rata", delta_color="normal" if entry > curr_5m['VWAP'] else "inverse")
    c3.metric("Rekomendasi Entry", f"Rp {entry:,.0f}")
    c4.metric("Maksimal Lot", f"{total_lot} Lot")
    
    st.markdown("---")
    
    # --- TABS LAYOUT ---
    tab1, tab2, tab3 = st.tabs(["📊 Chart & Indikator", "📋 Action Plan Detail", "💰 Info Dividen & Korporasi"])
    
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df_5m.index, open=df_5m['Open'], high=df_5m['High'], low=df_5m['Low'], close=df_5m['Close'], name="Harga 5M"))
        fig.add_trace(go.Scatter(x=df_5m.index, y=df_5m['VWAP'], line=dict(color='#3b82f6', width=2), name='VWAP (Bandar Line)'))
        fig.add_trace(go.Scatter(x=df_5m.index, y=df_5m['EMA20'], line=dict(color='#fbbf24', width=1.5, dash='dot'), name='EMA 20'))
        
        fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0, r=0, t=10, b=0), xaxis_rangeslider_visible=False, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        col_plan, col_rules = st.columns([1.5, 1])
        with col_plan:
            st.subheader("🎯 Eksekusi Trading")
            st.success(f"**TAKE PROFIT (TP):** Rp {tp:,.0f} \n\n*Jual parsial jika harga mulai melambat di dekat area ini.*")
            st.error(f"**STOP LOSS (SL):** Rp {sl:,.0f} \n\n*Cut loss tanpa ragu jika candle 5M ditutup di bawah level ini.*")
            st.warning(f"**RISK EXPOSURE:** Rp {jumlah_rupiah_risiko:,.0f} \n\n*Ini adalah nominal maksimal yang akan Anda hilangkan jika terkena SL.*")
            
        with col_rules:
            st.subheader("⚖️ Kondisi Market Saat Ini")
            if tren_harian == "DOWNTREND 🔴":
                st.error("⚠️ **Peringatan Keras:** Tren harian turun. Risiko nyangkut tinggi.")
            elif entry < curr_5m['VWAP']:
                st.warning("⏳ **Wait & See:** Harga di bawah VWAP. Institusi belum akumulasi penuh.")
            elif entry > curr_5m['VWAP'] and entry > curr_5m['EMA20']:
                st.success("🔥 **Clear to Launch:** Setup probabilitas tinggi. Momentum mendukung.")
            else:
                st.info("🔄 **Fase Konsolidasi:** Market sideway/belum jelas.")

    with tab3:
        st.subheader("Jadwal Pembagian Dividen")
        col_div1, col_div2 = st.columns(2)
        
        with col_div1:
            if dividen_data["ada"]:
                if dividen_data["status_upcoming"]:
                    upc = dividen_data["upcoming"]
                    st.success("📢 **DIVIDEN AKAN DATANG!**")
                    st.markdown(f"**Nominal:** `{upc['nominal']} / lembar`")
                    st.markdown(f"🛒 **Cum Date:** `{upc['cum_date']}`")
                    st.markdown(f"🛑 **Ex Date:** `{upc['ex_date']}`")
                    st.markdown(f"📝 **Rec Date:** `{upc['rec_date']}`")
                else:
                    st.info("Belum ada pengumuman dividen baru dalam waktu dekat.")
            else:
                st.warning("Tidak ada data pembagian dividen untuk emiten ini.")
                
        with col_div2:
            if dividen_data["ada"] and dividen_data["terakhir"]:
                ter = dividen_data["terakhir"]
                st.markdown("🕰️ **RIWAYAT TERAKHIR DIBAGIKAN:**")
                st.markdown(f"**Nominal:** `{ter['nominal']} / lembar`")
                st.markdown(f"- Cum Date: {ter['cum_date']}")
                st.markdown(f"- Ex Date: {ter['ex_date']}")
            
        st.caption("ℹ️ *Data korporasi ditarik dari database global. Untuk keperluan Cum-Date pasar reguler, selalu lakukan verifikasi silang (cross-check) dengan pengumuman resmi KSEI.*")

else:
    st.error("Gagal menarik data. Pastikan format kode saham benar (contoh: BBCA) dan koneksi internet Anda stabil.")

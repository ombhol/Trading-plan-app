# app.py

import streamlit as st
import pandas as pd

# Import Settings & Config
from config.settings import APP_TITLE, APP_ICON, SOP_TEXT

# Import UI Components
from ui.sidebar import render_sidebar
from ui.charts import buat_chart_intraday

# Import Core Logics
from core.bei_rules import cek_waktu_trading, hitung_batas_ara_arb, sesuaikan_fraksi_bei
from core.indicators import calculate_indicators, calculate_daily_atr
from core.data_fetcher import (
    get_market_data, ambil_harga_realtime_google, 
    scan_top_saham, ambil_berita_indonesia
)

# 1. Konfigurasi Halaman Utama
st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon=APP_ICON)

# 2. Render Sidebar
ticker_utama, modal_trading, risiko_persen, fee_broker, daftar_pantauan = render_sidebar()

# 3. Header & Sesi Waktu
st.title(f"{APP_ICON} {APP_TITLE} (Street Smart Edition)")
status_waktu, warna_waktu = cek_waktu_trading()
getattr(st, warna_waktu)(f"🕒 **Sesi Trading BEI Saat Ini:** {status_waktu}")

# 4. Fitur Scanner Top 3
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

# 5. Deep Dive Analisis Saham Spesifik
st.subheader(f"🔎 Deep Dive Analisis: {ticker_utama}")
df_5m, df_1d = get_market_data(ticker_utama)

if not df_5m.empty and not df_1d.empty:
    
    # Injeksi Harga Real-Time Google
    harga_realtime_deep = ambil_harga_realtime_google(ticker_utama)
    if harga_realtime_deep and harga_realtime_deep > 0:
        df_5m.loc[df_5m.index[-1], 'Close'] = harga_realtime_deep
        st.success(f"⚡ **Real-time Engine Active:** Terhubung ke Google Finance (Harga Live: Rp {harga_realtime_deep:,.0f})")
    else:
        st.warning("⚠️ **Mode Delay Active:** Gagal sinkronisasi Google. Menggunakan data yfinance.")
        
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
        
        # Kalkulasi Parameter Intraday
        batas_ara, batas_arb = hitung_batas_ara_arb(close_kemarin)
        atr_daily = calculate_daily_atr(df_1d)
        atr_final = atr_daily if atr_daily > 0 else (float(curr_5m['ATR']) * 5)
        
        sl = max(sesuaikan_fraksi_bei(entry - (atr_final * 1.0), 'sl'), batas_arb)
        tp1_mentah = max(entry + (float(curr_5m['ATR']) * 3.0), entry * (1 + fee_broker + 0.005))
        tp2_mentah = entry + (atr_final * 0.5) if entry + (atr_final * 0.5) > tp1_mentah else tp1_mentah + (float(curr_5m['ATR']) * 3.0)
        
        tp1 = min(sesuaikan_fraksi_bei(tp1_mentah, 'tp'), batas_ara)
        tp2 = min(sesuaikan_fraksi_bei(tp2_mentah, 'tp'), batas_ara)
        
        jarak_sl_rp = entry - sl
        lot_by_risk = int(((modal_trading * risiko_persen) / max(1, jarak_sl_rp)) / 100) if jarak_sl_rp > 0 else 0
        lot_by_liquidity = int((float(curr_5m['Vol_MA20']) / 100) * 0.05)
        total_lot = min(lot_by_risk, lot_by_liquidity)
        
        # Penilaian Skor Intraday
        skor_utama = sum([
            30 if entry > curr_5m['VWAP'] else 0,
            20 if entry > curr_5m['EMA20'] else 0,
            20 if 40 < curr_5m['RSI'] < 65 else (-20 if curr_5m['RSI'] >= 70 else 0),
            30 if curr_5m['Volume'] > (curr_5m['Vol_MA20'] * 3) else (10 if curr_5m['Volume'] > curr_5m['Vol_MA20'] else 0)
        ])
        
        vwap_val = float(curr_5m['VWAP']) if pd.notnull(curr_5m['VWAP']) else 0
        jarak_vwap_persen = ((entry - vwap_val) / vwap_val * 100) if vwap_val > 0 else 0

        # Render Metrik Atas
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tren (Daily)", tren_harian)
        c2.metric("Harga VWAP", f"Rp {vwap_val:,.0f}", f"{jarak_vwap_persen:+.2f}%", delta_color="normal" if entry > vwap_val else "inverse")
        c3.metric("Harga Saat Ini", f"Rp {entry:,.0f}", f"{persen_kenaikan:+.2f}%")
        c4.metric("Safe Lot Size", f"{total_lot} Lot", "Dibatasi Likuiditas" if lot_by_liquidity < lot_by_risk else "Sesuai Risk Profile")
        
        # Render Tab UI
        tab1, tab2, tab3 = st.tabs(["📊 Eksekusi Order & Net PnL", "📰 Sentimen Berita", "📖 Rules & Panduan"])
        
        with tab1:
            col_plan, col_rules = st.columns([1.5, 1])
            entry_cicil_1 = sesuaikan_fraksi_bei(entry)
            entry_cicil_2 = sesuaikan_fraksi_bei(vwap_val) if vwap_val > 0 else entry
            if entry_cicil_2 >= entry_cicil_1: entry_cicil_2 = sesuaikan_fraksi_bei(float(curr_5m['EMA20']))

            with col_plan:
                st.markdown("### 🎯 Skenario Entry Anti-Guyur")
                if persen_kenaikan > 5.5 or jarak_vwap_persen > 2.5:
                    st.warning("🚨 **RAWAN GUYURAN:** Harga melesat jauh dari modal bandar (VWAP).")
                    st.write(f"🔹 **Tranche 1 (Test Water - 30%):** Rp {entry_cicil_1}")
                    st.write(f"🔥 **Tranche 2 (Pullback - 70%):** Rp {entry_cicil_2}")
                else:
                    st.success("✅ **ZONA AKUMULASI AMAN:** Harga merapat ke ekuilibrium.")
                    st.write(f"🔹 **Tranche 1 (Masuk Awal - 50%):** Rp {entry_cicil_1}")
                    st.write(f"🔹 **Tranche 2 (Jaring Bawah - 50%):** Rp {entry_cicil_2}")

                st.markdown("---")
                st.markdown("### 🛡️ Target Realisasi Cuan")
                modal_terpakai = entry * total_lot * 100
                if modal_terpakai > 0:
                    net_rp_tp1 = (tp1 * total_lot * 100 - modal_terpakai) - ((modal_terpakai + tp1 * total_lot * 100) * fee_broker)
                    net_rp_tp2 = (tp2 * total_lot * 100 - modal_terpakai) - ((modal_terpakai + tp2 * total_lot * 100) * fee_broker)
                    
                    if net_rp_tp1 <= 0:
                        st.error(f"⚠️ **TP1 (Rp {tp1:,}):** Margin dihabiskan oleh fee broker.")
                    else:
                        st.success(f"🎯 **TP1 (Quick Scalp 50%): Rp {tp1:,}** | Nett: {(net_rp_tp1/modal_terpakai)*100:.1f}% (~Rp {net_rp_tp1:,.0f})")
                    st.info(f"🚀 **TP2 (Swing Intraday): Rp {tp2:,}** | Nett: {(net_rp_tp2/modal_terpakai)*100:.1f}% (~Rp {net_rp_tp2:,.0f})")
                else:
                    st.warning("Lot size 0. Jarak Stop Loss terlalu lebar atau Likuiditas mati.")
                    
                st.error(f"📉 **STOP LOSS STRICT:** Rp {sl:,.0f} *(Batas ARB Hari Ini: Rp {batas_arb:,.0f})*")
                
            with col_rules:
                st.markdown("### 📝 Validasi Real Market")
                if float(curr_5m['Turnover_MA20']) < 100000000:
                    st.error("❌ **Saham Ilusi:** Omset kecil. Rawan manipulasi Bid/Offer!")
                elif tren_harian == "DOWNTREND 🔴" and skor_utama >= 60:
                    st.warning("⚠️ **REBOUND PLAY:** Spekulatif pantulan cepat. Wajib Hit & Run!")
                elif tren_harian == "DOWNTREND 🔴": 
                    st.error("❌ **Trend Hancur:** Market membuang emiten ini. Jangan tangkap pisau jatuh.")
                elif persen_kenaikan > 8.0: 
                    st.error("❌ **Ekstrem FOMO:** Hindari masuk di zona pucuk harian.")
                else: 
                    st.success("🚀 **Clear for Takeoff:** Momentum dan struktur uptrend valid.")
                    
            st.markdown("---")
            # Memanggil Modul Chart
            st.plotly_chart(buat_chart_intraday(df_5m), use_container_width=True)

        with tab2:
            st.subheader(f"📰 Katalis Media: {ticker_utama}")
            berita = ambil_berita_indonesia(ticker_utama)
            if berita:
                for item in berita:
                    st.markdown(f"🔹 **[{item['title']}]({item['link']})**")
                    st.caption(f"🗞️ {item['source']} | 🕒 {item['date']}")
            else:
                st.info("Tidak ada sentimen berita penggerak.")
                
        with tab3:
            st.markdown(SOP_TEXT)
else:
    st.error("Gagal menarik data. Pastikan format ticker benar (contoh: BBCA) dan koneksi server aktif.")

import streamlit as st
import pandas as pd
from datetime import date

# Mengatur konfigurasi halaman agar ramah di layar HP
st.set_page_config(page_title="Trading Plan", page_icon="📈", layout="centered")

st.title("📈 Trading Plan Harian")

# Session state untuk menyimpan data selama sesi aktif
if 'trading_data' not in st.session_state:
    st.session_state['trading_data'] = pd.DataFrame(columns=[
        'Tanggal', 'Aset', 'Posisi', 'Entry', 'Stop Loss', 'Take Profit', 'Risk/Reward', 'Catatan'
    ])

st.write("Masukkan rencana trading Anda hari ini:")

with st.form("trading_plan_form"):
    tanggal = st.date_input("Tanggal", date.today())
    aset = st.text_input("Simbol/Aset (Contoh: BTCUSDT, BBCA, EURUSD)")
    posisi = st.selectbox("Arah Posisi", ["Long / Buy", "Short / Sell"])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        entry = st.number_input("Harga Entry", min_value=0.0, format="%.4f")
    with col2:
        stop_loss = st.number_input("Stop Loss (SL)", min_value=0.0, format="%.4f")
    with col3:
        take_profit = st.number_input("Take Profit (TP)", min_value=0.0, format="%.4f")
        
    catatan = st.text_area("Catatan Strategi / Alasan Entry")
    
    submit_button = st.form_submit_button("Simpan Trading Plan")

if submit_button:
    try:
        if posisi == "Long / Buy":
            risk = entry - stop_loss
            reward = take_profit - entry
        else:
            risk = stop_loss - entry
            reward = entry - take_profit
            
        rr_ratio = reward / risk if risk > 0 else 0
        rr_text = f"1 : {rr_ratio:.2f}"
    except Exception:
        rr_text = "Data tidak valid"

    new_data = pd.DataFrame({
        'Tanggal': [tanggal],
        'Aset': [aset],
        'Posisi': [posisi],
        'Entry': [entry],
        'Stop Loss': [stop_loss],
        'Take Profit': [take_profit],
        'Risk/Reward': [rr_text],
        'Catatan': [catatan]
    })
    
    st.session_state['trading_data'] = pd.concat([st.session_state['trading_data'], new_data], ignore_index=True)
    st.success("Trading plan berhasil ditambahkan!")

st.write("### 📋 Rencana & Jurnal Hari Ini")
st.dataframe(st.session_state['trading_data'])

# Fitur Tambahan: Tombol Download Excel/CSV agar data Anda bisa disimpan ke HP
if not st.session_state['trading_data'].empty:
    csv = st.session_state['trading_data'].to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Unduh Hasil Rencana (CSV)",
        data=csv,
        file_name=f"trading_plan_{date.today()}.csv",
        mime='text/csv',
    )

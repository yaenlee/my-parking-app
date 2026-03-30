import streamlit as st
import requests
import pandas as pd
import urllib3
import os

# --- [1] 環境設定 ---
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="停車監控中心", layout="wide")

# --- [2] 初始化 Session State ---
if 'vehicle_list' not in st.session_state:
    st.session_state.vehicle_list = [] # 改成空清單，讓介面從零開始

# --- [3] 定義 Callback 函式 (這就是解決錯誤的關鍵) ---
def add_car_callback():
    # 從暫存區拿值
    new_car = st.session_state.temp_input.upper().strip()
    if new_car and new_car not in st.session_state.vehicle_list:
        st.session_state.vehicle_list.append(new_car)
    # 這裡清空輸入框是安全的，因為是在按鈕觸發的當下執行
    st.session_state.temp_input = ""

def clear_list_callback():
    st.session_state.vehicle_list = []

# --- [4] 查詢邏輯 ---
def fetch_data(car_no, type_code):
    clean_car = car_no.replace('-', '').strip()
    res = {"車號": car_no}
    car_total = 0
    CITY_URLS = {
        "台北市": "https://trafficapi.pma.gov.taipei/Parking/PayBill/CarID/{car}/CarType/{type}",
        "新北市": "https://trafficapi.traffic.ntpc.gov.tw/Parking/PayBill/CarID/{car}/CarType/{type}",
        "桃園市": "https://bill-epark.tycg.gov.tw/Parking/PayBill/CarID/{car}/CarType/{type}"
    }
    headers = {'User-Agent': 'Mozilla/5.0'}
    for city, url in CITY_URLS.items():
        try:
            resp = requests.get(url.format(car=clean_car, type=type_code), timeout=8, verify=False)
            if resp.status_code == 200:
                amt = sum(b.get('Amount', 0) for b in resp.json().get('Bills', []))
                res[city] = f"🔴 {amt}元" if amt > 0 else "🟢 無費用"
                car_total += amt
            else: res[city] = "⚠️ 忙碌"
        except: res[city] = "❌ 異常"
    return res, car_total

# --- [5] UI 佈局 ---
st.title("🚗 全方位停車費監控面板")

with st.sidebar:
    st.header("⚙️ 車庫管理")
    
    # 使用 key="temp_input" 綁定
    st.text_input("➕ 輸入車號", key="temp_input", placeholder="例如: ABC-1234")
    
    col_add, col_clear = st.columns(2)
    with col_add:
        # 使用 on_click 觸發剛才寫好的 Callback
        st.button("新增車號", on_click=add_car_callback, use_container_width=True, type="secondary")
    
    with col_clear:
        st.button("清空清單", on_click=clear_list_callback, use_container_width=True)
    
    st.divider()
    
    selected_targets = st.multiselect(
        "🎯 選擇監控對象",
        options=st.session_state.vehicle_list,
        default=st.session_state.vehicle_list
    )
    
    car_type = st.radio("車種設定", ["汽車", "機車"], horizontal=True)
    t_code = 'C' if car_type == "汽車" else 'M'
    
    start_btn = st.button("🚀 執行多車同步掃描", type="primary", use_container_width=True)

# --- [6] 顯示結果 ---
if start_btn:
    if not selected_targets:
        st.warning("請先新增並勾選車號。")
    else:
        all_results = []
        grand_total = 0
        with st.spinner('掃描中...'):
            for car in selected_targets:
                res, total = fetch_data(car, t_code)
                all_results.append(res)
                grand_total += total
        
        c1, c2 = st.columns(2)
        c1.metric("監控數量", f"{len(selected_targets)} 台")
        c2.metric("總待繳金額", f"{grand_total} 元", delta=f"{grand_total}元" if grand_total > 0 else None, delta_color="inverse")
        
        st.table(pd.DataFrame(all_results).set_index("車號"))
        
        if grand_total > 0:
            st.error("📢 偵測到未繳費項目！")
        else:
            st.success("✅ 目前狀態良好。")

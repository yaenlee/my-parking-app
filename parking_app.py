import streamlit as st
import requests
import pandas as pd
import urllib3
import os

# --- [1] 環境與安全設定 ---
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="停車監控中心", layout="wide")

# --- [2] 初始化 Session State ---
if 'vehicle_list' not in st.session_state:
    st.session_state.vehicle_list = []  # 初始清空，由使用者自行新增

# --- [3] 定義 Callback 函式 (處理邏輯與清空) ---
def add_car_callback():
    # 取得輸入並轉大寫，支援空格、逗號、全形逗號分隔
    raw_input = st.session_state.temp_input.upper().strip()
    if raw_input:
        # 批量切分邏輯
        new_cars = raw_input.replace(',', ' ').replace('，', ' ').replace('\n', ' ').split()
        for car in new_cars:
            car = car.strip()
            if car and car not in st.session_state.vehicle_list:
                st.session_state.vehicle_list.append(car)
        # 成功後自動清空輸入框
        st.session_state.temp_input = ""

def clear_list_callback():
    st.session_state.vehicle_list = []

# --- [4] 核心查詢 API 函式 ---
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

# --- [5] UI 側邊欄佈局 ---
st.title("🚗 北北桃停車費同步監控系統")

with st.sidebar:
    st.header("⚙️ 管理監控清單")
    
    # 輸入框：支援批量
    st.text_input(
        "➕ 新增車號 (支援批量)", 
        key="temp_input", 
        placeholder="多台請用空格或逗號隔開",
        help="例如: ABC-1234, XYZ-5678"
    )
    
    col_add, col_clear = st.columns(2)
    with col_add:
        st.button("確認新增", on_click=add_car_callback, use_container_width=True, type="primary")
    with col_clear:
        st.button("清空清單", on_click=clear_list_callback, use_container_width=True)
    
    st.divider()
    
    # 選擇本次要查的車
    selected_targets = st.multiselect(
        "🎯 選擇監控對象",
        options=st.session_state.vehicle_list,
        default=st.session_state.vehicle_list
    )
    
    car_type = st.radio("車種設定", ["汽車", "機車"], horizontal=True)
    t_code = 'C' if car_type == "汽車" else 'M'
    
    start_btn = st.button("🚀 執行多車同步掃描", use_container_width=True)

# --- [6] 主畫面查詢結果 ---
if start_btn:
    if not selected_targets:
        st.warning("請先在左側新增並勾選車號。")
    else:
        all_results = []
        grand_total = 0
        
        with st.spinner('連線政府 API 掃描中...'):
            for car in selected_targets:
                res, total = fetch_data(car, t_code)
                all_results.append(res)
                grand_total += total
        
        # 顯示儀表板
        c1, c2 = st.columns(2)
        c1.metric("監控數量", f"{len(selected_targets)} 台")
        c2.metric("待繳總金額", f"{grand_total} 元", delta=f"{grand_total}元" if grand_total > 0 else None, delta_color="inverse")
        
        # 顯示詳細表格
        st.subheader("📋 實時監控報表")
        df = pd.DataFrame(all_results).set_index("車號")
        st.table(df)
        
        if grand_total > 0:
            st.error("📢 偵測到未繳費項目，請點擊 [台北通](https://pay.taipei/) 繳費。")
        else:
            st.success("✅ 檢查完畢，目前所有車輛均無待繳費用。")
else:
    st.info("💡 操作指南：在左側輸入車號（多台請隔開），點擊『確認新增』後，再按『執行掃描』。")

st.divider()
st.caption("IT Note: 已優化批量處理邏輯，支援大量車號同時檢索。")

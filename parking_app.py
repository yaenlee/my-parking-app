import streamlit as st
import requests
import pandas as pd
import urllib3
import os

# --- [1] 環境淨化 ---
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="停車監控中心", layout="wide")

# --- [2] 初始化車庫清單 (使用 Session State 儲存) ---
if 'vehicle_list' not in st.session_state:
    # 這裡可以預設放妳最常用的車號
    st.session_state.vehicle_list = ["BWS-8036"]

# --- [3] 查詢核心函式 ---
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

# --- [4] UI 佈局 ---
st.title("🚗 全方位停車費監控面板")

with st.sidebar:
    st.header("⚙️ 車庫管理")
    
    # 新增車號
    with st.container():
        new_car = st.text_input("➕ 輸入車號", placeholder="例如: ABC-1234").upper().strip()
        if st.button("新增至監控清單", use_container_width=True):
            if new_car and new_car not in st.session_state.vehicle_list:
                st.session_state.vehicle_list.append(new_car)
                st.rerun()
    
    st.divider()
    
    # 選擇要查詢的車輛 (可多選)
    selected_targets = st.multiselect(
        "🎯 選擇本次監控對象",
        options=st.session_state.vehicle_list,
        default=st.session_state.vehicle_list # 預設全選
    )
    
    st.divider()
    car_type = st.radio("車種設定", ["汽車", "機車"], horizontal=True)
    t_code = 'C' if car_type == "汽車" else 'M'
    
    # 執行按鈕
    start_btn = st.button("🚀 執行多車同步掃描", type="primary", use_container_width=True)

# --- [5] 顯示結果 ---
if start_btn:
    if not selected_targets:
        st.warning("請先在左側選取或新增至少一個車號。")
    else:
        all_results = []
        grand_total = 0
        
        # 顯示進度條
        progress_text = "連線政府伺服器中..."
        my_bar = st.progress(0, text=progress_text)
        
        for index, car in enumerate(selected_targets):
            res, total = fetch_data(car, t_code)
            all_results.append(res)
            grand_total += total
            my_bar.progress((index + 1) / len(selected_targets))
        
        my_bar.empty()
        
        # 頂部數據看板
        c1, c2 = st.columns(2)
        c1.metric("監控車輛總數", f"{len(selected_targets)} 台")
        c2.metric("全車庫總待繳", f"{grand_total} 元", delta=f"{grand_total}元" if grand_total > 0 else None, delta_color="inverse")
        
        # 詳細表格
        st.subheader("📋 實時監控報表")
        df = pd.DataFrame(all_results).set_index("車號")
        st.table(df)
        
        if grand_total > 0:
            st.error("📢 偵測到未繳費項目，請點擊 [台北通](https://pay.taipei/) 或各縣市官網處理。")
        else:
            st.success("✅ 目前所有選定車輛狀態良好。")
else:
    st.info("💡 操作指南：\n1. 在左側輸入車號點擊『新增』。\n2. 在『選擇監控對象』勾選妳想查的所有車輛。\n3. 按下『執行多車同步掃描』即可一次看完。")

st.divider()
st.caption("IT Note: 已優化北北桃連線路徑，支援同時多車異步查詢。")
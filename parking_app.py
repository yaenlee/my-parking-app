import streamlit as st
import requests
import pandas as pd
import urllib3
import os

# --- [1] 環境與安全設定 ---
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定網頁標題與寬度佈局
st.set_page_config(page_title="停車監控中心", layout="wide", initial_sidebar_state="collapsed")

# --- [2] 初始化 Session State ---
if 'vehicle_list' not in st.session_state:
    st.session_state.vehicle_list = []

# --- [3] Callback 函式 (處理批量新增與清空) ---
def add_car_callback():
    raw_input = st.session_state.temp_input.upper().strip()
    if raw_input:
        # 支援空格、逗號、全形逗號、換行分隔
        new_cars = raw_input.replace(',', ' ').replace('，', ' ').replace('\n', ' ').split()
        for car in new_cars:
            car = car.strip()
            if car and car not in st.session_state.vehicle_list:
                st.session_state.vehicle_list.append(car)
        st.session_state.temp_input = "" # 清空輸入框

def clear_list_callback():
    st.session_state.vehicle_list = []

# --- [4] API 查詢邏輯 ---
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
                res[city] = f"🔴 {amt}元" if amt > 0 else "🟢 無"
                car_total += amt
            else: res[city] = "⚠️ 忙碌"
        except: res[city] = "❌ 異常"
    return res, car_total

# --- [5] UI 側邊欄 (手機版會縮成左上角箭頭) ---
with st.sidebar:
    st.header("⚙️ 監控清單管理")
    
    st.text_input(
        "➕ 新增車號 (可批量)", 
        key="temp_input", 
        placeholder="多台請用空格隔開",
        help="例如: ABC-1234 XYZ-5678"
    )
    
    c1, c2 = st.columns(2)
    with c1:
        st.button("確認新增", on_click=add_car_callback, use_container_width=True, type="primary")
    with c2:
        st.button("清空清單", on_click=clear_list_callback, use_container_width=True)
    
    st.divider()
    
    selected_targets = st.multiselect(
        "🎯 選擇查詢對象",
        options=st.session_state.vehicle_list,
        default=st.session_state.vehicle_list
    )
    
    car_type = st.radio("車種", ["汽車", "機車"], horizontal=True)
    t_code = 'C' if car_type == "汽車" else 'M'
    
    # 查詢按鈕
    start_btn = st.button("🚀 執行同步掃描", use_container_width=True)

# --- [6] 主畫面顯示 ---
st.title("🚗 北北桃停車監控中心")

if start_btn:
    if not selected_targets:
        st.warning("請展開左側選單並新增車號。")
    else:
        all_results = []
        grand_total = 0
        
        with st.spinner('掃描中...'):
            for car in selected_targets:
                res, total = fetch_data(car, t_code)
                all_results.append(res)
                grand_total += total
        
        # 指標看板 (手機會自動垂直堆疊)
        m1, m2 = st.columns(2)
        m1.metric("監控數量", f"{len(selected_targets)} 台")
        m2.metric("待繳總額", f"{grand_total} 元", delta=f"{grand_total}元" if grand_total > 0 else None, delta_color="inverse")
        
        # 詳細表格 (支援手機橫向滑動)
        st.subheader("📋 查詢詳情")
        df = pd.DataFrame(all_results).set_index("車號")
        st.dataframe(df, use_container_width=True) 
        
        if grand_total > 0:
            st.error("📢 偵測到未繳費項目！")
        else:
            st.success("✅ 狀態正常，無待繳費用。")
else:
    # 專為手機用戶設計的說明
    st.info("""
    ### 📱 快速操作指南
    1. **手機用戶**：請點擊左上角箭頭 **『 > 』** 展開設定選單。
    2. **電腦用戶**：直接在左側側邊欄操作。
    3. **功能**：支援同時輸入多個車號（用空格隔開），一鍵查詢北北桃。
    """)

st.divider()
st.caption("IT Note: 介面已優化 RWD 響應式佈局，支援 iOS/Android 瀏覽器。")

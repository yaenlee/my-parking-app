import streamlit as st
import requests
import pandas as pd
import urllib3
import os

# --- [1] 環境與安全設定 ---
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="停車監控中心", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- [2] 初始化 Session State ---
if 'vehicle_list' not in st.session_state:
    st.session_state.vehicle_list = []

# --- [3] Callback 函式 ---
def add_car_callback():
    raw_input = st.session_state.temp_input.upper().strip()
    if raw_input:
        # 支援多種分隔符號批量新增
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

# --- [5] UI 側邊欄 ---
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
    
    start_btn = st.button("🚀 執行同步掃描", use_container_width=True)

    st.divider()
    # --- 法律免責聲明區塊 ---
    with st.expander("⚖️ 法律免責聲明"):
        st.caption("""
        1. 本工具僅供學術研究與個人便利使用，非政府官方程式。
        2. 使用者輸入車號即表示已獲得車主授權查詢。
        3. 本程式不蒐集、不儲存任何車牌個資，關閉視窗即清除記錄。
        4. 資料來源為各縣市政府公開 API，正確資訊請以官網為準。
        """)

# --- [6] 主畫面顯示 ---
st.title("🚗 北北桃停車監控中心")

if start_btn:
    if not selected_targets:
        st.warning("請點擊左上角箭頭 『 > 』 展開選單並新增車號。")
    else:
        all_results = []
        grand_total = 0
        
        with st.spinner('同步連線政府 API 中...'):
            for car in selected_targets:
                res, total = fetch_data(car, t_code)
                all_results.append(res)
                grand_total += total
        
        m1, m2 = st.columns(2)
        m1.metric("監控數量", f"{len(selected_targets)} 台")
        m2.metric("待繳總額", f"{grand_total} 元", delta=f"{grand_total}元" if grand_total > 0 else None, delta_color="inverse")
        
        st.subheader("📋 查詢詳情")
        df = pd.DataFrame(all_results).set_index("車號")
        st.dataframe(df, use_container_width=True) 
        
        if grand_total > 0:
            st.error("📢 偵測到未繳費項目，請點擊 [台北通](https://pay.taipei/) 繳費。")
        else:
            st.success("✅ 檢查完畢，目前所有車輛均無待繳費用。")
else:
    st.info("""
    ### 📱 快速操作指南
    1. **手機用戶**：點擊左上角 **『 > 』** 展開設定選單。
    2. **功能**：支援同時輸入多個車號（用空格隔開），一鍵查詢北北桃。
    3. **安全**：本工具不儲存任何個資，請放心使用。
    """)

st.divider()
st.caption(f"IT Note: 系統運行中 | 當前時間: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")

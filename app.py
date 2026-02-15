import streamlit as st

# Set page config for mobile-friendly view
st.set_page_config(
    page_title="ICU Pharmacist Helper",
    page_icon="💊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for "iPhone-like" feel
st.markdown("""
    <style>
    .stApp {
        background-color: #f2f2f7; /* iOS system gray 6 */
    }
    .main > div {
        padding-top: 1rem;
        padding-bottom: 3rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3rem;
        background-color: #007aff; /* iOS Blue */
        color: white;
        border: none;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #0063cf;
    }
    .css-1d391kg {
        padding-top: 1rem;
    }
    /* Card-like containers */
    .css-1r6slb0 {
        background: white;
        padding: 1.5rem;
        border-radius: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    h1, h2, h3 {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    </style>
""", unsafe_allow_html=True)

# Application Header
st.title("ICU 薬剤師ツール 💊")
st.caption("※本ツールは判断補助用です。最終判断は臨床で行ってください。")

# Tabs for navigation
tab1, tab2 = st.tabs(["🧪 腎機能 (Ccr)", "💉 γ計算"])

# --- TAB 1: Cockcroft-Gault Calculation ---
with tab1:
    st.header("Ccr (Cockcroft-Gault)")
    
    with st.container():
        st.markdown("### 📝 患者情報")
        col1, col2 = st.columns(2)
        
        with col1:
            age = st.number_input("年齢 (歳)", min_value=18, max_value=120, value=60, step=1)
            weight = st.number_input("体重 (kg)", min_value=20.0, max_value=200.0, value=60.0, step=0.1)
        
        with col2:
            sex = st.radio("性別", ["男性", "女性"], horizontal=True)
            scr = st.number_input("Scr (mg/dL)", min_value=0.1, max_value=20.0, value=1.0, step=0.01)

        # Calculation Logic
        if scr > 0:
            # Standard Cockcroft-Gault Formula
            ccr_val = ((140 - age) * weight) / (72 * scr)
            if sex == "女性":
                ccr_val *= 0.85
            
            # Display Result
            st.divider()
            st.markdown("### 📊 計算結果")
            st.metric(label="Creatinine Clearance (Ccr)", value=f"{ccr_val:.1f} mL/min")
            
            # Clinical Context (Reference)
            st.info(
                f"**計算式**: {'(140-Age)×Wt / (72×Scr)'} {'× 0.85 (女性)' if sex == '女性' else ''}"
            )
            
            if ccr_val < 30:
                st.error("⚠️ 高度腎機能低下の可能性があります。投与量を確認してください。")
            elif ccr_val < 60:
                st.warning("⚠️ 中等度腎機能低下の可能性があります。")
            else:
                st.success("✅ 腎機能は保たれている可能性があります。")
        else:
            st.warning("Scrを入力してください")

# --- TAB 2: Gamma Calculation ---
with tab2:
    st.header("γ計算 (Gamma Calculator)")
    
    st.markdown("### 💊 薬剤組成")
    col1, col2 = st.columns(2)
    with col1:
        drug_mg = st.number_input("薬剤量 (mg)", min_value=0.0, value=100.0, step=10.0)
    with col2:
        sol_ml = st.number_input("溶解液量 (mL)", min_value=1.0, value=100.0, step=10.0)
    
    patient_wt = st.number_input("患者体重 (kg)", min_value=1.0, value=50.0, step=0.1, key="gamma_wt")

    if sol_ml > 0 and patient_wt > 0:
        # Concentration
        conc = drug_mg / sol_ml  # mg/mL
        st.caption(f"薬剤濃度: {conc:.2f} mg/mL")
        
        st.divider()
        mode = st.radio("計算モード", ["流量(mL/h) から γを計算", "γ(μg/kg/min) から 流量を計算"], index=0)
        
        if mode == "流量(mL/h) から γを計算":
            flow_rate = st.number_input("流量 (mL/h)", min_value=0.0, value=5.0, step=0.1)
            
            # Calculation: (mL/h * mg/mL * 1000) / (60 * kg) = μg/kg/min
            gamma = (flow_rate * conc * 1000) / (60 * patient_wt)
            
            st.markdown("### 🎯 結果")
            st.metric(label="投与量 (γ)", value=f"{gamma:.2f} μg/kg/min")
            
            st.markdown("#### 計算式")
            st.code(f"({flow_rate} mL/h × {conc:.2f} mg/mL × 1000) ÷ (60 min × {patient_wt} kg)", language="text")
            
        else:
            target_gamma = st.number_input("目標投与量 (γ)", min_value=0.0, value=0.05, step=0.01)
            
            # Calculation: (μg/kg/min * 60 * kg) / 1000 / (mg/mL) = mL/h
            needed_flow = (target_gamma * 60 * patient_wt) / (1000 * conc) if conc > 0 else 0
            
            st.markdown("### 🎯 結果")
            st.metric(label="必要流量", value=f"{needed_flow:.1f} mL/h")
            
            st.markdown("#### 計算式")
            st.code(f"({target_gamma} γ × 60 min × {patient_wt} kg) ÷ 1000 ÷ {conc:.2f} mg/mL", language="text")
    else:
        st.error("溶解液量と体重は0より大きい値を入力してください")

# Footer
st.markdown("---")
st.markdown("Build with ❤️ for Pharmacists")

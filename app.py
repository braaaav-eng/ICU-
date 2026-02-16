import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# ⚙️ Configuration & Constants
# ==========================================
st.set_page_config(
    page_title="ICU Tool",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------
# 📊 Clinical Thresholds (Editable)
# ------------------------------------------

# Gamma Module Thresholds (Upper limit warning)
GAMMA_THRESHOLDS = {
    "Norepinephrine (NAD)": 0.3, # J-SSCG2020: 0.05-0.3
    "Dobutamine (DOB)": 10.0,
    "Dopamine (DOA)": 10.0,
    "Nicardipine": 6.0, 
    "Midazolam": 0.2, # mg/kg/h
    "Propofol": 3.0,  # mg/kg/h
    "Dexmedetomidine": 0.7, # ug/kg/h
    "Nitroglycerin": 5.0, # usually start 0.1-0.5
    "Carperitide": 0.1
}

# Forrester Classification Thresholds
FORRESTER_CI_THRESH = 2.2 # L/min/m2
FORRESTER_PCWP_THRESH = 18.0 # mmHg

# ------------------------------------------
# 🩹 Session Initialization (Robust)
# ------------------------------------------
INITIAL_KEYS = [
    "gamma_mg", "gamma_ml", "gamma_flow", "gamma_weight",
    "ccr_age", "ccr_weight", "ccr_scr",
    "ab_ph", "ab_pco2", "ab_hco3", "ab_na", "ab_cl", "ab_alb",
    "hf_pcwp", "hf_ci", "hf_sbp"
]

for key in INITIAL_KEYS:
    if key not in st.session_state:
        st.session_state[key] = ""

# ==========================================
# 🎨 UI/UX & Scripts
# ==========================================

# Custom CSS
st.markdown("""
<style>
    /* 1. Fix Safari Top Spacing */
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 5rem !important;
    }
    
    /* Mobile Input Sizing */
    .stTextInput input, .stNumberInput input {
        font-size: 16px !important; /* iOS Zoom prevention */
        padding: 0.8rem;
    }
    
    /* Result Cards */
    .result-card-green {
        background-color: #d1fae5; padding: 1rem; border-radius: 8px; border-left: 6px solid #10b981; margin: 1rem 0;
    }
    .result-card-yellow {
        background-color: #fef3c7; padding: 1rem; border-radius: 8px; border-left: 6px solid #f59e0b; margin: 1rem 0;
    }
    .result-card-red {
        background-color: #fee2e2; padding: 1rem; border-radius: 8px; border-left: 6px solid #ef4444; margin: 1rem 0;
    }
    
    .result-main { font-size: 1.5rem; font-weight: 800; color: #1f2937; line-height: 1.2; }
    .result-sub { font-size: 1.1rem; font-weight: 700; color: #374151; margin-top: 0.3rem; }
    .result-ref { font-size: 0.85rem; color: #6b7280; font-style: italic; margin-top: 5px; }

    /* Hide Footer */
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Navigation Tabs as Buttons (Radio) */
    .stRadio div[role="radiogroup"] { flex-direction: column; }
    .stRadio div[role="radiogroup"] > label {
        padding: 12px; margin-bottom: 8px; border-radius: 8px;
        background: #f3f4f6; border: 1px solid #e5e7eb;
    }
    .stRadio div[role="radiogroup"] > label[data-checked="true"] {
        background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# JS Injection for UX (Inputmode & Enter key nav)
jquery_script = """
<script>
    document.addEventListener("DOMContentLoaded", function() {
        // 1. Set inputmode='decimal' for numeric text inputs
        const inputs = document.querySelectorAll('input[type="text"]');
        inputs.forEach((input, index) => {
            if (input.placeholder && input.placeholder.includes('例:')) {
                input.setAttribute('inputmode', 'decimal');
                input.setAttribute('tabindex', index + 1); // Set proper tab index
            }
        });

        // 2. Add Enter key navigation
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                const activeElement = document.activeElement;
                if (activeElement.tagName === 'INPUT' && activeElement.type === 'text') {
                    const currentTabIndex = parseInt(activeElement.getAttribute('tabindex'));
                    if (!isNaN(currentTabIndex)) {
                        const nextElement = document.querySelector(`input[tabindex="${currentTabIndex + 1}"]`);
                        if (nextElement) {
                            nextElement.focus();
                            event.preventDefault(); // Prevent accidental submission
                        }
                    }
                }
            }
        });
    });
    
    // Fallback for simple re-runs
    setTimeout(function(){
        const inputs = document.querySelectorAll('input[type="text"]');
        inputs.forEach((input, index) => {
            if (input.placeholder && input.placeholder.includes('例:')) {
                input.setAttribute('inputmode', 'decimal');
                input.setAttribute('tabindex', index + 1);
            }
        });
    }, 800);
</script>
"""
components.html(jquery_script, height=0, width=0)


# ==========================================
# 🛠 Helpers
# ==========================================
def safe_float(val):
    if not val or val.strip() == "": return None
    try:
        return float(val)
    except:
        return None

# ==========================================
# 💉 Module 1: Gamma
# ==========================================
DRUG_PRESETS = {
    "カスタム": {"mg": None, "ml": None, "ref": None, "source": None},
    "Norepinephrine (NAD)": {
        "mg": 5.0, "ml": 50.0, 
        "ref": "0.05 - 0.3 μg/kg/min", "source": "日本版敗血症診療GL2020"
    },
    "Dobutamine (DOB)": {
        "mg": 150.0, "ml": 50.0, "ref": "1 - 10 μg/kg/min", "source": "添付文書"
    },
    "Dopamine (DOA)": {
        "mg": 150.0, "ml": 50.0, "ref": "3 - 10 μg/kg/min", "source": "添付文書"
    },
    "Nicardipine": {
        "mg": 50.0, "ml": 50.0, "ref": "0.5 - 6 μg/kg/min", "source": "高血圧治療GL"
    },
    "Midazolam": {
        "mg": 50.0, "ml": 50.0, "ref": "0.03 - 0.2 mg/kg/h", "source": "PADISガイドライン"
    },
    "Propofol": {
        "mg": 1000.0, "ml": 100.0, "ref": "0.3 - 3.0 mg/kg/h", "source": "添付文書"
    },
    "Dexmedetomidine": {
        "mg": 0.2, "ml": 50.0, "ref": "0.2 - 0.7 μg/kg/h", "source": "添付文書"
    },
    "Nitroglycerin": {
        "mg": 50.0, "ml": 100.0, "ref": "0.5 - 20 μg/kg/min", "source": "添付文書"
    },
    "Carperitide": {
        "mg": 3.0, "ml": 50.0, "ref": "0.05 - 0.1 μg/kg/min", "source": "心不全診療GL"
    }
}

def on_gamma_preset():
    sel = st.session_state.gamma_preset
    if sel in DRUG_PRESETS and DRUG_PRESETS[sel]["mg"] is not None:
        st.session_state.gamma_mg = str(DRUG_PRESETS[sel]["mg"])
        st.session_state.gamma_ml = str(DRUG_PRESETS[sel]["ml"])

def render_gamma():
    st.markdown("## 💉 γ計算")
    
    st.selectbox("薬剤選択", list(DRUG_PRESETS.keys()), key="gamma_preset", on_change=on_gamma_preset)
    
    # Inputs
    c1, c2 = st.columns(2)
    c1.text_input("薬剤量 (mg)", key="gamma_mg", placeholder="例: 5")
    c2.text_input("溶解量 (mL)", key="gamma_ml", placeholder="例: 50")
    st.text_input("投与速度 (mL/h)", key="gamma_flow", placeholder="例: 3.0")
    
    use_weight = st.checkbox("体重換算 (kg)", value=False)
    if use_weight:
        st.text_input("体重 (kg)", key="gamma_weight", placeholder="例: 50")

    if st.button("計算", type="primary", use_container_width=True):
        mg = safe_float(st.session_state.gamma_mg)
        ml = safe_float(st.session_state.gamma_ml)
        flow = safe_float(st.session_state.gamma_flow)
        wt = safe_float(st.session_state.gamma_weight) if use_weight else None
        
        # Validation
        if None in [mg, ml, flow]:
            st.error("数値を入力してください")
            return
        if mg <= 0 or ml <= 0 or flow <= 0:
            st.error("0以下の値は無効です")
            return
            
        # Calculation
        dose_mg_h = flow * (mg / ml)
        
        # Output Generation
        preset_name = st.session_state.gamma_preset
        preset_data = DRUG_PRESETS[preset_name]
        is_dex = "Dexmedetomidine" in preset_name
        is_prop = "Propofol" in preset_name
        is_mid = "Midazolam" in preset_name
        
        main_text = f"{dose_mg_h:.2f} mg/h"
        sub_text = ""
        warnings = []
        card_class = "result-card-green"
        
        if wt and wt > 0:
            gamma = (dose_mg_h * 1000) / (wt * 60)
            
            # Unit logic
            if is_dex:
                mcg_kg_h = (dose_mg_h * 1000) / wt
                sub_text = f"{mcg_kg_h:.2f} μg/kg/h <br><span style='font-size:0.9rem; color:#666'>({gamma:.3f} γ)</span>"
                # Check threshold (ug/kg/h)
                if GAMMA_THRESHOLDS["Dexmedetomidine"] and mcg_kg_h > GAMMA_THRESHOLDS["Dexmedetomidine"]:
                    warnings.append(f"高用量注意 (> {GAMMA_THRESHOLDS['Dexmedetomidine']} μg/kg/h)")
            elif is_prop or is_mid:
                mg_kg_h = dose_mg_h / wt
                sub_text = f"{mg_kg_h:.2f} mg/kg/h"
                key = "Propofol" if is_prop else "Midazolam"
                if GAMMA_THRESHOLDS[key] and mg_kg_h > GAMMA_THRESHOLDS[key]:
                    warnings.append(f"高用量注意 (> {GAMMA_THRESHOLDS[key]} mg/kg/h)")
            else:
                sub_text = f"{gamma:.2f} μg/kg/min"
                if preset_name in GAMMA_THRESHOLDS and GAMMA_THRESHOLDS[preset_name]:
                    if gamma > GAMMA_THRESHOLDS[preset_name]:
                        warnings.append(f"高用量注意 (> {GAMMA_THRESHOLDS[preset_name]} γ)")
                        
        elif is_dex or is_prop or is_mid or "Norepinephrine" in preset_name:
            # Need weight for these strictly usually, but show mg/h if no weight
            pass
            
        if warnings:
            card_class = "result-card-yellow"
            
        # Reference
        ref_text = ""
        if preset_data["ref"]:
            ref_text = f"推奨: {preset_data['ref']} (出典: {preset_data['source']})"
            
        # Display
        st.markdown(f"""
        <div class="{card_class}">
            <div class="result-main">{main_text}</div>
            <div class="result-sub">{sub_text}</div>
            <div class="result-ref">{ref_text}</div>
        </div>
        """, unsafe_allow_html=True)
        
        for w in warnings: st.warning(w)

        with st.expander("計算詳細"):
            st.write(f"濃度: {mg/ml:.3f} mg/mL")
            st.write(f"式: {flow} mL/h × {mg/ml:.3f} mg/mL = {dose_mg_h:.2f} mg/h")

# ==========================================
# 🧪 Module 2: CCr
# ==========================================
def render_ccr():
    st.markdown("## 🧪 CCr (腎機能)")
    
    c1, c2 = st.columns(2)
    c1.text_input("年齢 (歳)", key="ccr_age", placeholder="例: 65")
    c2.text_input("体重 (kg)", key="ccr_weight", placeholder="例: 50")
    st.text_input("Scr (mg/dL)", key="ccr_scr", placeholder="例: 1.0")
    sex = st.radio("性別", ["男性", "女性"], horizontal=True)
    
    if st.button("計算", type="primary", use_container_width=True):
        age = safe_float(st.session_state.ccr_age)
        wt = safe_float(st.session_state.ccr_weight)
        scr = safe_float(st.session_state.ccr_scr)
        
        if None in [age, wt, scr] or scr <= 0:
            st.error("正しい数値を入力してください")
            return
            
        ccr = ((140 - age) * wt) / (72 * scr)
        if sex == "女性": ccr *= 0.85
        
        cat = "正常 (>60)"
        color = "result-card-green"
        if ccr < 30: 
            cat = "高度低下 (<30)"
            color = "result-card-red"
        elif ccr < 60:
            cat = "中等度低下 (30-60)"
            color = "result-card-yellow"
            
        st.markdown(f"""
        <div class="{color}">
            <div class="result-main">{ccr:.1f} mL/min</div>
            <div class="result-sub">{cat}</div>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# ⚖️ Module 3: Acid-Base
# ==========================================
def render_ab():
    st.markdown("## ⚖️ 酸塩基平衡")
    
    st.text_input("pH", key="ab_ph", placeholder="例: 7.32")
    c1, c2 = st.columns(2)
    c1.text_input("PaCO2", key="ab_pco2", placeholder="mmHg")
    c2.text_input("HCO3", key="ab_hco3", placeholder="mEq/L")
    c3, c4 = st.columns(2)
    c3.text_input("Na", key="ab_na", placeholder="mEq/L")
    c4.text_input("Cl", key="ab_cl", placeholder="mEq/L")
    st.text_input("Alb (任意)", key="ab_alb", placeholder="g/dL")
    
    if st.button("判定", type="primary", use_container_width=True):
        ph = safe_float(st.session_state.ab_ph)
        na = safe_float(st.session_state.ab_na)
        cl = safe_float(st.session_state.ab_cl)
        hco3 = safe_float(st.session_state.ab_hco3)
        alb = safe_float(st.session_state.ab_alb)
        
        if None in [ph, na, cl, hco3]:
            st.error("Alb以外の必須値を入力してください")
            return
            
        # Analysis
        main_state = "正常範囲"
        if ph < 7.35: main_state = "アシデミア"
        elif ph > 7.45: main_state = "アルカレミア"
        
        ag = na - (cl + hco3)
        ag_show = ag
        ag_txt = f"AG: {ag:.1f}"
        
        if alb:
            ag_corr = ag + 2.5*(4.0 - alb)
            ag_show = ag_corr
            ag_txt += f" (補正 {ag_corr:.1f})"
            
        sub_msgs = []
        is_high_ag = False
        if ag_show > 12:
            is_high_ag = True
            sub_msgs.append("AG開大性 代謝性アシドーシス")
            
            # Delta Ratio
            d_ag = ag_show - 12
            d_hco3 = 24 - hco3
            if d_hco3 != 0:
                ratio = d_ag / d_hco3
                if ratio < 0.4: sub_msgs.append("併存: 高Cl性アシドーシス")
                elif ratio > 2.0: sub_msgs.append("併存: 代謝性アルカローシス")
        
        color = "result-card-yellow" if ph < 7.35 or is_high_ag else "result-card-green"
        
        st.markdown(f"""
        <div class="{color}">
            <div class="result-main">{main_state}</div>
            <div class="result-sub">{ag_txt} {'[開大]' if is_high_ag else ''}</div>
        </div>
        """, unsafe_allow_html=True)
        
        for m in sub_msgs: st.info(m)

# ==========================================
# 🚨 Module 4: Shock (New)
# ==========================================
def render_shock():
    st.markdown("## 🚨 ショック分類")
    
    sbp = st.selectbox("収縮期血圧 (SBP)", ["< 90 mmHg (ショック)", "> 90 mmHg (維持)"])
    skin = st.radio("皮膚所見 (灌流)", ["Warm (温/Dry)", "Cold (冷/湿)"])
    lung = st.radio("肺うっ血 (聴診)", ["なし (Dry)", "あり (Wet)"])
    urine = st.selectbox("尿量", ["維持 (>0.5 mL/kg/h)", "低下/無尿"])
    lactate = st.selectbox("乳酸値", ["正常 (<2 mmol/L)", "上昇 (>2 mmol/L)"])
    
    if st.button("評価", type="primary", use_container_width=True):
        if "維持" in sbp:
            st.success("現在はショック血圧ではありません。バイタル変動に注意してください。")
            return
            
        # Logic Rule Base
        shock_type = "分類不能"
        action = "原因検索・ABC安定化"
        prob = "中"
        
        if skin.startswith("Warm"):
            shock_type = "血液分布異常性ショック (敗血症等)"
            action = "ノルアドレナリン + 輸液 + 抗生剤"
            prob = "高"
        else: # Cold
            if lung.startswith("あり"):
                shock_type = "心原性ショック"
                action = "強心薬・昇圧薬 (Do Not Fluid)"
                prob = "高"
            else: # Dry
                shock_type = "循環血液量減少性ショック"
                action = "急速輸液負荷"
                prob = "高"
                
        st.markdown(f"""
        <div class="result-card-red">
            <div class="result-main">{shock_type}</div>
            <div class="result-sub">推奨: {action}</div>
            <div class="result-ref">乳酸値: {lactate} / 尿量: {urine}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("参照ガイドライン"):
            st.write("出典: [日本版敗血症診療ガイドライン2020](https://www.jsicm.org/news/upload/j-sscg2020_plus.pdf)")
            st.write("Warm Shock → Distributive (Septic)")
            st.write("Cold & Wet → Cardiogenic")
            st.write("Cold & Dry → Hypovolemic / Obstructive")

# ==========================================
# 🫀 Module 5: Heart Failure (Forrester)
# ==========================================
def render_hf():
    st.markdown("## 🫀 心不全 (Forrester)")
    
    st.markdown("#### ヘモダイナミクス入力")
    c1, c2 = st.columns(2)
    c1.text_input("CI (L/min/m2)", key="hf_ci", placeholder="例: 2.0")
    c2.text_input("PCWP (mmHg)", key="hf_pcwp", placeholder="例: 20")
    st.text_input("収縮期血圧 (opt)", key="hf_sbp", placeholder="例: 100")
    
    status = st.radio("クリニカルシナリオ (CS)", ["CS1 (血圧高値)", "CS2 (全身浮腫)", "CS3 (低灌流)", "CS4 (ACS)", "CS5 (右心不全)"])
    
    if st.button("分類実行", type="primary", use_container_width=True):
        ci = safe_float(st.session_state.hf_ci)
        pcwp = safe_float(st.session_state.hf_pcwp)
        
        if None in [ci, pcwp]:
            st.error("CIとPCWPを入力してください (推定値可)")
            return
            
        # Logic
        # Forrester Thresholds: CI=2.2, PCWP=18
        is_wet = pcwp >= FORRESTER_PCWP_THRESH
        is_cold = ci < FORRESTER_CI_THRESH
        
        subset = "I"
        desc = "正常 (Warm & Dry)"
        rx = "経過観察 / 基礎疾患治療"
        color = "result-card-green"
        
        if not is_cold and is_wet:
            subset = "II"
            desc = "肺うっ血 (Warm & Wet)"
            rx = "利尿薬 (Furosemide) + 血管拡張 (Nitrates)"
            color = "result-card-yellow"
        elif is_cold and not is_wet:
            subset = "III"
            desc = "低灌流 (Cold & Dry)"
            rx = "輸液負荷 (Check Volume) + 強心薬"
            color = "result-card-yellow"
        elif is_cold and is_wet:
            subset = "IV"
            desc = "うっ血 + 低灌流 (Cold & Wet)"
            rx = "強心薬 + 昇圧薬 + 補助循環検討"
            color = "result-card-red"
            
        st.markdown(f"""
        <div class="{color}">
            <div class="result-main">Subset {subset}</div>
            <div class="result-sub">{desc}</div>
            <div class="result-sub" style="font-size:1rem">推奨: {rx}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("詳細閾値・根拠"):
            st.write(f"**PCWP**: {pcwp} (閾値 {FORRESTER_PCWP_THRESH}) -> {'Wet' if is_wet else 'Dry'}")
            st.write(f"**CI**: {ci} (閾値 {FORRESTER_CI_THRESH}) -> {'Cold' if is_cold else 'Warm'}")
            st.caption("出典: 日本循環器学会 心不全診療ガイドライン")

# ==========================================
# 🚀 Main Router
# ==========================================
def main():
    menu = ["γ計算", "CCr (腎機能)", "酸塩基平衡", "ショック分類", "心不全 (Forrester)"]
    choice = st.radio("機能選択", menu, label_visibility="collapsed")
    
    st.markdown("---")
    
    if choice == "γ計算": render_gamma()
    elif choice == "CCr (腎機能)": render_ccr()
    elif choice == "酸塩基平衡": render_ab()
    elif choice == "ショック分類": render_shock()
    elif choice == "心不全 (Forrester)": render_hf()

if __name__ == "__main__":
    main()

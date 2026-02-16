import streamlit as st
import math

# ==========================================
# ⚙️ Configuration & Styles
# ==========================================
st.set_page_config(
    page_title="ICU Tool",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Initialize Session State
if "init_done" not in st.session_state:
    st.session_state["gamma_mg_input"] = ""
    st.session_state["gamma_ml_input"] = ""
    st.session_state["gamma_flow_input"] = ""
    st.session_state["gamma_weight_input"] = ""
    st.session_state["init_done"] = True

# Custom CSS & JS for Mobile Optimization
st.markdown("""
<style>
    /* Global Mobile Tweaks */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }
    
    /* Input Styling for touch targets */
    .stTextInput input {
        font-size: 16px; /* Prevent zoom on iOS */
        padding: 0.8rem;
    }
    
    /* Result Card Styling */
    .result-card-green {
        background-color: #d1fae5;
        padding: 1rem;
        border-radius: 8px;
        border-left: 6px solid #10b981;
        margin-bottom: 1rem;
    }
    .result-card-yellow {
        background-color: #fef3c7;
        padding: 1rem;
        border-radius: 8px;
        border-left: 6px solid #f59e0b;
        margin-bottom: 1rem;
    }
    .result-card-red {
        background-color: #fee2e2;
        padding: 1rem;
        border-radius: 8px;
        border-left: 6px solid #ef4444;
        margin-bottom: 1rem;
    }
    
    /* Typography */
    .result-main {
        font-size: 1.6rem;
        font-weight: 800;
        color: #1f2937;
        line-height: 1.3;
    }
    .result-sub {
        font-size: 1.1rem;
        font-weight: 700;
        color: #374151;
        margin-top: 0.3rem;
    }
    .result-ref {
        font-size: 0.85rem;
        color: #6b7280;
        margin-top: 0.5rem;
        font-style: italic;
    }
    
    /* Vertical Radio Buttons (Mobile Friendly) */
    .stRadio div[role="radiogroup"] {
        flex-direction: column;
    }
    .stRadio div[role="radiogroup"] > label {
        background-color: #f3f4f6;
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 8px;
        border: 1px solid #e5e7eb;
        width: 100%;
    }
    .stRadio div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #eff6ff;
        border-color: #3b82f6;
        color: #3b82f6;
        font-weight: bold;
    }
    
    /* Hide footer */
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
</style>

<!-- JS: iOS Numeric Keyboard Trigger -->
<script>
    setTimeout(function(){
        const inputs = document.querySelectorAll('input[type="text"]');
        inputs.forEach(i => {
            if(i.placeholder && i.placeholder.includes('例:')) {
                i.setAttribute('inputmode', 'decimal');
            }
        });
    }, 500);
</script>
""", unsafe_allow_html=True)

# ==========================================
# 📚 Data & Constants
# ==========================================

# 閾値定義 (γ = μg/kg/min)
# Dexmedetomidine は例外的に μg/kg/h で判定したいが、統一ロジックのため変換して扱うか個別対応
GAMMA_THRESHOLDS = {
    "Norepinephrine (NAD)": 0.5, # >0.5γで注意
    "Dobutamine (DOB)": 10.0,
    "Dopamine (DOA)": 10.0,
    "Nicardipine": 10.0, 
    "Midazolam": None,  # mg/kg/h
    "Propofol": None,   # mg/kg/h
    "Dexmedetomidine": None, # ug/kg/h
    "Nitroglycerin": 5.0,
    "Carperitide": 0.2
}

# 薬剤プリセット定義 (数値型)
# value: {mg, ml, ref_range_txt, source}
DRUG_PRESETS = {
    "カスタム": {
        "mg": None, "ml": None, 
        "ref": None, "source": None
    },
    "Norepinephrine (NAD)": {
        "mg": 5.0, "ml": 50.0, 
        "ref": "0.05 - 0.3 μg/kg/min", 
        "source": "日本版敗血症診療GL2020"
    },
    "Dobutamine (DOB)": {
        "mg": 150.0, "ml": 50.0, 
        "ref": "1 - 10 μg/kg/min", 
        "source": "添付文書"
    },
    "Dopamine (DOA)": {
        "mg": 150.0, "ml": 50.0, 
        "ref": "3 - 10 μg/kg/min", 
        "source": "添付文書"
    },
    "Nicardipine": {
        "mg": 50.0, "ml": 50.0, 
        "ref": "0.5 - 6 μg/kg/min (2-10 mg/h)", 
        "source": "高血圧治療GL"
    },
    "Midazolam": {
        "mg": 50.0, "ml": 50.0, 
        "ref": "0.03 - 0.2 mg/kg/h", 
        "source": "PADISガイドライン"
    },
    "Propofol": {
        "mg": 1000.0, "ml": 100.0, 
        "ref": "0.3 - 3.0 mg/kg/h", 
        "source": "添付文書"
    },
    "Dexmedetomidine": {
        "mg": 0.2, "ml": 50.0, # 200mcg = 0.2mg
        "ref": "0.2 - 0.7 μg/kg/h", 
        "source": "添付文書"
    },
    "Nitroglycerin": {
        "mg": 50.0, "ml": 100.0, 
        "ref": "0.5 - 20 μg/kg/min", 
        "source": "添付文書"
    },
    "Carperitide": {
        "mg": 3.0, "ml": 50.0, # 3000mcg
        "ref": "0.05 - 0.1 μg/kg/min", 
        "source": "心不全診療GL"
    }
}

# ==========================================
# 🛠 Helper Functions
# ==========================================
def safe_float(value_str):
    """Convert string to float. Returns None if empty/invalid/zero."""
    if not value_str or not isinstance(value_str, str) or value_str.strip() == "":
        return None
    try:
        val = float(value_str)
        return val # Allow 0 return, handle logic outside
    except ValueError:
        return None

def on_preset_change():
    """Callback to update session state when preset changes."""
    selected = st.session_state.get("gamma_preset_selector", "カスタム")
    
    if selected in DRUG_PRESETS:
        data = DRUG_PRESETS[selected]
        # 数値を文字列に変換してInputにセット
        if data["mg"] is not None:
            st.session_state["gamma_mg_input"] = str(data["mg"])
        if data["ml"] is not None:
            st.session_state["gamma_ml_input"] = str(data["ml"])
    
    # Force rerun (sometimes needed in older streamlit, but safe to ignore if state works)

# ==========================================
# 📱 1. Gamma Module
# ==========================================
def render_gamma():
    st.markdown("### 💉 γ計算 (持続投与)")
    
    # 1. Preset Selector
    st.selectbox(
        "薬剤プリセット", 
        options=list(DRUG_PRESETS.keys()),
        index=0,
        key="gamma_preset_selector",
        on_change=on_preset_change
    )
    
    # 2. Inputs
    # drug_mg
    st.text_input("薬剤総量 (mg)", key="gamma_mg_input", placeholder="例: 5")
    drug_mg = safe_float(st.session_state.gamma_mg_input)
    
    # sol_ml
    st.text_input("溶解総量 (mL)", key="gamma_ml_input", placeholder="例: 50")
    sol_ml = safe_float(st.session_state.gamma_ml_input)
    
    # flow rate
    st.text_input("投与速度 (mL/h)", key="gamma_flow_input", placeholder="例: 3.0")
    flow_mlh = safe_float(st.session_state.gamma_flow_input)
    
    # weight toggle
    use_weight = st.checkbox("体重で換算する", value=False)
    weight_kg = None
    if use_weight:
        st.text_input("体重 (kg)", key="gamma_weight_input", placeholder="例: 50")
        weight_kg = safe_float(st.session_state.gamma_weight_input)

    # 3. Calculation Logic
    if st.button("計算実行", type="primary", use_container_width=True):
        
        # Validation
        errors = []
        if drug_mg is None: errors.append("薬剤総量(mg)を入力してください")
        elif drug_mg <= 0: errors.append("薬剤総量は0より大きい値を入力してください")
        
        if sol_ml is None: errors.append("溶解総量(mL)を入力してください")
        elif sol_ml <= 0: errors.append("溶解総量は0より大きい値を入力してください")
        
        if flow_mlh is None: errors.append("投与速度(mL/h)を入力してください")
        elif flow_mlh <= 0: errors.append("投与速度は0より大きい値を入力してください")
        
        if use_weight and (weight_kg is None or weight_kg <= 0):
            errors.append("体重(kg)を正しく入力してください")

        if errors:
            for e in errors: st.error(e)
            return
            
        # Basic Calculation
        conc_mg_ml = drug_mg / sol_ml
        dose_mg_h = flow_mlh * conc_mg_ml
        dose_gamma = None
        
        # Unit Logic
        preset_name = st.session_state.gamma_preset_selector
        preset_info = DRUG_PRESETS[preset_name]
        is_dex = "Dexmedetomidine" in preset_name
        is_propofol = "Propofol" in preset_name
        is_midazolam = "Midazolam" in preset_name
        
        # HTML Components
        res_main = f"{dose_mg_h:.2f} <span style='font-size:1rem'>mg/h</span>"
        res_sub_list = []
        
        if weight_kg:
            # Standard Gamma: μg/kg/min
            dose_gamma = (dose_mg_h * 1000) / (weight_kg * 60)
            
            # Alternative Units
            dose_mcg_kg_h = (dose_mg_h * 1000) / weight_kg
            dose_mg_kg_h = dose_mg_h / weight_kg

            if is_dex:
                # Dex: Show μg/kg/h AND γ
                res_sub_list.append(f"{dose_mcg_kg_h:.2f} <span style='font-size:0.9rem'>μg/kg/h</span>")
                res_sub_list.append(f"<span style='color:#666; font-size:0.8rem'>({dose_gamma:.3f} γ)</span>")
            elif is_propofol or is_midazolam:
                 # Propofol/Midazolam: mg/kg/h
                 res_sub_list.append(f"{dose_mg_kg_h:.2f} <span style='font-size:0.9rem'>mg/kg/h</span>")
            else:
                # Default: gamma
                res_sub_list.append(f"{dose_gamma:.2f} <span style='font-size:0.9rem'>μg/kg/min</span>")

        # Threshold Check & Warnings
        card_color = "result-card-green"
        warnings = []
        
        # 1. Preset based threshold
        thresh = GAMMA_THRESHOLDS.get(preset_name)
        if thresh and dose_gamma and dose_gamma > thresh:
            warnings.append(f"⚠️ {preset_name}の高用量域の可能性があります (> {thresh})")
            card_color = "result-card-yellow"
            
        # 2. Generic Extreme check
        if dose_mg_h > 2000: # Slightly relaxed
            warnings.append("⚠️ 投与量が極端に高値です (確認推奨)")
            card_color = "result-card-yellow"
        if dose_gamma and dose_gamma > 20.0: # Generic gamma cap
            warnings.append("⚠️ γ値が極端に高値です")
            card_color = "result-card-yellow"

        # Reference Text
        ref_text = ""
        if preset_info["ref"]:
            ref_text = f"推奨: {preset_info['ref']} (出典: {preset_info['source'] or '不明'})"

        # Output Render
        sub_html = " ".join(res_sub_list)
        st.markdown(f"""
        <div class="{card_color}">
            <div class="result-main">{res_main}</div>
            <div class="result-sub">{sub_html}</div>
            <div class="result-ref">{ref_text}</div>
        </div>
        """, unsafe_allow_html=True)
        
        for w in warnings:
            st.warning(w)

        with st.expander("詳細・計算式"):
            st.write(f"濃度: {conc_mg_ml:.3f} mg/mL")
            st.write(f"式 (mg/h): {flow_mlh} × {conc_mg_ml:.3f}")
            if weight_kg:
                st.write(f"体重: {weight_kg} kg")
                if is_dex:
                    st.write("μg/kg/h = γ × 60")
                if is_propofol:
                    st.write("mg/kg/h = mg/h ÷ kg")

# ==========================================
# 🧪 2. Renal Module
# ==========================================
def render_renal():
    st.markdown("### 🧪 CCr (Cockcroft-Gault)")
    
    st.text_input("年齢 (歳)", key="ccr_age", placeholder="例: 65")
    st.text_input("体重 (kg)", key="ccr_weight", placeholder="例: 55")
    st.text_input("Scr (mg/dL)", key="ccr_scr", placeholder="例: 0.9")
    sex = st.radio("性別", ["男性", "女性"], horizontal=True)
    
    if st.button("計算実行", type="primary", use_container_width=True):
        age = safe_float(st.session_state.ccr_age)
        weight = safe_float(st.session_state.ccr_weight)
        scr = safe_float(st.session_state.ccr_scr)
        
        if None in [age, weight, scr]:
            st.error("全ての数値を入力してください")
            return
        if scr <= 0:
            st.error("Scrは0より大きい必要があります")
            return
            
        ccr = ((140 - age) * weight) / (72 * scr)
        if sex == "女性":
            ccr *= 0.85
            
        if ccr < 30:
            color = "result-card-red"
            cat = "高度低下 (<30)"
        elif ccr < 60:
            color = "result-card-yellow"
            cat = "中等度低下 (30-60)"
        else:
            color = "result-card-green"
            cat = "正常〜軽度 (>60)"
            
        st.markdown(f"""
        <div class="{color}">
            <div class="result-main">{ccr:.1f} <span style='font-size:1rem'>mL/min</span></div>
            <div class="result-sub">{cat}</div>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# ⚖️ 3. Acid-Base Module
# ==========================================
def render_acidbase():
    st.markdown("### ⚖️ 酸塩基平衡")
    
    st.text_input("pH", key="ab_ph", placeholder="例: 7.32")
    st.text_input("PaCO2 (mmHg)", key="ab_pco2", placeholder="例: 35")
    st.text_input("HCO3- (mEq/L)", key="ab_hco3", placeholder="例: 18")
    st.text_input("Na (mEq/L)", key="ab_na", placeholder="例: 135")
    st.text_input("Cl (mEq/L)", key="ab_cl", placeholder="例: 98")
    st.text_input("Alb (g/dL) [任意]", key="ab_alb", placeholder="例: 3.5")
    
    if st.button("判定実行", type="primary", use_container_width=True):
        ph = safe_float(st.session_state.ab_ph)
        pco2 = safe_float(st.session_state.ab_pco2)
        hco3 = safe_float(st.session_state.ab_hco3)
        na = safe_float(st.session_state.ab_na)
        cl = safe_float(st.session_state.ab_cl)
        alb = safe_float(st.session_state.ab_alb)
        
        if None in [ph, pco2, hco3, na, cl]:
            st.error("Alb以外の必須項目を入力してください")
            return
        
        # Primary Disorder
        conclusions = []
        if ph < 7.35: main = "アシデミア (酸血症)"
        elif ph > 7.45: main = "アルカレミア (アルカリ血症)"
        else: main = "pH正常範囲"
        
        # AG Calc
        ag = na - (cl + hco3)
        ag_display = f"{ag:.1f}"
        
        # Corrected AG
        bg_color = "result-card-green"
        ag_extra_msg = ""
        
        eval_ag = ag
        if alb is not None:
            ag_corr = ag + 2.5 * (4.0 - alb)
            eval_ag = ag_corr
            ag_display += f" (補正 {ag_corr:.1f})"

        # AG Evaluation
        delta_ratio = None
        if eval_ag > 12:
            ag_extra_msg = " [AG開大]"
            bg_color = "result-card-yellow"
            
            # Delta Ratio
            delta_ag = eval_ag - 12
            delta_hco3 = 24 - hco3
            if delta_hco3 != 0:
                delta_ratio = delta_ag / delta_hco3
                if delta_ratio < 0.4:
                    conclusions.append("混合: 高Cl性アシドーシスの合併")
                elif delta_ratio > 2.0:
                    conclusions.append("混合: 代謝性アルカローシスの合併")
        
        # Output
        st.markdown(f"""
        <div class="{bg_color}">
            <div class="result-main">{main}</div>
            <div class="result-sub">AG: {ag_display}{ag_extra_msg}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Secondary findings
        for c in conclusions:
            st.info(c)
            
        # Detailed Expander (Winter's etc)
        with st.expander("詳細解析 (代償・予測)"):
            st.write(f"**Anion Gap**: {ag:.1f}")
            if alb: st.write(f"**補正AG**: {ag:.1f} + 2.5×(4-{alb}) = {ag_corr:.1f}")
            
            # Winter's Formula (Metabolic Acidosis)
            if hco3 < 24 and ph < 7.40 and pco2:
                expected_pco2 = 1.5 * hco3 + 8
                st.write(f"**Winter's Formula**: 予測PaCO2 = {expected_pco2:.1f} ± 2")
                if pco2 > (expected_pco2 + 2):
                    st.write("👉 呼吸性アシドーシスの合併 (代償不全)")
                elif pco2 < (expected_pco2 - 2):
                    st.write("👉 呼吸性アルカローシスの合併 (過代償)")
                else:
                    st.write("👉 呼吸性代償の範囲内")
            
            # Delta Ratio
            if delta_ratio is not None:
                st.write(f"**Delta Ratio (ΔAG/ΔHCO3)**: {delta_ratio:.2f}")

# ==========================================
# 🫀 4. Cardio Module
# ==========================================
def render_cardio():
    st.markdown("### 🫀 心不全・ショック")
    
    sbp = st.radio("収縮期血圧 (SBP)", ["維持 (>90)", "低下 (<90)"])
    skin = st.radio("皮膚所見 (灌流)", ["Warm (温かい)", "Cold (冷たい)"])
    lung = st.radio("肺うっ血 (聴診)", ["Dry (なし)", "Wet (あり)"])
    lac = st.radio("乳酸値", ["正常 (<2)", "上昇 (>2)"])

    if st.button("分類実行", type="primary", use_container_width=True):
        subset = ""
        action = []
        color = "result-card-green"
        
        if skin.startswith("Warm"):
            if lung.startswith("Dry"):
                subset = "Subset I (安定)"
                action = ["経過観察", "輸液過剰注意"]
            else:
                subset = "Subset II (うっ血)"
                action = ["血管拡張薬", "利尿薬"]
                color = "result-card-yellow"
        else: # Cold
            color = "result-card-red"
            if lung.startswith("Dry"):
                subset = "Subset III (低灌流)"
                action = ["輸液負荷試験", "強心薬"]
            else:
                subset = "Subset IV (最重症)"
                action = ["強心薬", "昇圧薬", "補助循環"]
        
        # Shock
        shock_msg = ""
        if sbp.startswith("低下"):
            shock_msg = "🚨 SHOCK"
            color = "result-card-red"
            if skin.startswith("Warm"):
                shock_msg += " (Distributive?)"
                action.insert(0, "Noradrenaline")
            else:
                if lung.startswith("Wet"):
                    shock_msg += " (Cardiogenic?)"
                    action.insert(0, "昇圧・強心")
                else:
                    shock_msg += " (Hypovolemic?)"
                    action.insert(0, "急速輸液")
                    
        final_title = f"{subset}"
        if shock_msg:
            final_title += f" + {shock_msg}"
            
        st.markdown(f"""
        <div class="{color}">
            <div class="result-main" style="font-size:1.3rem">{final_title}</div>
            <div class="result-sub">推奨: {' / '.join(action)}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if lac.startswith("上昇"):
            st.error("組織低灌流の疑い。再評価が必要です。")

# ==========================================
# 🚀 Global Router
# ==========================================
def main():
    # Vertical Menu for Mobile
    mode = st.radio(
        "機能選択", 
        ["γ計算 (持続投与)", "CCr (腎機能)", "酸塩基平衡", "心不全分類"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    if mode == "γ計算 (持続投与)":
        render_gamma()
    elif mode == "CCr (腎機能)":
        render_renal()
    elif mode == "酸塩基平衡":
        render_acidbase()
    elif mode == "心不全分類":
        render_cardio()

if __name__ == "__main__":
    main()

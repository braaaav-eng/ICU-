import streamlit as st
import json
import math

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
# 🩺 Clinical Constants & Thresholds (Editable)
# ------------------------------------------

# === Clinical constants & mappings (編集可能) ===
GAMMA_THRESHOLDS = {
    "Norepinephrine (NAD)": {"type":"ug/kg/min", "threshold": 0.3},
    "Dobutamine (DOB)": {"type":"ug/kg/min", "threshold": 10.0},
    "Dopamine (DOA)": {"type":"ug/kg/min", "threshold": 10.0},
    "Nicardipine": {"type":"ug/kg/min", "threshold": 5.0},
    "Midazolam": {"type":"mg/kg/h", "threshold": 0.2},
    "Propofol": {"type":"mg/kg/h", "threshold": 3.0},
    "Dexmedetomidine": {"type":"ug/kg/h", "threshold": 0.7},
    "Nitroglycerin": {"type":"ug/kg/min", "threshold": 5.0},
    "Carperitide": {"type":"ug/kg/min", "threshold": 0.1}
}

FORRESTER_CI = 2.2
FORRESTER_PCWP = 18.0

FENA_PRERENAL = 1.0
FENA_ATN = 2.0
FEUREA_PRERENAL = 35.0

MOL_WEIGHTS = {
    "Na": 23.0, "K": 39.1, "Cl": 35.5, 
    "Ca": 40.1, "Mg": 24.3, "P": 31.0
}
VALENCES = {
    "Na": 1, "K": 1, "Cl": 1, 
    "Ca": 2, "Mg": 2, "P": 1
}

DRUG_PRESETS = {
    "カスタム": {"mg": None, "ml": None},
    "Norepinephrine (NAD)": {"mg": 5.0, "ml": 50.0},
    "Dobutamine (DOB)": {"mg": 150.0, "ml": 50.0},
    "Dopamine (DOA)": {"mg": 150.0, "ml": 50.0},
    "Nicardipine": {"mg": 50.0, "ml": 50.0},
    "Midazolam": {"mg": 50.0, "ml": 50.0},
    "Propofol": {"mg": 1000.0, "ml": 100.0},
    "Dexmedetomidine": {"mg": 0.2, "ml": 50.0},
    "Nitroglycerin": {"mg": 50.0, "ml": 100.0},
    "Carperitide": {"mg": 3.0, "ml": 50.0}
}

# ==========================================
# 🩹 Session Initialization & Utils
# ==========================================
if "initialized" not in st.session_state:
    st.session_state.update({
        # Gamma
        "gamma_preset": "カスタム",
        "gamma_mg": None,
        "gamma_ml": None,
        "gamma_flow": None,
        "gamma_wt": None,
        # CCr
        "ccr_age": None,
        "ccr_wt": None,
        "ccr_scr": None,
        "ccr_sex": "男性",
        # Acid/base
        "ab_ph": None,
        "ab_pco2": None,
        "ab_hco3": None,
        "ab_na": None,
        "ab_cl": None,
        "ab_alb": None,
        # Shock
        "shock_sbp": None,
        "shock_dbp": None,
        "shock_hr": None,
        "shock_lac": None,
        # HF
        "hf_co": None,
        "hf_bsa": None,
        "hf_pcwp": None,
        # Renal
        "renal_una": None,
        "renal_pna": None,
        "renal_ucr": None,
        "renal_pcr": None,
        "renal_uurea": None,
        "renal_purea": None,
    })
    st.session_state["initialized"] = True

def preset_apply_to_session(preset_key):
    """Apply preset values to session state, allowing None for custom."""
    data = DRUG_PRESETS.get(preset_key, {"mg": None, "ml": None})
    st.session_state["gamma_mg"] = data.get("mg")
    st.session_state["gamma_ml"] = data.get("ml")

# ==========================================
# 🎨 Styles & Scripts
# ==========================================
st.markdown("""
<style>
    /* 1. Mobile Top Spacing */
    .block-container {
        padding-top: 2.8rem !important;
        padding-bottom: 5rem !important;
        max-width: 600px;
    }
    /* 2. Form & Inputs */
    .stNumberInput input { font-size: 16px !important; }
    .stSelectbox div { font-size: 16px !important; }
    
    /* 3. Result Cards */
    .result-card-green {
        background-color: #dcfce7; padding: 12px; border-radius: 8px; 
        border-left: 5px solid #22c55e; margin: 10px 0;
    }
    .result-card-yellow {
        background-color: #fef9c3; padding: 12px; border-radius: 8px; 
        border-left: 5px solid #eab308; margin: 10px 0;
    }
    .result-card-red {
        background-color: #fee2e2; padding: 12px; border-radius: 8px; 
        border-left: 5px solid #ef4444; margin: 10px 0;
    }
    .res-main { font-size: 1.4rem; font-weight: bold; color: #1f2937; }
    .res-sub { font-size: 1.0rem; color: #4b5563; margin-top: 4px; }
    
    /* Hide Footer */
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# iOS Numeric Keyboard Helper
st.markdown("""
<script>
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function(){
        const inputs = document.querySelectorAll('input[type="number"]');
        inputs.forEach(i => i.setAttribute('inputmode', 'decimal'));
    }, 1000);
});
</script>
""", unsafe_allow_html=True)


# ==========================================
# 🧠 Logic Functions
# ==========================================
def calc_gamma(drug_mg, sol_ml, flow, wt=None):
    if not drug_mg or not sol_ml or not flow:
        return None
    conc = drug_mg / sol_ml
    mg_h = flow * conc
    gamma = None
    if wt and wt > 0:
        gamma = (mg_h * 1000) / (wt * 60)
    return {"conc": conc, "mg_h": mg_h, "gamma": gamma}

def calc_ccr(age, wt, scr, sex):
    if not scr or scr <= 0: return None
    ccr = ((140 - age) * wt) / (72 * scr)
    if sex == "女性": ccr *= 0.85
    return ccr

def calc_fena(p_na, u_na, p_cr, u_cr):
    if not p_na or not u_cr or (p_na * u_cr) == 0: return None
    return (u_na * p_cr) / (p_na * u_cr) * 100

def calc_feurea(p_urea, u_urea, p_cr, u_cr):
    if not p_urea or not u_cr or (p_urea * u_cr) == 0: return None
    return (u_urea * p_cr) / (p_urea * u_cr) * 100

# ==========================================
# 📱 Modules
# ==========================================

def render_gamma_module():
    st.header("💉 γ計算 (持続投与)")

    # Preset selection
    current_preset = st.session_state.get("gamma_preset", "カスタム")
    preset = st.selectbox("薬剤プリセット", list(DRUG_PRESETS.keys()),
                          index=list(DRUG_PRESETS.keys()).index(current_preset))
    
    if preset != current_preset:
        st.session_state["gamma_preset"] = preset
        preset_apply_to_session(preset)
        st.rerun()

    with st.form("gamma_form"):
        drug_mg = st.number_input("薬剤総量 (mg)", min_value=0.0, step=0.1, format="%.1f", key="gamma_mg", value=None)
        sol_ml = st.number_input("溶解総量 (mL)", min_value=0.0, step=0.1, format="%.1f", key="gamma_ml", value=None)
        flow = st.number_input("投与速度 (mL/h)", min_value=0.0, step=0.1, format="%.1f", key="gamma_flow", value=None)
        
        use_wt = st.checkbox("体重で換算する", value=True)
        if use_wt:
            wt = st.number_input("体重 (kg)", min_value=0.0, step=0.1, format="%.1f", key="gamma_wt", value=None)
        else:
            wt = None

        submitted = st.form_submit_button("計算")

    if submitted:
        if drug_mg is None or sol_ml is None or flow is None:
            st.error("必須項目（薬剤量・溶解量・投与速度）を入力してください")
            return
            
        res = calc_gamma(drug_mg, sol_ml, flow, wt)
        if not res:
            st.error("入力値エラー")
            return
            
        mg_h = res["mg_h"]
        gamma = res["gamma"]
        conc = res["conc"]
        
        # Display Logic
        cfg = GAMMA_THRESHOLDS.get(preset)
        card = "result-card-green"
        warning = None
        display_secondary = ""

        if gamma is not None:
            # Threshold Check
            if cfg:
                if cfg["type"] == "ug/kg/h":
                    if gamma * 60 > cfg["threshold"]:
                        warning = f"注意: {preset} の閾値 {cfg['threshold']} μg/kg/h を超えています"
                        card = "result-card-yellow"
                    display_secondary = f"{gamma*60:.2f} μg/kg/h (= {gamma:.3f} μg/kg/min)"
                elif cfg["type"] == "ug/kg/min":
                    if gamma > cfg["threshold"]:
                        warning = f"注意: {preset} の閾値 {cfg['threshold']} μg/kg/min を超えています"
                        card = "result-card-yellow"
                    display_secondary = f"{gamma:.3f} μg/kg/min"
                elif cfg["type"] == "mg/kg/h":
                    mgkg_h = (mg_h / wt) if wt else 0
                    if mgkg_h > cfg["threshold"]:
                        warning = f"注意: {preset} の閾値 {cfg['threshold']} mg/kg/h を超えています"
                        card = "result-card-yellow"
                    display_secondary = f"{mgkg_h:.3f} mg/kg/h"
        else:
            display_secondary = "(体重未入力のため γ計算なし)"

        st.markdown(f"""
        <div class="{card}">
            <div class='res-main'>{mg_h:.2f} mg/h</div>
            <div class='res-sub'>{display_secondary}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if warning: st.warning(warning)
        
        with st.expander("計算根拠"):
            st.write(f"濃度: {conc:.4f} mg/mL")
            if gamma is not None:
                st.write(f"γ = ({mg_h:.4f} × 1000) / ({wt} × 60) = {gamma:.4f}")


def render_ccr_module():
    st.header("🧪 CCr (Cockcroft-Gault)")
    
    with st.form("ccr_form"):
        age = st.number_input("年齢 (歳)", min_value=0, step=1, format="%d", key="ccr_age", value=None)
        wt = st.number_input("体重 (kg)", min_value=0.0, step=0.1, format="%.1f", key="ccr_wt", value=None)
        scr = st.number_input("Scr (mg/dL)", min_value=0.0, step=0.01, format="%.2f", key="ccr_scr", value=None)
        sex = st.radio("性別", ["男性", "女性"], key="ccr_sex", horizontal=True)
        
        submitted = st.form_submit_button("計算")
        
    if submitted:
        if age is None or wt is None or scr is None:
            st.error("全項目を入力してください")
        else:
            val = calc_ccr(age, wt, scr, sex)
            if val:
                cat = "正常"
                col = "result-card-green"
                if val < 30: 
                    cat = "高度低下 (<30)"
                    col = "result-card-red"
                elif val < 60:
                    cat = "中等度低下 (30-60)"
                    col = "result-card-yellow"
                    
                st.markdown(f"""
                <div class="{col}">
                    <div class="res-main">{val:.1f} mL/min</div>
                    <div class="res-sub">{cat}</div>
                </div>
                """, unsafe_allow_html=True)


def render_ab_module():
    st.header("⚖️ 酸塩基平衡")
    
    with st.form("ab_form"):
        ph = st.number_input("pH", step=0.01, format="%.2f", key="ab_ph", value=None)
        c1, c2 = st.columns(2)
        pco2 = c1.number_input("PaCO2 (mmHg)", step=0.1, format="%.1f", key="ab_pco2", value=None)
        hco3 = c2.number_input("HCO3- (mmol/L)", step=0.1, format="%.1f", key="ab_hco3", value=None)
        c3, c4 = st.columns(2)
        na = c3.number_input("Na (mmol/L)", step=0.1, format="%.1f", key="ab_na", value=None)
        cl = c4.number_input("Cl (mmol/L)", step=0.1, format="%.1f", key="ab_cl", value=None)
        alb = st.number_input("Alb (g/dL, 任意)", step=0.1, format="%.1f", key="ab_alb", value=None)
        
        submitted = st.form_submit_button("判定")
        
    if submitted:
        if ph is None or pco2 is None or hco3 is None or na is None or cl is None:
            st.error("Alb以外の全項目を入力してください")
            return
            
        real_alb = alb if alb is not None else 4.0
        
        # AG
        ag = na - (cl + hco3)
        ag_corr = ag + 2.5 * (4.0 - real_alb)
        
        state = "pH正常範囲"
        if ph < 7.35: state = "アシデミア"
        elif ph > 7.45: state = "アルカレミア"
        
        is_high_ag = ag_corr > 12
        detail = []
        
        if is_high_ag:
            state += " (AG開大)"
            d_ag = ag_corr - 12
            d_hco3 = 24 - hco3
            if d_hco3 != 0:
                ratio = d_ag / d_hco3
                if ratio < 0.4: detail.append("高Cl性アシドーシス合併? (Ratio<0.4)")
                elif ratio > 2.0: detail.append("代謝性アルカローシス合併? (Ratio>2.0)")
                
        # Winter
        if hco3 < 24 and ph < 7.40:
            exp_pco2 = 1.5 * hco3 + 8
            detail.append(f"予測PaCO2: {exp_pco2:.1f}±2")
            if pco2 > exp_pco2 + 2: detail.append("呼吸性代償不全 (Resp Acidosis)")
            elif pco2 < exp_pco2 - 2: detail.append("過代償 (Resp Alkalosis)")
            
        col = "result-card-yellow" if "アシデミア" in state or is_high_ag else "result-card-green"
        st.markdown(f"""
        <div class="{col}">
            <div class="res-main">{state}</div>
            <div class="res-sub">AG(補正): {ag_corr:.1f}</div>
        </div>
        """, unsafe_allow_html=True)
        for d in detail: st.info(d)


def render_shock_module():
    st.header("🚨 ショック評価")
    with st.form("shock_form"):
        sbp = st.number_input("SBP (mmHg)", min_value=0, step=1, key="shock_sbp", value=None)
        dbp = st.number_input("DBP (mmHg)", min_value=0, step=1, key="shock_dbp", value=None)
        hr = st.number_input("HR (bpm)", min_value=0, step=1, key="shock_hr", value=None)
        lactate = st.number_input("乳酸 (mmol/L)", min_value=0.0, step=0.1, format="%.1f", key="shock_lac", value=None)
        
        skin = st.selectbox("皮膚所見", ["Cold", "Warm"])
        infection = st.checkbox("感染兆候あり")
        bleeding = st.checkbox("出血/外傷あり")
        jvd = st.checkbox("頸静脈怒張")
        submitted = st.form_submit_button("評価")
        
    if submitted:
        if sbp is None or dbp is None or lactate is None:
            st.error("血圧と乳酸値を入力してください")
            return
            
        map_val = (sbp + 2*dbp) / 3.0
        shock_flag = map_val < 65 or sbp < 90
        lactate_flag = lactate >= 2.0
        
        possibilities = []
        actions = []
        if shock_flag and lactate_flag and (infection or skin=="Warm"):
            possibilities.append("敗血症性 (Distributive)")
            actions.append("輸液 → NAD")
        if bleeding:
            possibilities.append("出血性 (Hypovolemic)")
            actions.append("輸血/止血")
        if jvd and skin=="Cold":
            possibilities.append("閉塞性/心原性")
            actions.append("心エコー確認")
            
        severity = "高" if (shock_flag and lactate_flag) else "中"
        if not shock_flag and not lactate_flag: severity = "低/なし"

        st.markdown(f"""<div class='result-card-red'>
            <div class='res-main'>ショック可能性: {severity}</div>
            <div class='res-sub'>疑い: {', '.join(possibilities) if possibilities else '---'}</div>
            </div>""", unsafe_allow_html=True)
        st.info(f"MAP: {map_val:.1f}, Lactate: {lactate}")


def render_hf_module():
    st.header("🫀 心不全 (Forrester)")
    with st.form("hf_form"):
        co = st.number_input("CO (L/min)", min_value=0.0, step=0.1, format="%.1f", key="hf_co", value=None)
        bsa = st.number_input("BSA (m2)", min_value=0.0, step=0.1, format="%.1f", key="hf_bsa", value=None)
        pcwp = st.number_input("PCWP (mmHg)", min_value=0, step=1, key="hf_pcwp", value=None)
        
        submitted = st.form_submit_button("分類")
        
    if submitted:
        if co is None or bsa is None or pcwp is None:
            st.error("全数値を入力してください")
            return
            
        ci = co / bsa if bsa > 0 else 0
        is_wet = pcwp >= FORRESTER_PCWP
        is_cold = ci < FORRESTER_CI
        
        subset = "I"
        if is_wet and not is_cold: subset = "II"
        elif not is_wet and is_cold: subset = "III"
        elif is_wet and is_cold: subset = "IV"
        
        st.markdown(f"""
        <div class="result-card-yellow">
            <div class="res-main">Subset {subset}</div>
            <div class="res-sub">CI: {ci:.2f}, PCWP: {pcwp}</div>
        </div>
        """, unsafe_allow_html=True)


def render_renal_diff():
    st.header("💧 腎障害鑑別")
    with st.form("renal_form"):
        c1, c2 = st.columns(2)
        u_na = c1.number_input("尿中Na", step=0.1, key="renal_una", value=None)
        p_na = c2.number_input("血清Na", step=0.1, key="renal_pna", value=None)
        c3, c4 = st.columns(2)
        u_cr = c3.number_input("尿中Cr", step=0.1, key="renal_ucr", value=None)
        p_cr = c4.number_input("血清Cr", step=0.1, key="renal_pcr", value=None)
        
        do_urea = st.checkbox("FeUrea")
        u_urea = None; p_urea = None
        if do_urea:
            c5, c6 = st.columns(2)
            u_urea = c5.number_input("尿Urea", step=0.1, key="renal_uurea", value=None)
            p_urea = c6.number_input("血清Urea", step=0.1, key="renal_purea", value=None)
            
        submitted = st.form_submit_button("計算")
        
    if submitted:
        fena = calc_fena(p_na, u_na, p_cr, u_cr)
        if fena is not None:
            st.success(f"FeNa: {fena:.2f}%")
        
        if do_urea:
            feurea = calc_feurea(p_urea, u_urea, p_cr, u_cr)
            if feurea is not None:
                st.info(f"FeUrea: {feurea:.2f}%")

def render_calc_tools():
    st.header("⚗️ 単位変換")
    with st.form("calc_form"):
        ion = st.selectbox("対象", ["Na", "K", "Cl", "Ca", "Mg", "P"])
        val = st.number_input("値", min_value=0.0, step=0.1, format="%.1f", value=None)
        unit = st.radio("入力単位", ["mg/dL", "mmol/L"], horizontal=True)
        submitted = st.form_submit_button("変換")
        
    if submitted and val is not None:
        mw = MOL_WEIGHTS[ion]
        res_mg = val if unit=="mg/dL" else (val * mw)/10
        res_mmol = (val * 10)/mw if unit=="mg/dL" else val
        st.write(f"{res_mg:.2f} mg/dL | {res_mmol:.2f} mmol/L")

def render_na_diff():
    st.header("🧂 低Na鑑別")
    st.write("Step by Step フロー")
    # Simple static content logic similar to before, inputs kept minimal or none needed here
    step = st.selectbox("Step", ["1. Posm", "2. Uosm", "3. Volume"])
    if step[0]=="1": st.info("Check Posm (Hypotonic?)")
    elif step[0]=="2": st.info("Check Uosm (>100?)")
    elif step[0]=="3": st.info("Check Volume Status")

def render_export_import():
    st.header("💾 保存・読込")
    st.markdown("現在の入力値をJSONで保存")
    
    # Export keys to clean names (removed _str suffixes)
    export_keys = [
        "gamma_preset", "gamma_mg", "gamma_ml", "gamma_flow", "gamma_wt",
        "ccr_age", "ccr_wt", "ccr_scr", "ccr_sex",
        "ab_ph", "ab_pco2", "ab_hco3", "ab_na", "ab_cl", "ab_alb"
    ]
    data = {k: st.session_state.get(k) for k in export_keys}
    st.download_button("JSON保存", json.dumps(data, ensure_ascii=False, indent=2), "icu_draft.json")
    
    uploaded = st.file_uploader("読込", type=["json"])
    if uploaded:
        try:
            d = json.load(uploaded)
            for k, v in d.items():
                if k in export_keys: st.session_state[k] = v
            st.success("復元しました")
        except: st.error("読込エラー")

# ==========================================
# 🚀 Main Router
# ==========================================
def main():
    MODES = [
        "γ計算", "CCr (腎機能)", "酸塩基平衡", 
        "🚨 ショック", "🫀 心不全", 
        "💧 腎障害鑑別", "🧂 低Na鑑別", "⚗️ 単位変換",
        "💾 保存・読込"
    ]
    st.title("ICU Pharm Tool")
    mode = st.radio("Menu", MODES, label_visibility="collapsed")
    st.markdown("---")
    
    if mode == "γ計算": render_gamma_module()
    elif mode == "CCr (腎機能)": render_ccr_module()
    elif mode == "酸塩基平衡": render_ab_module()
    elif mode == "🚨 ショック": render_shock_module()
    elif mode == "🫀 心不全": render_hf_module()
    elif mode == "💧 腎障害鑑別": render_renal_diff()
    elif mode == "🧂 低Na鑑別": render_na_diff()
    elif mode == "⚗️ 単位変換": render_calc_tools()
    elif mode == "💾 保存・読込": render_export_import()

if __name__ == "__main__":
    main()

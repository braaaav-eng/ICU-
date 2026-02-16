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
# 🩺 Clinical Constants & Thresholds
# ------------------------------------------
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
# 🩹 Session Initialization
# ==========================================
if "initialized" not in st.session_state:
    st.session_state.update({
        # Gamma
        "gamma_preset": "カスタム",
        "gamma_mg": None, "gamma_ml": None, "gamma_flow": None, "gamma_wt": None,
        # CCr
        "ccr_age": None, "ccr_wt": None, "ccr_scr": None, "ccr_sex": "男性",
        # Acid/base
        "ab_ph": None, "ab_pco2": None, "ab_hco3": None, "ab_na": None, "ab_cl": None, "ab_alb": None,
        # Shock
        "shock_sbp": None, "shock_dbp": None, "shock_hr": None, "shock_lac": None,
        # HF
        "hf_co": None, "hf_bsa": None, "hf_pcwp": None,
        # Renal
        "renal_una": None, "renal_pna": None, "renal_ucr": None, "renal_pcr": None,
        "renal_bun": None, "renal_uosm": None, # Expanded inputs
    })
    st.session_state["initialized"] = True

def preset_apply_to_session(preset_key):
    data = DRUG_PRESETS.get(preset_key, {"mg": None, "ml": None})
    st.session_state["gamma_mg"] = data.get("mg")
    st.session_state["gamma_ml"] = data.get("ml")

# ==========================================
# 🎨 Styles
# ==========================================
st.markdown("""
<style>
    .block-container {
        padding-top: 2.8rem !important;
        padding-bottom: 5rem !important;
        max-width: 600px;
    }
    .stNumberInput input { font-size: 16px !important; }
    .stSelectbox div { font-size: 16px !important; }
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Result Box Styles */
    .res-box {
        padding: 15px; border-radius: 8px; margin-bottom: 10px;
        border: 1px solid #e5e7eb;
    }
    .res-title { font-weight: bold; font-size: 1.1rem; margin-bottom: 5px; }
    .res-val { font-size: 1.5rem; font-weight: bold; color: #111827; }
    .res-sub { color: #6b7280; font-size: 0.9rem; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# iOS Keyboard Helper
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
        st.caption("例: 5.0")
        
        sol_ml = st.number_input("溶解総量 (mL)", min_value=0.0, step=0.1, format="%.1f", key="gamma_ml", value=None)
        st.caption("例: 50.0")
        
        flow = st.number_input("投与速度 (mL/h)", min_value=0.0, step=0.1, format="%.1f", key="gamma_flow", value=None)
        st.caption("例: 3.0")
        
        use_wt = st.checkbox("体重で換算する", value=True)
        wt = None
        if use_wt:
            wt = st.number_input("体重 (kg)", min_value=0.0, step=0.1, format="%.1f", key="gamma_wt", value=None)
            st.caption("例: 50.0")

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
        warning = None

        if gamma is not None and cfg:
            # Threshold Check
            if cfg["type"] == "ug/kg/h":
                if gamma * 60 > cfg["threshold"]: warning = f"注意: 閾値 {cfg['threshold']} μg/kg/h 超過"
            elif cfg["type"] == "ug/kg/min":
                if gamma > cfg["threshold"]: warning = f"注意: 閾値 {cfg['threshold']} μg/kg/min 超過"
            elif cfg["type"] == "mg/kg/h":
                mgkg_h = (mg_h / wt) if wt else 0
                if mgkg_h > cfg["threshold"]: warning = f"注意: 閾値 {cfg['threshold']} mg/kg/h 超過"

        # === Result Display ===
        st.markdown(f"### 結果")
        col_bg = "#fef2f2" if warning else "#ecfdf5"
        border = "#ef4444" if warning else "#10b981"
        
        st.markdown(f"""
        <div style="background-color:{col_bg}; padding:15px; border-radius:8px; border-left:5px solid {border}; margin-bottom:10px;">
            <div style="font-size:1.2rem; font-weight:bold; margin-bottom:4px;">流量: {mg_h:.2f} mg/h</div>
            {f'<div style="font-size:1.4rem; color:#111827; font-weight:bold;">γ: {gamma:.3f} μg/kg/min</div>' if gamma is not None else '<div style="color:#6b7280;">(体重未入力のためγ未計算)</div>'}
            {f'<div style="font-size:1.1rem; color:#4b5563;">= {gamma*60:.2f} μg/kg/h</div>' if gamma is not None else ''}
        </div>
        """, unsafe_allow_html=True)
        
        if warning: st.warning(warning)
        
        with st.expander("計算詳細"):
            st.write(f"濃度: {conc:.4f} mg/mL")
            if gamma is not None:
                st.write(f"γ = ({mg_h:.4f} × 1000) / ({wt} × 60)")


def render_ccr_module():
    st.header("🧪 CCr (Cockcroft-Gault)")
    
    with st.form("ccr_form"):
        age = st.number_input("年齢 (歳)", min_value=0, step=1, format="%d", key="ccr_age", value=None)
        st.caption("例: 65")
        wt = st.number_input("体重 (kg)", min_value=0.0, step=0.1, format="%.1f", key="ccr_wt", value=None)
        st.caption("例: 50.0")
        scr = st.number_input("Scr (mg/dL)", min_value=0.0, step=0.01, format="%.2f", key="ccr_scr", value=None)
        st.caption("例: 1.05")
        sex = st.radio("性別", ["男性", "女性"], key="ccr_sex", horizontal=True)
        
        submitted = st.form_submit_button("計算")
        
    if submitted:
        if age is None or wt is None or scr is None:
            st.error("全項目を入力してください")
        else:
            val = calc_ccr(age, wt, scr, sex)
            if val:
                st.metric("CCr (mL/min)", f"{val:.1f}")
                if val < 30: st.error("高度低下 (<30)")
                elif val < 60: st.warning("中等度低下 (30-60)")
                else: st.success("正常 (>60)")


def render_ab_module():
    st.header("⚖️ 酸塩基平衡")
    
    with st.form("ab_form"):
        ph = st.number_input("pH", step=0.01, format="%.2f", key="ab_ph", value=None)
        st.caption("例: 7.40")
        c1, c2 = st.columns(2)
        pco2 = c1.number_input("PaCO2 (mmHg)", step=0.1, format="%.1f", key="ab_pco2", value=None)
        st.caption("例: 40.0")
        hco3 = c2.number_input("HCO3- (mmol/L)", step=0.1, format="%.1f", key="ab_hco3", value=None)
        st.caption("例: 24.0")
        c3, c4 = st.columns(2)
        na = c3.number_input("Na (mmol/L)", step=0.1, format="%.1f", key="ab_na", value=None)
        st.caption("例: 140.0")
        cl = c4.number_input("Cl (mmol/L)", step=0.1, format="%.1f", key="ab_cl", value=None)
        st.caption("例: 100.0")
        alb = st.number_input("Alb (g/dL)", step=0.1, format="%.1f", key="ab_alb", value=None)
        st.caption("例: 4.0 (未入力時は4.0扱い)")
        
        submitted = st.form_submit_button("判定")
        
    if submitted:
        if ph is None or pco2 is None or hco3 is None or na is None or cl is None:
            st.error("Alb以外の全項目を入力してください")
            return
            
        real_alb = alb if alb is not None else 4.0
        ag = na - (cl + hco3)
        ag_corr = ag + 2.5 * (4.0 - real_alb)
        
        st.info(f"Anion Gap (補正): {ag_corr:.1f}")
        
        msgs = []
        if ph < 7.35: msgs.append("アシデミア")
        elif ph > 7.45: msgs.append("アルカレミア")
        
        if ag_corr > 12:
            msgs.append("AG開大性代謝性アシドーシス")
        
        # Winter
        if hco3 < 24 and ph < 7.40:
            exp = 1.5 * hco3 + 8
            if pco2 > exp + 2: msgs.append("呼吸性アシドーシス合併")
            elif pco2 < exp - 2: msgs.append("呼吸性アルカローシス合併")
        
        for m in msgs:
            st.write(f"・{m}")


def render_shock_module():
    st.header("🚨 ショック評価")
    with st.form("shock_form"):
        sbp = st.number_input("SBP (mmHg)", min_value=0, step=1, key="shock_sbp", value=None)
        st.caption("例: 80")
        dbp = st.number_input("DBP (mmHg)", min_value=0, step=1, key="shock_dbp", value=None)
        st.caption("例: 50")
        lactate = st.number_input("乳酸 (mmol/L)", min_value=0.0, step=0.1, format="%.1f", key="shock_lac", value=None)
        st.caption("例: 3.5")
        
        skin = st.selectbox("皮膚所見", ["Cold", "Warm"])
        submitted = st.form_submit_button("評価")
        
    if submitted:
        if sbp is None or dbp is None or lactate is None:
            st.error("数値を入力してください")
            return
        map_val = (sbp + 2*dbp) / 3.0
        st.metric("平均血圧 (MAP)", f"{map_val:.1f} mmHg")
        
        if map_val < 65 or sbp < 90 or lactate >= 2.0:
            st.error("ショックの疑いあり (MAP<65 or Lac>=2)")
            if skin == "Warm": st.write("Warm Shock: 敗血症性などを考慮 → 輸液負荷・NAD")
            else: st.write("Cold Shock: 心原性・循環血液量減少などを考慮")
        else:
            st.success("血行動態は比較的安定しています")


def render_hf_module():
    st.header("🫀 心不全 (Forrester)")
    with st.form("hf_form"):
        co = st.number_input("CO (L/min)", min_value=0.0, step=0.1, format="%.1f", key="hf_co", value=None)
        st.caption("例: 4.5")
        bsa = st.number_input("BSA (m2)", min_value=0.0, step=0.1, format="%.1f", key="hf_bsa", value=None)
        st.caption("例: 1.6")
        pcwp = st.number_input("PCWP (mmHg)", min_value=0, step=1, key="hf_pcwp", value=None)
        st.caption("例: 20")
        
        submitted = st.form_submit_button("分類")
        
    if submitted:
        if co is None or bsa is None or pcwp is None:
            st.error("全数値を入力してください")
            return
            
        ci = co / bsa if bsa > 0 else 0
        is_wet = pcwp >= FORRESTER_PCWP
        is_cold = ci < FORRESTER_CI
        
        # Determine subset and explanation
        subset = ""
        desc = ""
        action = ""
        color = ""
        
        if not is_wet and not is_cold:
            subset = "I (Warm & Dry)"
            desc = "正常: 循環維持、うっ血なし"
            action = "経過観察"
            color = "#dcfce7"
        elif is_wet and not is_cold:
            subset = "II (Warm & Wet)"
            desc = "うっ血あり + 末梢循環保たれている"
            action = "血管拡張薬 + 利尿薬 を検討"
            color = "#fef9c3"
        elif not is_wet and is_cold:
            subset = "III (Cold & Dry)"
            desc = "低灌流 + 容量不足の可能性"
            action = "輸液負荷テスト + 強心薬 を検討"
            color = "#fef9c3"
        elif is_wet and is_cold:
            subset = "IV (Cold & Wet)"
            desc = "うっ血 + 低灌流 (最重症)"
            action = "強心薬 + 昇圧薬 + 補助循環 を検討"
            color = "#fee2e2"
            
        st.markdown(f"""
        <div style="background-color:{color}; padding:15px; border-radius:8px; margin-bottom:10px;">
            <h3>Subset {subset}</h3>
            <p><strong>{desc}</strong></p>
            <p>推奨: {action}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write(f"CI: {ci:.2f} (閾値 2.2) / PCWP: {pcwp} (閾値 18)")


def render_renal_diff():
    st.header("💧 腎障害鑑別")
    with st.form("renal_form"):
        c1, c2 = st.columns(2)
        u_na = c1.number_input("尿中Na (mmol/L)", step=0.1, key="renal_una", value=None)
        p_na = c2.number_input("血清Na (mmol/L)", step=0.1, key="renal_pna", value=None)
        c3, c4 = st.columns(2)
        u_cr = c3.number_input("尿中Cr (mg/dL)", step=0.1, key="renal_ucr", value=None)
        p_cr = c4.number_input("血清Cr (mg/dL)", step=0.1, key="renal_pcr", value=None)
        
        c5, c6 = st.columns(2)
        bun = c5.number_input("BUN (mg/dL)", step=0.1, key="renal_bun", value=None)
        uosm = c6.number_input("尿浸透圧 (mOsm/kg)", step=1.0, key="renal_uosm", value=None)
        st.caption("※BUN/尿浸透圧は任意")
        
        submitted = st.form_submit_button("計算")
        
    if submitted:
        # FENa
        fena = None
        if u_na and p_na and u_cr and p_cr:
            fena = calc_fena(p_na, u_na, p_cr, u_cr)
            
        # BUN/Cr Ratio
        buncr = None
        if bun and p_cr and p_cr > 0:
            buncr = bun / p_cr
            
        st.subheader("分析結果")
        
        # Findings
        findings = []
        is_prerenal = False
        is_atn = False
        
        if fena is not None:
            st.metric("FENa", f"{fena:.2f} %")
            if fena < 1.0:
                findings.append("FENa < 1% : 腎前性疑い")
                is_prerenal = True
            elif fena > 2.0:
                findings.append("FENa > 2% : 腎性 (ATN) 疑い")
                is_atn = True
            else:
                findings.append("FENa 1-2%: 中間域")
                
        if buncr is not None:
            st.write(f"BUN/Cr比: {buncr:.1f}")
            if buncr > 20: 
                findings.append("BUN/Cr > 20 : 腎前性疑い")
                is_prerenal = True
                
        if uosm is not None:
            st.write(f"尿浸透圧: {uosm}")
            if uosm > 500:
                findings.append("Uosm > 500 : 腎前性疑い (濃縮能維持)")
                is_prerenal = True
            elif uosm < 350:
                findings.append("Uosm < 350 : 濃縮能低下 (ATN等)")
                is_atn = True
                
        if findings:
            for f in findings: st.info(f)
            
            # Conclusion
            if is_prerenal and not is_atn:
                st.success("総合判定: 腎前性 を強く示唆")
            elif is_atn and not is_prerenal:
                st.error("総合判定: 腎性 (ATN) を強く示唆")
            else:
                st.warning("総合判定: 混在 または 鑑別困難")
        else:
            st.write("データ不足のため判定できません")


def render_na_diff():
    st.header("🧂 低Na鑑別フロー")
    
    st.markdown("### 【Step 1】血清浸透圧 (Posm)")
    st.write("・**高値 (>295)** → 高血糖、マンニトール投与など")
    st.write("・**正常 (280-295)** → 偽性低Na血症 (高脂血症、高蛋白)")
    st.write("・**低値 (<275)** → 真の低Na血症 ⇒ Step 2へ")
    
    st.markdown("---")
    st.markdown("### 【Step 2】尿浸透圧 (Uosm)")
    st.write("・**< 100 mOsm/kg** → 水過剰摂取 (心因性多飲、ビール多飲)")
    st.write("・**> 100 mOsm/kg** → ADH分泌あり (ADH作用過剰) ⇒ Step 3へ")
    
    st.markdown("---")
    st.markdown("### 【Step 3】尿中Na濃度 (U_Na)")
    st.write("・**< 20 mmol/L** → 有効循環血漿量低下 (心不全、肝硬変、ネフローゼ、脱水)")
    st.write("・**> 20-30 mmol/L** → SIADH、腎性塩類喪失、利尿薬、副腎不全、甲状腺機能低下")


def render_calc_tools():
    st.header("⚗️ 単位変換")
    with st.form("calc_form"):
        ion = st.selectbox("対象", ["Na", "K", "Cl", "Ca", "Mg", "P"])
        val = st.number_input("値", min_value=0.0, step=0.1, format="%.1f", value=None)
        st.caption("例: 135.0")
        unit = st.radio("入力単位", ["mg/dL", "mmol/L"], horizontal=True)
        submitted = st.form_submit_button("変換")
        
    if submitted and val is not None:
        mw = MOL_WEIGHTS[ion]
        res_mg = val if unit=="mg/dL" else (val * mw)/10
        res_mmol = (val * 10)/mw if unit=="mg/dL" else val
        st.success(f"{res_mg:.2f} mg/dL  /  {res_mmol:.2f} mmol/L")

def render_export_import():
    st.header("💾 保存・読込")
    st.markdown("現在の入力値をJSONで保存")
    
    export_keys = [
        "gamma_preset", "gamma_mg", "gamma_ml", "gamma_flow", "gamma_wt",
        "ccr_age", "ccr_wt", "ccr_scr", "ccr_sex",
        "ab_ph", "ab_pco2", "ab_hco3", "ab_na", "ab_cl", "ab_alb",
        "renal_una", "renal_pna", "renal_ucr", "renal_pcr", "renal_bun", "renal_uosm"
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

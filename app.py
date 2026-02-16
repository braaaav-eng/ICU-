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
# 閾値をプリセット名と一致するキーで管理する（明示的）
GAMMA_THRESHOLDS = {
    "Norepinephrine (NAD)": {"type":"ug/kg/min", "threshold": 0.3},   # J-SSCG2024 参考値（運用で調整可）
    "Dobutamine (DOB)": {"type":"ug/kg/min", "threshold": 10.0},
    "Dopamine (DOA)": {"type":"ug/kg/min", "threshold": 10.0},
    "Nicardipine": {"type":"ug/kg/min", "threshold": 5.0},
    "Midazolam": {"type":"mg/kg/h", "threshold": 0.2},
    "Propofol": {"type":"mg/kg/h", "threshold": 3.0},
    "Dexmedetomidine": {"type":"ug/kg/h", "threshold": 0.7},  # Dex の閾値は μg/kg/h
    "Nitroglycerin": {"type":"ug/kg/min", "threshold": 5.0},
    "Carperitide": {"type":"ug/kg/min", "threshold": 0.1}
}

# Forrester thresholds
FORRESTER_CI = 2.2
FORRESTER_PCWP = 18.0

# FeNa thresholds
FENA_PRERENAL = 1.0
FENA_ATN = 2.0
FEUREA_PRERENAL = 35.0

# Electrolyte Atomic Weights
MOL_WEIGHTS = {
    "Na": 23.0, "K": 39.1, "Cl": 35.5, 
    "Ca": 40.1, "Mg": 24.3, "P": 31.0
}
VALENCES = {
    "Na": 1, "K": 1, "Cl": 1, 
    "Ca": 2, "Mg": 2, "P": 1 # PO4 usually treated specially, logic handles simplified
}

# Drug Presets (mg, mL)
DRUG_PRESETS = {
    "カスタム": {"mg": 0.0, "ml": 0.0},
    "Norepinephrine (NAD)": {"mg": 5.0, "ml": 50.0},
    "Dobutamine (DOB)": {"mg": 150.0, "ml": 50.0},
    "Dopamine (DOA)": {"mg": 150.0, "ml": 50.0},
    "Nicardipine": {"mg": 50.0, "ml": 50.0},
    "Midazolam": {"mg": 50.0, "ml": 50.0},
    "Propofol": {"mg": 1000.0, "ml": 100.0},
    "Dexmedetomidine": {"mg": 0.2, "ml": 50.0}, # 200mcg
    "Nitroglycerin": {"mg": 50.0, "ml": 100.0},
    "Carperitide": {"mg": 3.0, "ml": 50.0}
}

# ==========================================
# 🩹 Session Initialization & Utils
# ==========================================
if "initialized" not in st.session_state:
    st.session_state.update({
        # γ（文字列で初期化して空欄を許容）
        "gamma_preset": "カスタム",
        "gamma_mg_str": "",     # テキスト入力で空欄開始
        "gamma_ml_str": "",
        "gamma_flow_str": "",
        "gamma_wt_str": "",
        # CCr（同様に空欄）
        "ccr_age_str": "",
        "ccr_weight_str": "",
        "ccr_scr_str": "",
        "ccr_sex": "男性",
        # Acid/base (pHは特別扱い、初期は空)
        "ab_ph_str": "",
        "ab_pco2_str": "",
        "ab_hco3_str": "",
        "ab_na_str": "",
        "ab_cl_str": "",
        "ab_alb_str": "",
        # Draft save name
        "draft": None
    })
    st.session_state["initialized"] = True

def preset_apply_to_session(preset_key):
    """
    preset_key: str key from DRUG_PRESETS
    This writes preset mg/ml defaults into session_state values used by form inputs.
    """
    data = DRUG_PRESETS.get(preset_key, {"mg":0.0, "ml":0.0})
    # Convert to string for text_input, handle 0.0 specially if needed, but here simple str()
    # If the preset has 0.0, we might want to leave it empty or show "0.0". 
    # Usually presets have values.
    st.session_state["gamma_mg_str"] = str(data.get("mg", ""))
    st.session_state["gamma_ml_str"] = str(data.get("ml", ""))

def safe_parse_number(s: str, default=None):
    """
    テキスト入力用の安全パーサー。
    - 空欄 -> None（必須チェックで扱いやすくする）
    - 数字を返す場合は float を返す
    - 小数点桁制御は呼び出し側で round() を行う
    """
    if s is None: 
        return default
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if s == "":
        return None
    try:
        v = float(s.replace(",", ""))  # カンマ対応
        return v
    except:
        return default

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
    .stTextInput input { font-size: 16px !important; }
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

# optional: make text inputs show numeric keyboard on mobile when possible (experimental)
st.markdown("""
<script>
setTimeout(function(){
    // set inputmode for inputs that appear to be numeric placeholders
    document.querySelectorAll('input[type="text"]').forEach(function(inp){
        // heuristic: inputs with placeholder containing digits or specific labels
        if (inp.placeholder && inp.placeholder.match(/[0-9]/)) {
            inp.setAttribute('inputmode','decimal');
            inp.setAttribute('pattern','[0-9]*');
        }
    });
}, 800);
</script>
""", unsafe_allow_html=True)


# ==========================================
# 🧠 Logic Functions
# ==========================================

def calc_gamma(drug_mg, sol_ml, flow, wt=None):
    if drug_mg <= 0 or sol_ml <= 0 or flow <= 0:
        return None
    
    conc = drug_mg / sol_ml
    mg_h = flow * conc
    gamma = None
    
    if wt and wt > 0:
        gamma = (mg_h * 1000) / (wt * 60)
        
    return {
        "conc": conc,
        "mg_h": mg_h,
        "gamma": gamma
    }

def calc_ccr(age, wt, scr, sex):
    if scr <= 0: return None
    ccr = ((140 - age) * wt) / (72 * scr)
    if sex == "女性": ccr *= 0.85
    return ccr

def calc_fena(p_na, u_na, p_cr, u_cr):
    if p_na * u_cr == 0: return None
    return (u_na * p_cr) / (p_na * u_cr) * 100

def calc_feurea(p_urea, u_urea, p_cr, u_cr):
    if p_urea * u_cr == 0: return None
    return (u_urea * p_cr) / (p_urea * u_cr) * 100

# ==========================================
# 📱 Modules
# ==========================================

def render_gamma_module():
    st.header("💉 γ計算 (持続投与)")

    # Preset selector outside form to apply defaults into session_state if user wants
    preset = st.selectbox("薬剤プリセット", list(DRUG_PRESETS.keys()),
                          index=list(DRUG_PRESETS.keys()).index(st.session_state.get("gamma_preset","カスタム")))
    if preset != st.session_state.get("gamma_preset"):
        st.session_state["gamma_preset"] = preset
        preset_apply_to_session(preset)

    with st.form("gamma_form"):
        # Use text_input to allow empty default; show placeholders with typical values
        mg_str = st.text_input("薬剤総量 (mg)", value=st.session_state.get("gamma_mg_str",""), placeholder="例: 5")
        ml_str = st.text_input("溶解総量 (mL)", value=st.session_state.get("gamma_ml_str",""), placeholder="例: 50")
        flow_str = st.text_input("投与速度 (mL/h)", value=st.session_state.get("gamma_flow_str",""), placeholder="例: 3.0")
        use_wt = st.checkbox("体重で換算する", value=(st.session_state.get("gamma_wt_str","")!=""))
        wt_str = ""
        if use_wt:
            wt_str = st.text_input("体重 (kg)", value=st.session_state.get("gamma_wt_str",""), placeholder="例: 50")

        submitted = st.form_submit_button("計算")

    # Save back to session_state (so next open keeps last manual entries)
    if mg_str is not None: st.session_state["gamma_mg_str"] = mg_str
    if ml_str is not None: st.session_state["gamma_ml_str"] = ml_str
    if flow_str is not None: st.session_state["gamma_flow_str"] = flow_str
    if wt_str is not None: st.session_state["gamma_wt_str"] = wt_str

    if submitted:
        # parse
        drug_mg = safe_parse_number(mg_str)
        sol_ml = safe_parse_number(ml_str)
        flow = safe_parse_number(flow_str)
        wt = safe_parse_number(wt_str)

        # validation
        if drug_mg is None or sol_ml is None or flow is None:
            st.error("薬剤量・溶解量・投与速度をすべて入力してください（空欄は不可）。")
            return

        # Round inputs to sensible precision
        drug_mg = round(drug_mg, 1)   # mg は小数1位で十分
        sol_ml = round(sol_ml, 1)     # mL は小数1位
        flow = round(flow, 1)         # mL/h 小数1位

        conc = drug_mg / sol_ml
        mg_h = flow * conc
        gamma = None
        if wt and wt > 0:
            wt = round(wt, 1)  # 体重は小数1位
            gamma = (mg_h * 1000) / (wt * 60)  # μg/kg/min

        # threshold check and display
        cfg = GAMMA_THRESHOLDS.get(preset)
        card = "result-card-green"
        warning = None
        display_secondary = ""

        if gamma is not None and cfg:
            # handle types
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
                mgkg_h = (mg_h / wt) if (wt and wt>0) else None
                if mgkg_h and mgkg_h > cfg["threshold"]:
                    warning = f"注意: {preset} の閾値 {cfg['threshold']} mg/kg/h を超えています"
                    card = "result-card-yellow"
                display_secondary = f"{(mg_h / wt if wt and wt>0 else 0):.3f} mg/kg/h"
        else:
            # no weight -> show mg/h only
            display_secondary = "(体重未入力のため γは未表示) "

        # Show results (keep main display minimal to reduce DOM cost)
        st.markdown(f"""
        <div class="{card}">
            <div class='res-main'>{mg_h:.2f} mg/h</div>
            <div class='res-sub'>{display_secondary}</div>
        </div>
        """, unsafe_allow_html=True)

        if warning:
            st.warning(warning)

        with st.expander("計算根拠（詳細）"):
            st.write(f"濃度: {conc:.4f} mg/mL")
            st.write(f"式 (mg/h) = {flow} mL/h × {conc:.4f} mg/mL")
            if gamma is not None:
                st.write(f"γ = ({mg_h:.4f} mg/h × 1000) / ({wt} kg × 60) = {gamma:.4f} μg/kg/min")


def render_ccr_module():
    st.header("🧪 CCr (Cockcroft-Gault)")

    with st.form("ccr_form"):
        age_str = st.text_input("年齢 (歳)", value=st.session_state.get("ccr_age_str",""), placeholder="例: 65")
        wt_str = st.text_input("体重 (kg)", value=st.session_state.get("ccr_weight_str",""), placeholder="例: 55.0")
        scr_str = st.text_input("Scr (mg/dL)", value=st.session_state.get("ccr_scr_str",""), placeholder="例: 0.9")
        sex = st.radio("性別", ["男性", "女性"], horizontal=True)
        submitted = st.form_submit_button("計算")

    # persist
    st.session_state["ccr_age_str"] = age_str
    st.session_state["ccr_weight_str"] = wt_str
    st.session_state["ccr_scr_str"] = scr_str

    if submitted:
        age = safe_parse_number(age_str)
        wt = safe_parse_number(wt_str)
        scr = safe_parse_number(scr_str)

        if age is None or wt is None or scr is None:
            st.error("年齢・体重・Scr をすべて入力してください。")
            return

        # round sensible precision
        age = int(round(age))
        wt = round(wt, 1)
        scr = round(scr, 2)

        val = calc_ccr(age, wt, scr, sex)
        if val is None:
            st.error("計算できません（Scrは0より大きい値が必要）")
            return

        cat = "正常 (>60)"
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

        with st.expander("計算式"):
            st.write("((140 - Age) * Wt) / (72 * Scr)")
            if sex=="女性": st.write("× 0.85 (女性補正)")


def render_ab_module():
    st.header("⚖️ 酸塩基平衡")
    
    with st.form("ab_form"):
        ph = st.number_input("pH", 6.8, 8.0, 7.40, step=0.01)
        c1, c2 = st.columns(2)
        pco2 = c1.number_input("PaCO2", 10.0, 150.0, 40.0)
        hco3 = c2.number_input("HCO3-", 5.0, 60.0, 24.0)
        c3, c4 = st.columns(2)
        na = c3.number_input("Na", 50.0, 200.0, 140.0)
        cl = c4.number_input("Cl", 50.0, 200.0, 100.0)
        alb = st.number_input("Alb (任意)", 1.0, 6.0, 4.0)
        
        submitted = st.form_submit_button("判定", type="primary", use_container_width=True)
        
    if submitted:
        try:
            # AG
            ag = na - (cl + hco3)
            ag_corr = ag + 2.5 * (4.0 - alb)
            
            # Primary
            if ph < 7.35: state = "アシデミア"
            elif ph > 7.45: state = "アルカレミア"
            else: state = "pH正常範囲"
            
            # Gap logic
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

            # Winter's Formula Check
            if hco3 < 24 and ph < 7.40:
                exp_pco2 = 1.5 * hco3 + 8
                detail.append(f"予測PaCO2: {exp_pco2:.1f}±2")
                if pco2 > exp_pco2 + 2: detail.append("呼吸性代償不全 (Resp Acidosis)")
                elif pco2 < exp_pco2 - 2: detail.append("過代償 (Resp Alkalosis)")
                
            # Display
            col = "result-card-yellow" if "アシデミア" in state or is_high_ag else "result-card-green"
            st.markdown(f"""
            <div class="{col}">
                <div class="res-main">{state}</div>
                <div class="res-sub">AG(補正): {ag_corr:.1f}</div>
            </div>
            """, unsafe_allow_html=True)
            
            for d in detail: st.info(d)
        except Exception as e:
            st.error(f"Error: {e}")


def render_shock_module():
    st.header("🚨 ショック評価")

    with st.form("shock_form"):
        sbp = st.number_input("SBP (mmHg)", 0, 300, 80)
        dbp = st.number_input("DBP (mmHg)", 0, 200, 50)
        hr = st.number_input("HR (bpm)", 0, 300, 110)
        lactate = st.number_input("乳酸 (mmol/L)", 0.0, 20.0, 3.0)
        skin = st.selectbox("皮膚所見", ["Cold", "Warm"])
        infection = st.checkbox("感染兆候あり")
        bleeding = st.checkbox("出血/外傷あり")
        jvd = st.checkbox("頸静脈怒張")
        submitted = st.form_submit_button("評価")

    if submitted:
        try:
            map_val = (sbp + 2*dbp) / 3.0
            shock_flag = map_val < 65 or sbp < 90
            lactate_flag = lactate >= 2.0

            possibilities = []
            actions = []

            if shock_flag and lactate_flag and (infection or skin=="Warm"):
                possibilities.append("敗血症性ショック (Distributive)")
                actions.append("輸液評価 → ノルアドレナリン (NAD) を検討")
            if bleeding:
                possibilities.append("出血性ショック (Hypovolemic)")
                actions.append("止血/輸血/急速輸液を優先")
            if jvd and skin=="Cold":
                possibilities.append("閉塞性/心原性ショックの疑い")
                actions.append("緊急心エコー/心タンポナーデ等を除外")

            if not possibilities:
                possibilities.append("原因不明: 詳細評価（画像/血液/出血点）を推奨")

            severity = "中"
            if shock_flag and lactate_flag:
                severity = "高"

            st.markdown(f"""<div class='result-card-red'>
                <div class='res-main'>ショック可能性: {severity}</div>
                <div class='res-sub'>疑い: {', '.join(possibilities)}</div>
                </div>""", unsafe_allow_html=True)

            st.info(f"MAP: {map_val:.1f} mmHg | Lactate: {lactate:.2f} mmol/L")
            st.write("推奨アクション: " + (" → ".join(actions) if actions else "観察/追加検査"))
        except Exception as e:
            st.error(f"評価エラー: {str(e)}")


def render_hf_module():
    st.header("🫀 心不全 (Forrester)")
    
    with st.form("hf_form"):
        c1, c2 = st.columns(2)
        co = c1.number_input("心拍出量 CO (L/min)", 0.0, 15.0, 4.0, step=0.1)
        bsa = c2.number_input("体表面積 BSA (m2)", 0.0, 3.0, 1.6, step=0.1)
        
        pcwp = st.number_input("PCWP (mmHg)", 0, 50, 20, step=1)
        
        scenario = st.selectbox("CS (クリニカルシナリオ)", 
            ["CS1 (BP高値)", "CS2 (浮腫)", "CS3 (低灌流)", "CS4 (ACS)", "CS5 (右心不全)"])
        
        submitted = st.form_submit_button("分類")
        
    if submitted:
        try:
            if bsa <= 0:
                st.error("BSAは0より大きい値を入力してください")
            else:
                ci = co / bsa
                is_wet = pcwp >= FORRESTER_PCWP
                is_cold = ci < FORRESTER_CI
                
                subset = "I (Warm/Dry)"
                rx = "経過観察"
                col = "result-card-green"
                
                if is_wet and not is_cold:
                    subset = "II (Warm/Wet)"
                    rx = "血管拡張薬 + 利尿薬"
                    col = "result-card-yellow"
                elif not is_wet and is_cold:
                    subset = "III (Cold/Dry)"
                    rx = "輸液負荷 (Volume Check) + 強心薬"
                    col = "result-card-yellow"
                elif is_wet and is_cold:
                    subset = "IV (Cold/Wet)"
                    rx = "強心薬 + 昇圧薬 + 補助循環"
                    col = "result-card-red"
                    
                st.markdown(f"""
                <div class="{col}">
                    <div class="res-main">Subset {subset}</div>
                    <div class="res-sub">推奨: {rx}</div>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("ヘモダイナミクス評価"):
                    st.write(f"CI: {ci:.2f} (閾値 {FORRESTER_CI}) -> {'Cold' if is_cold else 'Warm'}")
                    st.write(f"PCWP: {pcwp} (閾値 {FORRESTER_PCWP}) -> {'Wet' if is_wet else 'Dry'}")
                    st.write(f"CS: {scenario}")
        except Exception as e:
            st.error(f"Error: {e}")


def render_renal_diff():
    st.header("💧 腎障害鑑別 (FeNa/FeUrea)")
    
    with st.form("renal_form"):
        c1, c2 = st.columns(2)
        u_na = c1.number_input("尿中Na", 0.0, 300.0, 20.0)
        p_na = c2.number_input("血清Na", 0.0, 200.0, 140.0)
        c3, c4 = st.columns(2)
        u_cr = c3.number_input("尿中Cr", 0.0, 500.0, 100.0)
        p_cr = c4.number_input("血清Cr", 0.0, 20.0, 1.0)
        
        do_urea = st.checkbox("FeUreaも計算 (利尿薬使用時)")
        u_urea = 0.0
        p_urea = 0.0
        if do_urea:
            c5, c6 = st.columns(2)
            u_urea = c5.number_input("尿中Urea (BUN)", 0.0)
            p_urea = c6.number_input("血清Urea (BUN)", 0.0)
            
        submitted = st.form_submit_button("計算")
    
    if submitted:
        try:
            fena = calc_fena(p_na, u_na, p_cr, u_cr)
            
            if fena is not None:
                state = "腎性 (ATN等)"
                if fena < FENA_PRERENAL: state = "腎前性 (脱水/心不全)"
                elif fena > FENA_ATN: state = "腎性 (ATN確定?)"
                
                st.markdown(f"**FeNa: {fena:.2f} %** → {state}")
                st.caption(f"閾値: <1% 腎前性, >2% 腎性")
            
            if do_urea:
                feurea = calc_feurea(p_urea, u_urea, p_cr, u_cr)
                if feurea is not None:
                    state_u = "腎性"
                    if feurea < FEUREA_PRERENAL: state_u = "腎前性 (利尿薬影響下)"
                    st.markdown(f"**FeUrea: {feurea:.2f} %** → {state_u}")
        except Exception as e:
            st.error(f"Error: {e}")


def render_calc_tools():
    st.header("⚗️ 電解質・単位変換")
    
    with st.form("calc_form"):
        ion = st.selectbox("対象", ["Na", "K", "Cl", "Ca", "Mg", "P"])
        val = st.number_input("値", 0.0, step=0.1, format="%.2f")
        unit = st.radio("入力単位", ["mg/dL", "mmol/L (mEq/L)"], horizontal=True)
        
        submitted = st.form_submit_button("変換")
        
    if submitted:
        try:
            mw = MOL_WEIGHTS[ion]
            valence = VALENCES[ion]
            
            res_mg = 0.0
            res_mmol = 0.0
            
            if unit == "mg/dL":
                # mg/dL -> mmol/L = (mg/dL * 10) / MW
                res_mg = val
                res_mmol = (val * 10) / mw
            else:
                # mmol/L -> mg/dL = (mmol/L * MW) / 10
                res_mmol = val
                res_mg = (val * mw) / 10
                
            res_meq = res_mmol * valence
            
            st.success(f"{ion} 変換結果")
            st.write(f"**{res_mg:.2f} mg/dL**")
            st.write(f"**{res_mmol:.2f} mmol/L**")
            st.write(f"**{res_meq:.2f} mEq/L**")
        except Exception as e:
            st.error(f"Error: {e}")

def render_na_diff():
    st.header("🧂 低Na血症鑑別")
    st.write("フローチャートガイド (Step by Step)")
    
    step = st.selectbox("現在のステップ", 
        ["1. 血漿浸透圧 (Posm)", "2. 尿浸透圧 (Uosm)", "3. 体液量 (Volume)"])
    
    if step.startswith("1"):
        st.info("Posm < 275 assuming hypotonic?")
        st.write("- 正常/高値 (280-295): 偽性低Na, 高血糖, Mannitol")
        st.write("- 低値 (<275): 真の低Na血症 → Step 2へ")
        
    elif step.startswith("2"):
        st.info("Uosm check")
        st.write("- Uosm < 100: 水中毒, 多飲, ビール排泄")
        st.write("- Uosm > 100: ADH分泌あり → Step 3へ")
        
    elif step.startswith("3"):
        st.info("体液量評価")
        st.write("- Hypovolemic (脱水): 尿Na<20=腎外性喪失, 尿Na>20=腎性喪失(利尿薬/CSW)")
        st.write("- Euvolemic (正常): SIADH, 甲状腺低下, 副腎不全")
        st.write("- Hypervolemic (浮腫): 心不全, 肝硬変, ネフローゼ")

def render_export_import():
    st.header("💾 データ保存・読込")
    
    st.markdown("現在の入力内容を JSON ファイルとして保存、または復元できます。")
    
    # Export
    # Dump session state to json
    # Filter only relevant keys to avoid internal Streamlit clutter
    export_keys = [
        "gamma_preset", "gamma_mg_str", "gamma_ml_str", "gamma_flow_str", "gamma_wt_str",
        "ccr_age_str", "ccr_weight_str", "ccr_scr_str", "ccr_sex",
        "ab_ph_str", "ab_pco2_str", "ab_hco3_str", "ab_na_str", "ab_cl_str", "ab_alb_str"
    ]
    data = {k: st.session_state.get(k) for k in export_keys}
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    
    st.download_button(
        label="📥 下書きを保存 (JSON)",
        data=json_str,
        file_name="icu_tool_draft.json",
        mime="application/json"
    )
    
    # Import
    uploaded = st.file_uploader("📤 下書きを読込", type=["json"])
    if uploaded is not None:
        try:
            loaded_data = json.load(uploaded)
            # Update session state
            for k, v in loaded_data.items():
                if k in export_keys:
                    st.session_state[k] = v
                    # Special handling if needed (e.g. preset sync)
                    if k == "gamma_preset":
                        preset_apply_to_session(v)
            
            st.success("データを復元しました。各モジュールで確認してください。")
        except Exception as e:
            st.error(f"読込エラー: {str(e)}")


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

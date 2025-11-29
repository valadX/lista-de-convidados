import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import requests
import os
import plotly.express as px
import pytz
import time
import re
import concurrent.futures # Para rodar em segundo plano

# ==========================================
# CONFIGURAÇÃO INICIAL
# ==========================================
st.set_page_config(page_title="Controle de Buffet", page_icon="🟣", layout="wide")

# Configurações Globais
LOGO_URL = "https://lanbele.com.br/wp-content/uploads/2025/09/IMG-20250920-WA0029-1024x585.png"
LOGO_PATH = "logo_cache.png"
SENHA_ADMIN = "1234"
SHEET_NAME = "Controle_Buffet"

# Imports Condicionais (Google Sheets)
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

# ==========================================
# 1. UTILITÁRIOS E CSS
# ==========================================

def get_brazil_time():
    return datetime.now(pytz.timezone('America/Sao_Paulo'))

@st.cache_resource
def download_logo():
    if not os.path.exists(LOGO_PATH):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(LOGO_URL, headers=headers, timeout=5)
            if response.status_code == 200:
                with open(LOGO_PATH, "wb") as f: f.write(response.content)
        except: pass

@st.cache_resource
def get_thread_executor():
    """Cria um executor para salvar em segundo plano sem travar a tela"""
    return concurrent.futures.ThreadPoolExecutor(max_workers=4)

st.markdown("""
    <style>
    .stApp { background-color: #2e003e; color: white; }
    
    input, .stNumberInput input { 
        color: #000000 !important; 
        font-weight: bold; 
        background-color: #ffffff !important;
    }
    div[data-baseweb="input"] {
        background-color: #ffffff !important;
        border-radius: 8px;
    }

    .metric-card {
        padding: 15px; border-radius: 12px; text-align: center;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.3); margin-bottom: 10px;
        border: 1px solid rgba(255,255,255,0.1); color: white;
    }
    .card-purple { background: linear-gradient(135deg, #6a1b9a, #4a148c); }
    .card-green { background: linear-gradient(135deg, #43a047, #2e7d32); }
    .card-orange { background: linear-gradient(135deg, #fb8c00, #ef6c00); }
    
    .big-number { font-size: 2.8em; font-weight: bold; margin: 0; text-shadow: 1px 1px 3px rgba(0,0,0,0.5); }
    .label { font-size: 0.9em; font-weight: 500; text-transform: uppercase; opacity: 0.9; }
    
    div.stButton > button { 
        width: 100%; border-radius: 8px; height: 3em; font-weight: bold; border: none;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONEXÃO OTIMIZADA (CACHEADA)
# ==========================================

@st.cache_resource(ttl=3600) # Mantém a conexão viva por 1 hora
def get_cached_sheet_object():
    """Conecta no Google APENAS UMA VEZ e guarda na memória"""
    if not HAS_GSHEETS: return None
    
    creds_dict = None
    if "gcp_service_account" in st.secrets: creds_dict = dict(st.secrets["gcp_service_account"])
    elif "gsheets" in st.secrets: creds_dict = dict(st.secrets["gsheets"])
    if not creds_dict: return None

    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception: return None

def check_and_init_headers():
    sheet = get_cached_sheet_object()
    if not sheet: return
    try:
        # Verifica se está vazio
        if not sheet.row_values(1):
            sheet.append_row(["id", "Nome", "Tipo", "Idade", "Status", "Hora", "Data", "Evento"])
    except: pass

def get_active_parties_today():
    sheet = get_cached_sheet_object()
    if not sheet: return []
    try:
        data = sheet.get_all_records()
        today = get_brazil_time().strftime("%d/%m/%Y")
        return list({str(r.get('Evento','')).strip() for r in data if str(r.get('Data','')).strip() == today and str(r.get('Evento','')).strip()})
    except: return []

def load_data_from_sheets(target_event):
    sheet = get_cached_sheet_object()
    if not sheet: return [], 100
    try:
        data = sheet.get_all_records()
        cleaned = []
        today = get_brazil_time().strftime("%d/%m/%Y")
        target = str(target_event).strip().lower()
        limit = 100 

        for row in data:
            evt = str(row.get('Evento', '')).strip().lower()
            dt = str(row.get('Data', '')).strip()
            
            if evt == target and dt == today:
                if str(row.get('Status')) == "SYSTEM_START":
                    try: limit = int(row.get('Idade', 100))
                    except: pass
                    continue

                cleaned.append({
                    'id': str(row.get('id') or row.get('ID') or ''),
                    'Nome': row.get('Nome', ''),
                    'Tipo': row.get('Tipo', 'Adulto'),
                    'Idade': row.get('Idade', '-'),
                    'Status': row.get('Status', 'Pagante'),
                    'Hora': row.get('Hora', '--:--'),
                    'Data': dt,
                    'Evento': row.get('Evento', ''),
                    '_is_paying': True if row.get('Status') == 'Pagante' else False
                })
        return cleaned[::-1], limit
    except: return [], 100

# FUNÇÃO DE SALVAMENTO ASSÍNCRONA
def _save_row_bg(row_data):
    """Função interna que roda na thread separada"""
    sheet = get_cached_sheet_object()
    if not sheet: return
    try:
        sheet.append_row([
            str(row_data.get('id')), row_data.get('Nome'), row_data.get('Tipo'),
            str(row_data.get('Idade')), row_data.get('Status'), row_data.get('Hora'),
            row_data.get('Data'), row_data.get('Evento')
        ])
    except: pass

def save_row(row_data):
    """Dispara o salvamento e libera a tela IMEDIATAMENTE"""
    executor = get_thread_executor()
    executor.submit(_save_row_bg, row_data)
    return True # Retorna True imediatamente, confiando na thread

def delete_row(guest_id):
    sheet = get_cached_sheet_object()
    if not sheet: return False
    try:
        cell = sheet.find(str(guest_id))
        if cell: 
            sheet.delete_rows(cell.row)
            return True
    except: pass
    return False

# ==========================================
# 3. SMART PARSER
# ==========================================

def parse_input_text(text):
    text = text.strip()
    if not text: return None
    lower_text = text.lower()
    
    keywords = ['mãe', 'mae', 'pai', 'irmao', 'irmão', 'irma', 'irmã', 'fotografo', 'fotógrafo', 'staff', 'baba', 'babá', 'avó', 'avô', 'cortesia']
    words = lower_text.replace(',', ' ').replace('-', ' ').split()
    
    if any(k in words for k in keywords):
        return {"Nome": text.title(), "Tipo": "Cortesia", "Idade": "-", "Status": "Cortesia", "_is_paying": False}

    match = re.search(r'(\d+)', text)
    if match:
        age = int(match.group(1))
        clean_name = re.sub(r'\d+\s*(anos|ano|a)?', '', text, flags=re.IGNORECASE).strip()
        if not clean_name: clean_name = "Criança"
        status = "Isento" if age <= 7 else "Pagante"
        is_paying = (age > 7)
        return {"Nome": clean_name.title(), "Tipo": "Criança", "Idade": f"{age} anos", "Status": status, "_is_paying": is_paying}

    return {"Nome": text.title(), "Tipo": "Adulto", "Idade": "-", "Status": "Pagante", "_is_paying": True}

# ==========================================
# 4. PDF
# ==========================================
@st.cache_data(show_spinner=False)
def generate_pdf(party_name, guests_df, p_counts, guest_limit):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists(LOGO_PATH):
        try: pdf.image(LOGO_PATH, x=10, y=10, w=40)
        except: pass

    pdf.set_font("Helvetica", 'B', 16)
    pdf.set_xy(55, 15)
    pdf.set_text_color(106, 27, 154)
    pdf.cell(0, 10, txt=f"Relatório Final: {party_name}", ln=True)
    
    pdf.set_xy(55, 23)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(50, 50, 50)
    now_str = get_brazil_time().strftime('%d/%m/%Y %H:%M')
    pdf.cell(0, 10, txt=f"Gerado em: {now_str}", ln=True)
    pdf.ln(20)
    
    pdf.set_fill_color(106, 27, 154); pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 12); pdf.cell(0, 10, "  Resumo", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", size=12); pdf.ln(2)
    
    pdf.cell(0, 8, f"Limite Contratado: {guest_limit}", ln=True)
    pdf.cell(0, 8, f"Total Presente: {p_counts['total']}", ln=True)
    pdf.ln(2)
    pdf.cell(0, 8, f"Pagantes: {p_counts['paying']}", ln=True)
    pdf.cell(0, 8, f"Isentos (<=7): {p_counts['free']}", ln=True)
    pdf.cell(0, 8, f"Cortesias: {p_counts['cortesia']}", ln=True)
    pdf.ln(10)
    
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_fill_color(106, 27, 154); pdf.set_text_color(255, 255, 255)
    pdf.cell(80, 8, "Nome", 1, 0, 'L', 1); pdf.cell(30, 8, "Tipo", 1, 0, 'C', 1)
    pdf.cell(30, 8, "Idade", 1, 0, 'C', 1); pdf.cell(30, 8, "Status", 1, 0, 'C', 1)
    pdf.cell(20, 8, "Hora", 1, 1, 'C', 1)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", size=10)
    
    fill = False
    for index, row in guests_df.iterrows():
        if fill: pdf.set_fill_color(240, 240, 245)
        else: pdf.set_fill_color(255, 255, 255)
        try:
            vals = [str(row.get(c,'-')).encode('latin-1', 'replace').decode('latin-1') for c in ['Nome', 'Tipo', 'Idade', 'Status', 'Hora']]
        except: vals = ["-"] * 5
        pdf.cell(80, 8, vals[0], 1, 0, 'L', fill); pdf.cell(30, 8, vals[1], 1, 0, 'C', fill)
        pdf.cell(30, 8, vals[2], 1, 0, 'C', fill); pdf.cell(30, 8, vals[3], 1, 0, 'C', fill)
        pdf.cell(20, 8, vals[4], 1, 1, 'C', fill)
        fill = not fill
        
    try: return bytes(pdf.output())
    except: return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 5. LÓGICA DE APLICAÇÃO
# ==========================================

download_logo()
if HAS_GSHEETS: check_and_init_headers()

defaults = {'active': False, 'name': '', 'limit': 100, 'guests': [], 'last_time': None}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

def sync_data():
    if st.session_state.active and HAS_GSHEETS:
        with st.spinner("Sincronizando..."):
            guests, limit = load_data_from_sheets(st.session_state.name)
            st.session_state.guests = guests
            st.session_state.limit = limit

def handle_add_guest_smart():
    raw_text = st.session_state.smart_input
    if not raw_text: return
    
    parsed = parse_input_text(raw_text)
    if not parsed: return

    # Anti-duplicação (3s é suficiente para evitar duplo clique)
    if st.session_state.guests and st.session_state.last_time:
        last = st.session_state.guests[0]
        if last['Nome'] == parsed['Nome'] and (datetime.now() - st.session_state.last_time).total_seconds() < 3:
            st.toast(f"⚠️ {parsed['Nome']} duplicado evitado!")
            st.session_state.smart_input = ""
            return

    new_guest = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "Nome": parsed['Nome'], "Tipo": parsed['Tipo'], 
        "Idade": parsed['Idade'], "Status": parsed['Status'],
        "Hora": get_brazil_time().strftime("%H:%M"), "Data": get_brazil_time().strftime("%d/%m/%Y"),
        "Evento": st.session_state.name, "_is_paying": parsed['_is_paying']
    }
    
    # 1. ATUALIZA A TELA IMEDIATAMENTE (MUITO RÁPIDO)
    st.session_state.guests.insert(0, new_guest)
    st.session_state.last_time = datetime.now()
    st.session_state.smart_input = "" 
    st.toast(f"✅ {parsed['Nome']} ({parsed['Tipo']})")
    
    # 2. MANDA PARA A NUVEM EM SEGUNDO PLANO (SEM TRAVAR)
    if HAS_GSHEETS: 
        save_row(new_guest) # Agora roda em thread

# ==========================================
# 6. INTERFACE
# ==========================================

with st.sidebar:
    status_color = "🟢" if get_cached_sheet_object() else "🔴"
    st.caption(f"{status_color} Conexão: {'Online' if '🟢' in status_color else 'Offline'}")

    if not st.session_state.active:
        st.header("🎉 Iniciar / Entrar")
        if st.button("🔄 Buscar Festas Hoje"): st.rerun()
        active = get_active_parties_today()
        
        if active:
            sel = st.selectbox("Festas encontradas:", active)
            if st.button("👉 Entrar na Festa"):
                st.session_state.name = sel
                st.session_state.active = True
                sync_data()
                st.rerun()
        else:
            st.info("Nenhuma festa encontrada.")
            
        st.markdown("---")
        new_name = st.text_input("Nome do Evento", placeholder="Ex: Maria 15 Anos")
        new_limit = st.number_input("Limite Contrato", min_value=0, value=100, step=1)
        
        if st.button("🚀 Criar Nova"):
            if not new_name: st.error("Nome obrigatório!")
            elif not get_cached_sheet_object(): st.error("Sem conexão!")
            else:
                marker = {
                    "id": "SYSTEM", "Nome": "--- START ---", "Tipo": "System",
                    "Idade": str(new_limit), "Status": "SYSTEM_START",
                    "Hora": get_brazil_time().strftime("%H:%M"), "Data": get_brazil_time().strftime("%d/%m/%Y"),
                    "Evento": new_name.strip()
                }
                save_row(marker)
                st.session_state.name = new_name
                st.session_state.limit = new_limit
                st.session_state.active = True
                st.session_state.guests = []
                st.rerun()
    else:
        st.header(f"🎈 {st.session_state.name}")
        st.markdown("### 📂 Relatórios")
        df = pd.DataFrame(st.session_state.guests)
        
        c_counts = {'total': 0, 'paying': 0, 'free': 0, 'cortesia': 0}
        if not df.empty:
            c_counts['total'] = len(df)
            c_counts['paying'] = df[df['_is_paying'] == True].shape[0]
            c_counts['cortesia'] = df[df['Tipo'] == 'Cortesia'].shape[0]
            c_counts['free'] = df[df['_is_paying'] == False].shape[0] - c_counts['cortesia']
            
            cols_drop = ['_is_paying', 'id']
            pdf_data = generate_pdf(st.session_state.name, df.drop(columns=[c for c in cols_drop if c in df.columns], errors='ignore'), c_counts, st.session_state.limit)
            
            st.download_button("📄 Baixar PDF", pdf_data, "Relatorio.pdf", "application/pdf", use_container_width=True)
            msg = f"Relatório {st.session_state.name}: {c_counts['paying']} Pagantes. Total: {c_counts['total']}/{st.session_state.limit}"
            st.link_button("📱 Enviar Zap", f"https://api.whatsapp.com/send?text={msg}", use_container_width=True)
        else: st.info("Sem dados.")

        st.divider()
        if st.button("🔄 Sincronizar"): sync_data()
        
        with st.expander("🗑️ Excluir (Senha)"):
            if st.session_state.guests:
                opts = {f"{g['Nome']} ({g['Hora']})": g['id'] for g in st.session_state.guests}
                sel_del = st.selectbox("Selecione:", list(opts.keys()))
                pwd = st.text_input("Senha", type="password")
                if st.button("Confirmar Exclusão"):
                    if pwd == SENHA_ADMIN:
                        delete_row(opts[sel_del])
                        st.session_state.guests = [g for g in st.session_state.guests if g['id'] != opts[sel_del]]
                        st.success("Deletado!")
                        st.rerun()
                    else: st.error("Senha errada")
        
        st.divider()
        if st.button("🔴 Sair / Encerrar"):
            for k in ['active', 'name', 'guests']: st.session_state[k] = defaults[k]
            st.rerun()

c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)

if st.session_state.active:
    df = pd.DataFrame(st.session_state.guests)
    counts = {'total': 0, 'paying': 0, 'free': 0, 'cortesia': 0}
    if not df.empty:
        counts['total'] = len(df)
        counts['paying'] = df[df['_is_paying'] == True].shape[0]
        counts['cortesia'] = df[df['Tipo'] == 'Cortesia'].shape[0]
        counts['free'] = df[df['_is_paying'] == False].shape[0] - counts['cortesia']

    st.markdown(f"<h2 style='text-align: center;'>{st.session_state.name}</h2>", unsafe_allow_html=True)
    
    limit_val = st.session_state.limit if st.session_state.limit > 0 else 1
    pct = min(counts['paying'] / limit_val, 1.0)
    st.write(f"**Contrato (Pagantes):** {counts['paying']} / {st.session_state.limit}")
    st.progress(pct)
    if counts['paying'] >= st.session_state.limit: st.error("⚠️ LIMITE ATINGIDO!")

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card card-purple'><div class='label'>Pagantes</div><div class='big-number'>{counts['paying']}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card card-green'><div class='label'>Isentos (≤7)</div><div class='big-number'>{counts['free']}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card card-orange'><div class='label'>Total na Casa</div><div class='big-number'>{counts['total']}</div></div>", unsafe_allow_html=True)
    st.write("")

    tab1, tab2 = st.tabs(["📍 Registro Inteligente", "📊 Gráficos (Admin)"])
    
    with tab1:
        with st.container(border=True):
            st.subheader("Digite Nome ou Comando")
            st.caption("Ex: 'Carlos' (Adulto), 'Helena 6' (Criança 6), 'Maria Mãe' (Cortesia)")
            
            st.text_input("", placeholder="Digite aqui e aperte Enter...", key="smart_input", on_change=handle_add_guest_smart)
            
            st.write("")
            if st.session_state.guests:
                if st.button("↩️ Desfazer Último"):
                    last = st.session_state.guests.pop(0)
                    if HAS_GSHEETS: delete_row(last['id'])
                    st.rerun()
                
                st.markdown("---")
                st.write("📝 **Últimos 5 Registros:**")
                recent_df = pd.DataFrame(st.session_state.guests[:5])
                if not recent_df.empty:
                    st.dataframe(
                        recent_df[['Nome', 'Tipo', 'Idade', 'Status', 'Hora']], 
                        use_container_width=True, 
                        hide_index=True
                    )

    with st.expander("🛠️ Opções Manuais (Caso a inteligência erre)"):
        st.text_input("Nome Manual", key="temp_name")
        c1, c2 = st.columns(2)
        with c1: st.radio("Tipo", ["Adulto", "Criança", "Cortesia"], horizontal=True, key="temp_type")
        with c2: st.number_input("Idade", 0, 18, 1, key="temp_age")
        
        def handle_manual():
            st.session_state.smart_input = f"{st.session_state.temp_name} {st.session_state.temp_age if st.session_state.temp_type == 'Criança' else ''} {st.session_state.temp_type if st.session_state.temp_type == 'Cortesia' else ''}"
            handle_add_guest_smart()
            
        st.button("Adicionar Manualmente", on_click=handle_manual)

    with st.expander("📊 Gráficos (Admin)"):
        pwd = st.text_input("Senha Admin", type="password", key="report_pass")
        if pwd == SENHA_ADMIN:
            if not df.empty:
                if 'Hora' in df.columns:
                    try:
                        df['dt'] = pd.to_datetime(df['Hora'], format='%H:%M').apply(lambda x: x.replace(year=2024))
                        df['15min'] = df['dt'].dt.floor('15T')
                        counts_time = df['15min'].value_counts().sort_index().reset_index()
                        counts_time.columns = ['Horário', 'Chegadas']
                        counts_time['Horário'] = counts_time['Horário'].dt.strftime('%H:%M')
                        st.plotly_chart(px.bar(counts_time, x='Horário', y='Chegadas', text='Chegadas'), use_container_width=True)
                    except: pass
                
                st.dataframe(df.drop(columns=['_is_paying', 'id'], errors='ignore'), use_container_width=True, hide_index=True)
            else: st.info("Sem dados.")
        elif pwd: st.error("Senha errada")

else:
    st.info("👈 Comece pela barra lateral.")
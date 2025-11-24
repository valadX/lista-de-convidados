import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import requests
import os
import plotly.express as px

# --- TENTATIVA DE IMPORTAR BIBLIOTECAS DO GOOGLE ---
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

# --- CONFIGURAÇÕES GERAIS ---
LOGO_URL = "https://lanbele.com.br/wp-content/uploads/2025/09/IMG-20250920-WA0029-1024x585.png"
LOGO_PATH = "logo_cache.png"
SENHA_ADMIN = "140206"
SHEET_NAME = "Controle_Buffet" 

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Controle de Buffet", page_icon="🟣", layout="wide")

# ==========================================
# 1. FUNÇÕES DE BANCO DE DADOS (GOOGLE SHEETS)
# ==========================================

def get_db_connection():
    """Conecta ao Google Sheets"""
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
    except Exception as e:
        st.error(f"Erro na conexão com o Google: {e}")
        return None

def load_data_from_sheets():
    """Carrega dados e LIMPA colunas perigosas"""
    sheet = get_db_connection()
    if sheet:
        try:
            data = sheet.get_all_records()
            cleaned_data = []
            
            for row in data:
                # --- LIMPEZA CRÍTICA PARA EVITAR OVERFLOW ---
                raw_id = row.get('id') or row.get('ID') or ''
                safe_id = str(raw_id)
                
                clean_row = {
                    'id': safe_id,
                    'Nome': row.get('Nome', ''),
                    'Tipo': row.get('Tipo', 'Adulto'),
                    'Idade': row.get('Idade', '-'),
                    'Status': row.get('Status', 'Pagante'),
                    'Hora': row.get('Hora', '--:--')
                }
                
                clean_row['_is_paying'] = True if clean_row['Status'] == 'Pagante' else False
                cleaned_data.append(clean_row)
                
            return cleaned_data[::-1]
        except Exception as e:
            return []
    return []

def save_guest_to_sheets(guest_dict):
    """Salva linha"""
    sheet = get_db_connection()
    if sheet:
        try:
            row = [
                str(guest_dict['id']),
                guest_dict['Nome'],
                guest_dict['Tipo'],
                guest_dict['Idade'],
                guest_dict['Status'],
                guest_dict['Hora'],
                datetime.now().strftime("%d/%m/%Y")
            ]
            sheet.append_row(row)
        except:
            pass

def delete_guest_from_sheets(guest_id):
    """Deleta linha"""
    sheet = get_db_connection()
    if sheet:
        try:
            cell = sheet.find(str(guest_id))
            if cell:
                sheet.delete_rows(cell.row)
        except:
            pass

# ==========================================
# 2. FUNÇÕES VISUAIS E UTILITÁRIOS
# ==========================================

@st.cache_resource
def download_logo():
    if not os.path.exists(LOGO_PATH):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(LOGO_URL, headers=headers, timeout=5)
            if response.status_code == 200:
                with open(LOGO_PATH, "wb") as f:
                    f.write(response.content)
                return True
        except:
            return False
    return True

@st.cache_data(show_spinner=False)
def generate_pdf_report_v6(party_name, guests_df, total_paying, total_free, total_cortesia, total_guests, guest_limit):
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists(LOGO_PATH):
        try: pdf.image(LOGO_PATH, x=10, y=10, w=40)
        except: pass

    pdf.set_font("Helvetica", 'B', 16)
    pdf.set_xy(55, 15)
    pdf.set_text_color(106, 27, 154)
    pdf.cell(0, 10, txt=f"Relatório: {party_name}", ln=True, align='L')
    pdf.set_xy(55, 23)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='L')
    pdf.ln(20)
    
    pdf.set_fill_color(106, 27, 154); pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 12); pdf.cell(0, 10, "  Resumo de Público", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", size=12); pdf.ln(2)
    
    pdf.cell(0, 8, f"Limite do Contrato: {guest_limit} pessoas", ln=True)
    pdf.cell(0, 8, f"Total Geral Presente: {total_guests}", ln=True)
    pdf.ln(2)
    pdf.cell(0, 8, f"Total Pagantes (Contrato): {total_paying}", ln=True)
    pdf.cell(0, 8, f"Crianças Isentas (<= 7 anos): {total_free}", ln=True)
    pdf.cell(0, 8, f"Cortesias (Família/Staff): {total_cortesia}", ln=True)
    
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
            r_nome = str(row.get('Nome', '-'))
            r_tipo = str(row.get('Tipo', '-'))
            r_status = str(row.get('Status', '-'))
            r_idade = str(row.get('Idade', '-'))
            r_hora = str(row.get('Hora', '-'))

            nome = r_nome.encode('latin-1', 'replace').decode('latin-1')
            tipo = r_tipo.encode('latin-1', 'replace').decode('latin-1')
            status = r_status.encode('latin-1', 'replace').decode('latin-1')
        except:
            nome = str(row.get('Nome', '-'))
            tipo = str(row.get('Tipo', '-'))
            status = str(row.get('Status', '-'))

        pdf.cell(80, 8, nome, 1, 0, 'L', fill); pdf.cell(30, 8, tipo, 1, 0, 'C', fill)
        pdf.cell(30, 8, str(r_idade), 1, 0, 'C', fill); pdf.cell(30, 8, status, 1, 0, 'C', fill)
        pdf.cell(20, 8, str(r_hora), 1, 1, 'C', fill)
        fill = not fill
        
    try:
        raw = pdf.output()
        if isinstance(raw, str): return raw.encode('latin-1')
        return bytes(raw)
    except:
        return pdf.output(dest='S').encode('latin-1')

# --- CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #2e003e; color: white; }
    input, .stNumberInput input { color: white !important; font-weight: bold; }
    div[data-baseweb="base-input"], div[data-baseweb="input"] {
        background-color: rgba(255, 255, 255, 0.15) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px;
    }
    label, .stMarkdown, p, h1, h2, h3, li, span { color: white !important; }
    header[data-testid="stHeader"] { background-color: #2e003e; }
    .metric-card {
        padding: 15px; border-radius: 12px; text-align: center;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.3); margin-bottom: 10px;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .card-purple { background: linear-gradient(135deg, #6a1b9a, #4a148c); }
    .card-green { background: linear-gradient(135deg, #43a047, #2e7d32); }
    .card-orange { background: linear-gradient(135deg, #fb8c00, #ef6c00); }
    .big-number { font-size: 2.5em; font-weight: bold; margin: 0; text-shadow: 1px 1px 2px black; }
    .label { font-size: 0.9em; font-weight: 500; text-transform: uppercase; opacity: 0.9; }
    div.stButton > button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; border: none; }
    section[data-testid="stSidebar"] { background-color: #1a0024; border-right: 1px solid #4a148c; }
    /* Abas */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; background-color: rgba(255,255,255,0.1);
        border-radius: 8px 8px 0px 0px; color: white; padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #6a1b9a; color: white; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. LÓGICA DE NEGÓCIO
# ==========================================

if 'guests' not in st.session_state:
    st.session_state.guests = []
    if HAS_GSHEETS and ("gsheets" in st.secrets or "gcp_service_account" in st.secrets):
        db_data = load_data_from_sheets()
        if db_data:
            st.session_state.guests = db_data

if 'last_action_time' not in st.session_state:
    st.session_state.last_action_time = None

download_logo()

def add_guest():
    name = st.session_state.temp_name
    guest_type = st.session_state.temp_type
    age = st.session_state.get('temp_age', 0)
    
    if not name:
        st.warning("⚠️ Digite o nome!")
        return
    if guest_type == "Criança" and age == 0:
        st.warning("⚠️ Informe a idade!")
        return

    is_paying = True
    display_age = "-"
    status_label = "Pagante"
    
    if guest_type == "Criança":
        display_age = f"{int(age)} anos"
        # --- REGRA ATUALIZADA: SÓ É ISENTO ATÉ 7 ANOS ---
        if age <= 7: 
            is_paying = False
            status_label = "Isento"
    elif guest_type == "Cortesia":
        is_paying = False
        status_label = "Cortesia"

    unique_id = str(datetime.now().strftime("%Y%m%d%H%M%S%f"))
    
    new_guest = {
        "id": unique_id, "Nome": name, "Tipo": guest_type,
        "Idade": display_age, "Status": status_label,
        "Hora": datetime.now().strftime("%H:%M"), "_is_paying": is_paying
    }
    
    st.session_state.guests.insert(0, new_guest)
    if HAS_GSHEETS and ("gsheets" in st.secrets or "gcp_service_account" in st.secrets):
        save_guest_to_sheets(new_guest)
    
    st.session_state.last_action_time = datetime.now()
    st.session_state.temp_name = "" 

def remove_last_guest():
    if st.session_state.guests:
        removed = st.session_state.guests.pop(0)
        if HAS_GSHEETS and ("gsheets" in st.secrets or "gcp_service_account" in st.secrets):
            delete_guest_from_sheets(removed['id'])
        st.success(f"↩️ Desfeito: {removed['Nome']} removido.")
        st.session_state.last_action_time = None

def remove_guest_by_id(guest_id):
    st.session_state.guests = [g for g in st.session_state.guests if str(g['id']) != str(guest_id)]
    if HAS_GSHEETS and ("gsheets" in st.secrets or "gcp_service_account" in st.secrets):
        delete_guest_from_sheets(guest_id)

# --- CÁLCULOS ---
df = pd.DataFrame(st.session_state.guests)

if not df.empty:
    if 'id' in df.columns: df['id'] = df['id'].astype(str)
    if 'ID' in df.columns: df['ID'] = df['ID'].astype(str)
    
    total_paying = df[df['_is_paying'] == True].shape[0]
    total_cortesia = df[df['Tipo'] == 'Cortesia'].shape[0]
    total_not_paying_all = df[df['_is_paying'] == False].shape[0]
    total_free = total_not_paying_all - total_cortesia
    total_guests = len(df)
else:
    total_paying = 0; total_free = 0; total_cortesia = 0; total_guests = 0

# ==========================================
# 4. INTERFACE
# ==========================================

with st.sidebar:
    st.header("⚙️ Configurações")
    
    is_connected = HAS_GSHEETS and ("gsheets" in st.secrets or "gcp_service_account" in st.secrets)
    if is_connected:
        st.success("🟢 Online")
    else:
        st.warning("🟡 Offline")

    with st.expander("📝 Dados do Evento", expanded=True):
        party_name = st.text_input("Nome do Evento", value="Aniversário")
        guest_limit = st.number_input("Limite do Contrato", min_value=1, value=100, step=5)
    
    st.divider()

    with st.expander("🗑️ Excluir (Senha)"):
        if not df.empty:
            st.warning("Requer Senha")
            guest_options = {}
            for g in st.session_state.guests:
                g_nome = g.get('Nome', 'Sem Nome')
                g_hora = g.get('Hora', '--:--')
                g_id = str(g.get('id', ''))
                guest_options[f"{g_nome} ({g_hora})"] = g_id
            
            selected_name = st.selectbox("Selecione:", options=list(guest_options.keys()))
            password_input = st.text_input("Senha Admin", type="password")
            if st.button("❌ Confirmar"):
                if password_input == SENHA_ADMIN:
                    if selected_name in guest_options:
                        remove_guest_by_id(guest_options[selected_name])
                        st.success("Removido!"); st.rerun()
                else: st.error("Senha errada!")
        else: st.info("Lista vazia.")
    
    st.divider()
    
    # --- EXPORTAÇÃO NA LATERAL (PÚBLICA) ---
    st.subheader("📂 Exportar Dados")
    if not df.empty:
        cols_to_drop = ['_is_paying', 'id', 'ID']
        export_df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
        
        pdf_bytes = generate_pdf_report_v6(party_name, export_df, total_paying, total_free, total_cortesia, total_guests, guest_limit)
        
        st.download_button("📄 Baixar Relatório PDF", data=pdf_bytes, file_name="lista_final.pdf", mime="application/pdf", use_container_width=True)
        
        msg = f"Resumo {party_name}: {total_paying} Pagantes. Total: {total_guests}/{guest_limit}."
        st.link_button("📱 Enviar Resumo no Zap", f"https://api.whatsapp.com/send?text={msg}", use_container_width=True)
    else:
        st.info("Nenhum dado para exportar.")

    st.divider()
    if st.button("🗑️ NOVA FESTA (Zerar Local)"): 
        st.session_state.guests = []
        st.rerun()

# --- TELA PRINCIPAL ---
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)
    else: st.info("Carregando logo...")

st.markdown(f"<h2 style='text-align: center;'>{party_name}</h2>", unsafe_allow_html=True)

percent_full = min(total_guests / guest_limit, 1.0)
st.write(f"**Lotação:** {total_guests} de {guest_limit} pessoas")
st.progress(percent_full)
if total_guests >= guest_limit: 
    st.error("⚠️ LIMITE DO CONTRATO ATINGIDO! (Entrada Liberada)")

col1, col2, col3 = st.columns(3)
with col1: st.markdown(f"""<div class="metric-card card-purple"><div class="label">Pagantes</div><div class="big-number">{total_paying}</div></div>""", unsafe_allow_html=True)
with col2: st.markdown(f"""<div class="metric-card card-green"><div class="label">Isentos (≤7)</div><div class="big-number">{total_free}</div><div style="font-size:0.7em">Crianças</div></div>""", unsafe_allow_html=True)
with col3: st.markdown(f"""<div class="metric-card card-orange"><div class="label">Cortesias</div><div class="big-number">{total_cortesia}</div><div style="font-size:0.7em">Família</div></div>""", unsafe_allow_html=True)

st.write("") 

# --- ABAS PRINCIPAIS ---
tab_entry, tab_reports = st.tabs(["📍 Registrar Entrada", "📊 Relatórios & Gráficos (🔒)"])

# --- ABA 1: REGISTRO (PÚBLICO) ---
with tab_entry:
    with st.container(border=True):
        st.subheader("Adicionar Convidado")
        
        st.text_input("Nome do Convidado", placeholder="Digite o nome...", key="temp_name")
        
        c_type, c_age = st.columns([2, 1])
        with c_type: 
            guest_type = st.radio("Tipo", ["Adulto", "Criança", "Cortesia"], horizontal=True, key="temp_type")
        
        with c_age: 
            if guest_type == "Criança":
                st.number_input("Idade", min_value=0, max_value=18, step=1, key="temp_age", on_change=add_guest)
            else:
                st.empty()

        st.write("")
        
        b1, b2 = st.columns([3, 1])
        with b1:
            st.button("➕ CONFIRMAR ENTRADA", type="primary", on_click=add_guest)
        with b2:
            show_undo = False
            if st.session_state.guests and st.session_state.last_action_time:
                seconds_passed = (datetime.now() - st.session_state.last_action_time).total_seconds()
                if seconds_passed <= 15:
                    show_undo = True
            if show_undo:
                st.button("↩️ Desfazer", on_click=remove_last_guest, help="Remove o último convidado")

# --- ABA 2: RELATÓRIOS (PROTEGIDO) ---
with tab_reports:
    st.write("### 🔒 Área Restrita")
    senha = st.text_input("Digite a senha de administrador para visualizar os gráficos:", type="password", key="report_pwd")
    
    if senha == SENHA_ADMIN:
        if not df.empty:
            st.success("Acesso Liberado")
            st.subheader("📈 Fluxo de Chegada (Intervalos de 15 min)")
            
            if 'Hora' in df.columns:
                # Lógica de Agrupamento de 15 min
                chart_df = df.copy()
                chart_df['datetime'] = pd.to_datetime(chart_df['Hora'], format='%H:%M').apply(
                    lambda x: x.replace(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
                )
                chart_df['Intervalo'] = chart_df['datetime'].dt.floor('15T')
                interval_counts = chart_df['Intervalo'].value_counts().sort_index().reset_index()
                interval_counts.columns = ['Horário', 'Chegadas']
                interval_counts['Horário'] = interval_counts['Horário'].dt.strftime('%H:%M')
                
                fig_time = px.bar(interval_counts, x="Horário", y="Chegadas", text="Chegadas", color_discrete_sequence=['#fb8c00'])
                fig_time.update_layout(
                    margin=dict(t=10,b=10,l=10,r=10), 
                    height=300, 
                    paper_bgcolor='rgba(0,0,0,0)', 
                    plot_bgcolor='rgba(255,255,255,0.1)', 
                    font_color="white",
                    xaxis_title="Horário (Blocos de 15min)",
                    yaxis_title="Pessoas"
                )
                st.plotly_chart(fig_time, use_container_width=True)

            st.write("#### Lista Completa")
            cols_to_drop = ['_is_paying', 'id', 'ID']
            display_df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=300)
                
        else:
            st.info("Nenhum dado para exibir nos relatórios ainda.")
    elif senha:
        st.error("Senha Incorreta!")
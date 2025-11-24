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
SENHA_ADMIN = "1234"
SHEET_NAME = "Controle_Buffet" # Nome exato da sua planilha no Google

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Controle de Buffet", page_icon="🟣", layout="wide")

# ==========================================
# 1. FUNÇÕES DE BANCO DE DADOS (GOOGLE SHEETS)
# ==========================================

def get_db_connection():
    """Conecta ao Google Sheets usando as credenciais do st.secrets"""
    if not HAS_GSHEETS:
        return None
    
    # Verifica se os segredos existem no ambiente (Cloud ou Local)
    if "gsheets" not in st.secrets:
        return None

    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # Converte o objeto de segredos para dicionário padrão
        credentials_dict = dict(st.secrets["gsheets"])
        creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        st.error(f"Erro na conexão com o Google: {e}")
        return None

def load_data_from_sheets():
    """Carrega dados da nuvem para o sistema"""
    sheet = get_db_connection()
    if sheet:
        try:
            data = sheet.get_all_records()
            for row in data:
                row['_is_paying'] = True if row['Status'] == 'Pagante' else False
            return data[::-1]
        except Exception:
            return []
    return []

def save_guest_to_sheets(guest_dict):
    """Salva uma nova linha na planilha"""
    sheet = get_db_connection()
    if sheet:
        try:
            row = [
                guest_dict['id'],
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
    """Remove convidado da planilha"""
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
def generate_pdf(party_name, guests_df, total_paying, total_free, total_cortesia, total_guests, guest_limit):
    # Cria o PDF
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists(LOGO_PATH):
        try: pdf.image(LOGO_PATH, x=10, y=10, w=40)
        except: pass

    # Cabeçalho
    pdf.set_font("Helvetica", 'B', 16)
    pdf.set_xy(55, 15)
    pdf.set_text_color(106, 27, 154)
    pdf.cell(0, 10, txt=f"Relatório: {party_name}", ln=True, align='L')
    pdf.set_xy(55, 23)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 10, txt=f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='L')
    pdf.ln(20)
    
    # Resumo
    pdf.set_fill_color(106, 27, 154); pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 12); pdf.cell(0, 10, "  Resumo de Público", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", size=12); pdf.ln(2)
    
    pdf.cell(0, 8, f"Limite do Contrato: {guest_limit} pessoas", ln=True)
    pdf.cell(0, 8, f"Total Geral Presente: {total_guests}", ln=True)
    pdf.ln(2)
    pdf.cell(0, 8, f"Total Pagantes (Contrato): {total_paying}", ln=True)
    pdf.cell(0, 8, f"Crianças Isentas (< 8 anos): {total_free}", ln=True)
    pdf.cell(0, 8, f"Cortesias (Família/Staff): {total_cortesia}", ln=True)
    
    pdf.ln(10)
    
    # Tabela
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
            nome = str(row['Nome']).encode('latin-1', 'replace').decode('latin-1')
            tipo = str(row['Tipo']).encode('latin-1', 'replace').decode('latin-1')
            status = str(row['Status']).encode('latin-1', 'replace').decode('latin-1')
        except:
            nome = str(row['Nome']); tipo = str(row['Tipo']); status = str(row['Status'])

        pdf.cell(80, 8, nome, 1, 0, 'L', fill); pdf.cell(30, 8, tipo, 1, 0, 'C', fill)
        pdf.cell(30, 8, str(row['Idade']), 1, 0, 'C', fill); pdf.cell(30, 8, status, 1, 0, 'C', fill)
        pdf.cell(20, 8, str(row['Hora']), 1, 1, 'C', fill)
        fill = not fill
        
    # --- CORREÇÃO DE COMPATIBILIDADE (AQUI ESTAVA O ERRO) ---
    try:
        # Tenta pegar como string (padrão antigo)
        output_string = pdf.output(dest='S')
        if isinstance(output_string, str):
            # Se for string, converte para bytes
            return output_string.encode('latin-1')
        # Se já for bytes (versão nova), retorna direto
        return output_string
    except:
        # Última tentativa: deixar a biblioteca decidir o padrão
        return pdf.output()

# --- CSS (ESTILO) ---
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. LÓGICA DE NEGÓCIO E ESTADO
# ==========================================

# Sincronização Inicial
if 'guests' not in st.session_state:
    st.session_state.guests = []
    if HAS_GSHEETS and "gsheets" in st.secrets:
        db_data = load_data_from_sheets()
        if db_data:
            st.session_state.guests = db_data

if 'last_action_time' not in st.session_state:
    st.session_state.last_action_time = None

download_logo()

def add_guest():
    """Adiciona convidado (Memória + Sheets)"""
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
        if age <= 8: 
            is_paying = False
            status_label = "Isento"
    elif guest_type == "Cortesia":
        is_paying = False
        status_label = "Cortesia"

    unique_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    new_guest = {
        "id": unique_id, "Nome": name, "Tipo": guest_type,
        "Idade": display_age, "Status": status_label,
        "Hora": datetime.now().strftime("%H:%M"), "_is_paying": is_paying
    }
    
    st.session_state.guests.insert(0, new_guest)
    
    if HAS_GSHEETS and "gsheets" in st.secrets:
        save_guest_to_sheets(new_guest)
    
    st.session_state.last_action_time = datetime.now()
    st.session_state.temp_name = "" 

def remove_last_guest():
    """Desfazer (Memória + Sheets)"""
    if st.session_state.guests:
        removed = st.session_state.guests.pop(0)
        if HAS_GSHEETS and "gsheets" in st.secrets:
            delete_guest_from_sheets(removed['id'])
        st.success(f"↩️ Desfeito: {removed['Nome']} removido.")
        st.session_state.last_action_time = None

def remove_guest_by_id(guest_id):
    """Remover específico (Memória + Sheets)"""
    st.session_state.guests = [g for g in st.session_state.guests if g['id'] != guest_id]
    if HAS_GSHEETS and "gsheets" in st.secrets:
        delete_guest_from_sheets(guest_id)

# --- CÁLCULOS TOTAIS ---
df = pd.DataFrame(st.session_state.guests)
if not df.empty:
    total_paying = df[df['_is_paying'] == True].shape[0]
    total_cortesia = df[df['Tipo'] == 'Cortesia'].shape[0]
    total_not_paying_all = df[df['_is_paying'] == False].shape[0]
    total_free = total_not_paying_all - total_cortesia
    total_guests = len(df)
else:
    total_paying = 0; total_free = 0; total_cortesia = 0; total_guests = 0

# ==========================================
# 4. INTERFACE GRÁFICA (LAYOUT)
# ==========================================

with st.sidebar:
    st.header("⚙️ Configurações & Lista")
    
    # STATUS CONEXÃO (Agora depende da configuração na nuvem)
    if HAS_GSHEETS and "gsheets" in st.secrets:
        st.success("🟢 Online (Sincronizado)")
    else:
        st.warning("🟡 Offline (Local)")
        st.caption("Configure os 'Secrets' no painel do Streamlit Cloud para ativar o Google Sheets.")

    with st.expander("📝 Dados do Evento", expanded=True):
        party_name = st.text_input("Nome do Evento", value="Aniversário")
        guest_limit = st.number_input("Limite do Contrato", min_value=1, value=100, step=5)
    
    st.divider()

    with st.expander("🗑️ Excluir Convidado (Senha)"):
        if not df.empty:
            st.warning("Requer Senha")
            guest_options = {f"{g['Nome']} ({g['Hora']})": g['id'] for g in st.session_state.guests}
            selected_name = st.selectbox("Selecione:", options=list(guest_options.keys()))
            password_input = st.text_input("Senha Admin", type="password")
            if st.button("❌ Confirmar"):
                if password_input == SENHA_ADMIN:
                    remove_guest_by_id(guest_options[selected_name])
                    st.success("Removido!"); st.rerun()
                else: st.error("Senha errada!")
        else: st.info("Lista vazia.")
    
    st.divider()

    st.subheader("📂 Relatórios")
    if not df.empty:
        st.write("**📈 Chegadas por Horário:**")
        time_data = df.copy(); time_data['Contagem'] = 1; time_data = time_data.sort_values('Hora')
        fig_time = px.histogram(time_data, x="Hora", title=None, color_discrete_sequence=['#fb8c00'])
        fig_time.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=150, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.1)', font_color="white")
        st.plotly_chart(fig_time, use_container_width=True)

        # PDF Seguro
        cols_to_drop = ['_is_paying', 'id']
        export_df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
        pdf_bytes = generate_pdf(party_name, export_df, total_paying, total_free, total_cortesia, total_guests, guest_limit)
        
        st.download_button("📄 Baixar PDF", data=pdf_bytes, file_name="lista.pdf", mime="application/pdf")
        msg = f"Resumo {party_name}: {total_paying} Pagantes. Total: {total_guests}/{guest_limit}."
        st.link_button("📱 Enviar Zap", f"https://api.whatsapp.com/send?text={msg}")
        
        st.write("---")
        st.dataframe(export_df, use_container_width=True, hide_index=True, height=200)
    else: st.info("Lista vazia.")
    
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
with col2: st.markdown(f"""<div class="metric-card card-green"><div class="label">Isentos</div><div class="big-number">{total_free}</div><div style="font-size:0.7em">Crianças</div></div>""", unsafe_allow_html=True)
with col3: st.markdown(f"""<div class="metric-card card-orange"><div class="label">Cortesias</div><div class="big-number">{total_cortesia}</div><div style="font-size:0.7em">Família</div></div>""", unsafe_allow_html=True)

st.write("") 

with st.container(border=True):
    st.subheader("📍 Registrar Entrada")
    
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
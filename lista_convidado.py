import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import requests
import os
import plotly.express as px
import pytz # Biblioteca de fuso horário

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
SHEET_NAME = "Controle_Buffet" 

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Controle de Buffet", page_icon="🟣", layout="wide")

# ==========================================
# 0. FUNÇÕES DE TEMPO (FUSO HORÁRIO BRASIL)
# ==========================================
def get_brazil_time():
    """Retorna a data e hora atuais de São Paulo"""
    return datetime.now(pytz.timezone('America/Sao_Paulo'))

def get_today_str():
    """Retorna data formato DD/MM/YYYY BR"""
    return get_brazil_time().strftime("%d/%m/%Y")

def get_now_str():
    """Retorna hora formato HH:MM BR"""
    return get_brazil_time().strftime("%H:%M")

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

def get_active_parties_today():
    """Procura na planilha se existem festas rolando HOJE (Data BR)"""
    sheet = get_db_connection()
    if not sheet: return []
    
    try:
        data = sheet.get_all_records()
        today_str = get_today_str() # Usa data Brasil
        
        active_events = set()
        for row in data:
            row_date = str(row.get('Data', ''))
            row_event = str(row.get('Evento', '')).strip()
            
            if row_date == today_str and row_event:
                active_events.add(row_event)
        return list(active_events)
    except:
        return []

def load_data_from_sheets(target_event_name):
    """Carrega dados APENAS do evento ativo"""
    sheet = get_db_connection()
    if sheet:
        try:
            data = sheet.get_all_records()
            cleaned_data = []
            today_str = get_today_str() # Usa data Brasil

            for row in data:
                row_event = str(row.get('Evento', '')).strip().lower()
                target_event = str(target_event_name).strip().lower()
                row_date = str(row.get('Data', ''))
                row_status = str(row.get('Status', ''))
                
                # Ignora linhas de sistema
                if row_status == "SYSTEM_START":
                    continue

                # Compara Evento e Data
                if row_event == target_event and row_date == today_str:
                    raw_id = row.get('id') or row.get('ID') or ''
                    safe_id = str(raw_id)
                    
                    clean_row = {
                        'id': safe_id,
                        'Nome': row.get('Nome', ''),
                        'Tipo': row.get('Tipo', 'Adulto'),
                        'Idade': row.get('Idade', '-'),
                        'Status': row.get('Status', 'Pagante'),
                        'Hora': row.get('Hora', '--:--'),
                        'Data': row_date,
                        'Evento': row.get('Evento', '')
                    }
                    clean_row['_is_paying'] = True if clean_row['Status'] == 'Pagante' else False
                    cleaned_data.append(clean_row)
            
            return cleaned_data[::-1]
        except Exception as e:
            return []
    return []

def save_guest_to_sheets(guest_dict, event_name):
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
                guest_dict['Data'],
                event_name 
            ]
            sheet.append_row(row)
        except:
            pass

def delete_guest_from_sheets(guest_id):
    sheet = get_db_connection()
    if sheet:
        try:
            cell = sheet.find(str(guest_id))
            if cell: sheet.delete_rows(cell.row)
        except:
            pass

# ==========================================
# 2. FUNÇÕES VISUAIS
# ==========================================

@st.cache_resource
def download_logo():
    if not os.path.exists(LOGO_PATH):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(LOGO_URL, headers=headers, timeout=5)
            if response.status_code == 200:
                with open(LOGO_PATH, "wb") as f: f.write(response.content)
        except: pass

@st.cache_data(show_spinner=False)
def generate_pdf_report_v11(party_name, guests_df, total_paying, total_free, total_cortesia, total_guests, guest_limit):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists(LOGO_PATH):
        try: pdf.image(LOGO_PATH, x=10, y=10, w=40)
        except: pass

    pdf.set_font("Helvetica", 'B', 16)
    pdf.set_xy(55, 15)
    pdf.set_text_color(106, 27, 154)
    pdf.cell(0, 10, txt=f"Relatório Final: {party_name}", ln=True, align='L')
    pdf.set_xy(55, 23)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 10, txt=f"Data: {get_today_str()} | Encerrado às: {get_now_str()}", ln=True, align='L')
    pdf.ln(20)
    
    pdf.set_fill_color(106, 27, 154); pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 12); pdf.cell(0, 10, "  Resumo Financeiro e Público", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", size=12); pdf.ln(2)
    
    pdf.cell(0, 8, f"Limite Contratado: {guest_limit}", ln=True)
    pdf.cell(0, 8, f"Total Presente: {total_guests}", ln=True)
    pdf.ln(2)
    pdf.cell(0, 8, f"Pagantes: {total_paying}", ln=True)
    pdf.cell(0, 8, f"Isentos (<=7): {total_free}", ln=True)
    pdf.cell(0, 8, f"Cortesias: {total_cortesia}", ln=True)
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
            nome = str(row.get('Nome', '-')).encode('latin-1', 'replace').decode('latin-1')
            tipo = str(row.get('Tipo', '-')).encode('latin-1', 'replace').decode('latin-1')
            status = str(row.get('Status', '-')).encode('latin-1', 'replace').decode('latin-1')
            idade = str(row.get('Idade', '-'))
            hora = str(row.get('Hora', '-'))
        except:
            nome = str(row.get('Nome', '-')); tipo = "-"; status = "-"; idade="-"; hora="-"

        pdf.cell(80, 8, nome, 1, 0, 'L', fill); pdf.cell(30, 8, tipo, 1, 0, 'C', fill)
        pdf.cell(30, 8, idade, 1, 0, 'C', fill); pdf.cell(30, 8, status, 1, 0, 'C', fill)
        pdf.cell(20, 8, hora, 1, 1, 'C', fill)
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. GESTÃO DE SESSÃO
# ==========================================

download_logo()

if 'party_active' not in st.session_state:
    st.session_state.party_active = False
if 'party_name' not in st.session_state:
    st.session_state.party_name = ""
if 'guest_limit' not in st.session_state:
    st.session_state.guest_limit = 100
if 'guests' not in st.session_state:
    st.session_state.guests = []
if 'last_action_time' not in st.session_state:
    st.session_state.last_action_time = None

# --- FUNÇÃO PARA ENTRAR EM FESTA EXISTENTE ---
def join_existing_party(name_override=None):
    # Se foi passado um nome manual, usa ele. Se não, usa o selecionado no combo.
    selected = name_override if name_override else st.session_state.selected_active_party
    
    if selected:
        st.session_state.party_name = selected
        st.session_state.guest_limit = 100 
        st.session_state.party_active = True
        if HAS_GSHEETS:
            with st.spinner("Sincronizando dados..."):
                db_data = load_data_from_sheets(selected)
                # Se achou dados, carrega. Se não achou (é nova), inicia vazia.
                if db_data:
                    st.session_state.guests = db_data
                else:
                    st.session_state.guests = [] 
                    # Se entrou manualmente numa festa nova, cria o marco agora
                    start_system_marker(selected)
        st.rerun()

def start_system_marker(party_name):
    """Cria o marco inicial na planilha para o celular achar"""
    if HAS_GSHEETS:
        system_marker = {
            "id": "SYSTEM", 
            "Nome": "-- INÍCIO DA FESTA --", 
            "Tipo": "System",
            "Idade": "-", 
            "Status": "SYSTEM_START",
            "Hora": get_now_str(), 
            "Data": get_today_str()
        }
        save_guest_to_sheets(system_marker, party_name)

def start_party():
    if st.session_state.input_party_name:
        party_name = st.session_state.input_party_name
        st.session_state.party_name = party_name
        st.session_state.guest_limit = st.session_state.input_guest_limit
        st.session_state.party_active = True
        
        # Cria o marco inicial imediatamente
        start_system_marker(party_name)
        
        # Tenta carregar (caso seja retomada de crash)
        if HAS_GSHEETS:
            db_data = load_data_from_sheets(party_name)
            if db_data: st.session_state.guests = db_data
    else:
        st.warning("Digite o nome da festa!")

def end_party():
    st.session_state.party_active = False
    st.session_state.guests = []
    st.session_state.party_name = ""
    st.rerun()

def add_guest():
    if not st.session_state.party_active: return

    name = st.session_state.temp_name
    guest_type = st.session_state.temp_type
    age = st.session_state.get('temp_age', 0)
    
    if not name:
        st.warning("⚠️ Digite o nome!")
        return
    if guest_type == "Criança" and age == 0:
        st.warning("⚠️ Informe a idade!")
        return

    # --- TRAVA DE SEGURANÇA ANTI-DUPLICAÇÃO ---
    if st.session_state.guests and st.session_state.last_action_time:
        last_guest = st.session_state.guests[0]
        seconds_passed = (datetime.now() - st.session_state.last_action_time).total_seconds()
        if last_guest['Nome'] == name and seconds_passed < 5:
            st.warning(f"⚠️ {name} já foi adicionado agora! (Duplicidade evitada)")
            st.session_state.temp_name = "" # Limpa o campo
            return

    is_paying = True
    display_age = "-"
    status_label = "Pagante"
    
    if guest_type == "Criança":
        display_age = f"{int(age)} anos"
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
        "Hora": get_now_str(), 
        "Data": get_today_str(),
        "_is_paying": is_paying
    }
    
    st.session_state.guests.insert(0, new_guest)
    
    if HAS_GSHEETS and ("gsheets" in st.secrets or "gcp_service_account" in st.secrets):
        save_guest_to_sheets(new_guest, st.session_state.party_name)
    
    st.session_state.last_action_time = datetime.now()
    st.session_state.temp_name = "" 

def remove_last_guest():
    if st.session_state.guests:
        removed = st.session_state.guests.pop(0)
        if HAS_GSHEETS: delete_guest_from_sheets(removed['id'])
        st.success(f"↩️ Desfeito: {removed['Nome']} removido.")
        st.session_state.last_action_time = None

def remove_guest_by_id(guest_id):
    st.session_state.guests = [g for g in st.session_state.guests if str(g['id']) != str(guest_id)]
    if HAS_GSHEETS: delete_guest_from_sheets(guest_id)

def force_refresh():
    if st.session_state.party_active and HAS_GSHEETS:
        with st.spinner("Sincronizando..."):
            db_data = load_data_from_sheets(st.session_state.party_name)
            st.session_state.guests = db_data
            st.success("Sincronizado!")

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

# BARRA LATERAL
with st.sidebar:
    if not st.session_state.party_active:
        st.header("⚙️ Início (Data: " + get_today_str() + ")")
        is_connected = HAS_GSHEETS and ("gsheets" in st.secrets or "gcp_service_account" in st.secrets)
        
        if is_connected:
            st.success("🟢 Online")
            
            st.markdown("### 📡 Festas Rolando Hoje")
            if st.button("🔄 Buscar Festas"):
                st.rerun()
                
            active_events_today = get_active_parties_today()
            
            if active_events_today:
                st.selectbox("Selecione para entrar:", options=active_events_today, key="selected_active_party")
                if st.button("👉 ENTRAR NESTA FESTA", type="primary"):
                    join_existing_party()
            else:
                st.info("Nenhuma festa encontrada hoje.")
                
            st.markdown("---")
            st.write("Ou digite o nome exato para forçar entrada:")
        else:
            st.warning("🟡 Offline")
        
        # Se não achou na lista, digita aqui e inicia/entra
        st.text_input("Nome do Evento (Novo ou Existente)", key="input_party_name", placeholder="Ex: Enzo 5 Anos")
        st.number_input("Limite do Contrato", min_value=1, value=100, step=5, key="input_guest_limit")
        
        if st.button("🚀 INICIAR / ENTRAR"):
            start_party()
            st.rerun()
            
    else:
        st.header(f"🎉 {st.session_state.party_name}")
        st.caption(f"Contrato: {st.session_state.guest_limit} pessoas")
        
        if st.button("🔄 Sincronizar Agora"):
            force_refresh()
            
        st.divider()
        
        with st.expander("🗑️ Excluir (Senha)"):
            if not df.empty:
                guest_options = {f"{g.get('Nome','-')} ({g.get('Hora','-')})": str(g.get('id','')) for g in st.session_state.guests}
                selected_name = st.selectbox("Selecione:", options=list(guest_options.keys()))
                password_input = st.text_input("Senha Admin", type="password")
                if st.button("❌ Confirmar Exclusão"):
                    if password_input == SENHA_ADMIN:
                        if selected_name in guest_options:
                            remove_guest_by_id(guest_options[selected_name])
                            st.success("Removido!"); st.rerun()
                    else: st.error("Senha errada!")
            else: st.info("Lista vazia.")
            
        st.divider()
        
        st.subheader("🏁 Encerrar")
        if not df.empty:
            cols_to_drop = ['_is_paying', 'id', 'ID']
            export_df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
            pdf_bytes = generate_pdf_report_v11(st.session_state.party_name, export_df, total_paying, total_free, total_cortesia, total_guests, st.session_state.guest_limit)
            
            st.download_button("1️⃣ Baixar Relatório", data=pdf_bytes, file_name=f"Relatorio_{st.session_state.party_name}.pdf", mime="application/pdf", use_container_width=True)
            
            msg = f"Relatório Final - {st.session_state.party_name}: {total_paying} Pagantes. Total: {total_guests}/{st.session_state.guest_limit}."
            st.link_button("2️⃣ Enviar no Zap", f"https://api.whatsapp.com/send?text={msg}", use_container_width=True)
        
        st.write("")
        if st.button("🔴 SAIR / ENCERRAR"):
            end_party()

# ÁREA PRINCIPAL
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)

if not st.session_state.party_active:
    st.markdown("<h1 style='text-align: center;'>Controle de Buffet</h1>", unsafe_allow_html=True)
    st.info("👈 Na barra lateral: Se a festa já existe, selecione na lista. Se não aparecer, digite o nome e clique em Iniciar.")
    
else:
    st.markdown(f"<h2 style='text-align: center;'>{st.session_state.party_name}</h2>", unsafe_allow_html=True)

    percent_full = min(total_guests / st.session_state.guest_limit, 1.0)
    st.write(f"**Lotação:** {total_guests} de {st.session_state.guest_limit} pessoas")
    st.progress(percent_full)
    if total_guests >= st.session_state.guest_limit: 
        st.error("⚠️ LIMITE DO CONTRATO ATINGIDO! (Entrada Liberada)")

    col1, col2, col3 = st.columns(3)
    with col1: st.markdown(f"""<div class="metric-card card-purple"><div class="label">Pagantes</div><div class="big-number">{total_paying}</div></div>""", unsafe_allow_html=True)
    with col2: st.markdown(f"""<div class="metric-card card-green"><div class="label">Isentos (≤7)</div><div class="big-number">{total_free}</div><div style="font-size:0.7em">Crianças</div></div>""", unsafe_allow_html=True)
    with col3: st.markdown(f"""<div class="metric-card card-orange"><div class="label">Cortesias</div><div class="big-number">{total_cortesia}</div><div style="font-size:0.7em">Família</div></div>""", unsafe_allow_html=True)

    st.write("") 

    tab_entry, tab_reports = st.tabs(["📍 Registrar Entrada", "📊 Gráficos (Admin)"])

    with tab_entry:
        with st.container(border=True):
            st.subheader("Adicionar Convidado")
            st.text_input("Nome do Convidado", placeholder="Digite o nome...", key="temp_name")
            c_type, c_age = st.columns([2, 1])
            with c_type: guest_type = st.radio("Tipo", ["Adulto", "Criança", "Cortesia"], horizontal=True, key="temp_type")
            with c_age: 
                if guest_type == "Criança":
                    st.number_input("Idade", min_value=0, max_value=18, step=1, key="temp_age", on_change=add_guest)
                else: st.empty()
            st.write("")
            b1, b2 = st.columns([3, 1])
            with b1: st.button("➕ CONFIRMAR ENTRADA", type="primary", on_click=add_guest)
            with b2:
                show_undo = False
                if st.session_state.guests and st.session_state.last_action_time:
                    seconds_passed = (datetime.now() - st.session_state.last_action_time).total_seconds()
                    if seconds_passed <= 15: show_undo = True
                if show_undo: st.button("↩️ Desfazer", on_click=remove_last_guest, help="Remove o último convidado")

    with tab_reports:
        st.write("### 🔒 Área Restrita")
        senha = st.text_input("Senha Admin:", type="password", key="report_pwd")
        if senha == SENHA_ADMIN:
            if not df.empty and 'Hora' in df.columns:
                chart_df = df.copy()
                # Converte hora string para datetime para agrupar
                try:
                    chart_df['datetime'] = pd.to_datetime(chart_df['Hora'], format='%H:%M').apply(lambda x: x.replace(year=datetime.now().year))
                    chart_df['Intervalo'] = chart_df['datetime'].dt.floor('15T')
                    interval_counts = chart_df['Intervalo'].value_counts().sort_index().reset_index()
                    interval_counts.columns = ['Horário', 'Chegadas']
                    interval_counts['Horário'] = interval_counts['Horário'].dt.strftime('%H:%M')
                    
                    fig_time = px.bar(interval_counts, x="Horário", y="Chegadas", text="Chegadas", color_discrete_sequence=['#fb8c00'])
                    fig_time.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.1)', font_color="white")
                    st.plotly_chart(fig_time, use_container_width=True)
                except:
                    st.warning("Dados de horário insuficientes para gráfico.")
                
                st.write("#### Lista Completa")
                cols_to_drop = ['_is_paying', 'id', 'ID']
                display_df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
                st.dataframe(display_df, use_container_width=True, hide_index=True, height=300)
            else: st.info("Sem dados ainda.")
        elif senha: st.error("Senha Incorreta!")
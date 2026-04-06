import streamlit as st
import pandas as pd
import json
import os
from processor import process_pdf, get_font_stats

st.set_page_config(page_title="PDF Cleaner", layout="wide")

ABREV_FILE = "abreviacoes.json"

def load_abreviacoes():
    if os.path.exists(ABREV_FILE):
        try:
            with open(ABREV_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_abreviacoes(data):
    with open(ABREV_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

st.title("🧽 PDF Cleaner & Scraper")
st.markdown("Pré-processador inteligente de eBooks. Extrai texto de PDFs, aplica expansão de abreviaturas e re-injeta marcadores visuais.")

# --- SEÇÃO DE UPLOAD (TOPO) ---
st.header("📄 1. Enviar Arquivo")
uploaded_file = st.file_uploader("Selecione um Arquivo PDF Bruto", type=["pdf"], accept_multiple_files=False)

# Inicializar estados de sessão
if 'font_stats' not in st.session_state:
    st.session_state.font_stats = None
if 'last_uploaded' not in st.session_state:
    st.session_state.last_uploaded = None

# Layout de Colunas para Configurações e Filtros
col_config, col_main = st.columns([1, 2])

# Variáveis globais para os text_inputs (precisam existir antes do botão processar)
with col_config:
    st.header("⚙️ 2. Ajustes de Limpeza")
    
    with st.expander("Controle de Páginas", expanded=True):
        ignore_pages = st.text_input("🚫 Ignorar Páginas", help="Ex: 1, 3, 5-7")
        force_pages = st.text_input("✅ Forçar Extração", help="Ignora cortes nessas páginas")
    
    with st.expander("Cortes de Margem", expanded=False):
        top_margin = st.slider("Margem Superior (%)", 0, 30, 8)
        bottom_margin = st.slider("Margem Inferior (%)", 0, 30, 10)
    
    with st.expander("Estratégia de Pausas", expanded=False):
        inject_title_pauses = st.toggle("Pausa em Capítulos", value=True)
        inject_normal_pauses = st.toggle("Pausas Extras no Corpo", value=False)
    
    with st.expander("Expansor de Abreviação", expanded=False):
        df_abrev = pd.DataFrame(load_abreviacoes())
        if df_abrev.empty: df_abrev = pd.DataFrame(columns=["origem", "destino"])
        edited_df = st.data_editor(df_abrev, num_rows="dynamic", use_container_width=True)
        if st.button("Salvar Tabela"):
            save_abreviacoes(edited_df.to_dict('records'))
            st.success("Salvo!")
            
    with st.expander("Exportação", expanded=True):
        output_format = st.radio("Formato:", ["TXT", "PDF"], index=0)

with col_main:
    st.header("🎨 3. Análise de Estilos")
    
    if uploaded_file:
        if st.session_state.font_stats is None or st.session_state.last_uploaded != uploaded_file.name:
            with st.spinner("Analisando estilos do PDF..."):
                file_bytes = uploaded_file.read()
                st.session_state.font_stats = get_font_stats(file_bytes, ignore_pages)
                st.session_state.last_uploaded = uploaded_file.name
                st.session_state.file_bytes = file_bytes
        
        if st.session_state.font_stats:
            stats = st.session_state.font_stats
            sorted_fonts = sorted(stats.items(), key=lambda x: x[1]['count'], reverse=True)
            
            # --- DETECÇÃO AUTOMÁTICA ---
            primary_font = sorted_fonts[0][0] # Mais frequente
            
            # Capítulo: Maior fonte que tenha pelo menos 100 caracteres no livro
            potential_titles = [s for s, d in stats.items() if s > primary_font and d['count'] > 50]
            chapter_font = max(potential_titles) if potential_titles else primary_font
            
            # Display em Caixas Curtas
            c1, c2 = st.columns(2)
            c1.success(f"**Corpo do Texto:** {primary_font}pt")
            if chapter_font != primary_font:
                c2.info(f"**Títulos/Capítulos:** {chapter_font}pt")
            
            st.write("Selecione os estilos para manter no arquivo final:")
            allowed_sizes = []
            f_col1, f_col2 = st.columns(2)
            
            for idx, (size, data) in enumerate(sorted_fonts):
                label = f"**{size}pt** - Ex: *{data['sample'][:60]}...*"
                # Sugestão inteligente: marcar se for corpo ou capítulo
                is_suggested = (size == primary_font or size == chapter_font)
                
                target_col = f_col1 if idx % 2 == 0 else f_col2
                if target_col.checkbox(label, value=is_suggested, key=f"font_{size}"):
                    allowed_sizes.append(size)
            
            st.session_state.allowed_sizes = allowed_sizes

    st.divider()
    
    # Botão de Processar agora no final da coluna Main (mais visível após config)
    if uploaded_file and st.button("🚀 TRATAR E LIMPAR ARQUIVO", type="primary", use_container_width=True):
        try:
            with st.status("Processando...", expanded=True) as status:
                st.write("Lendo bytes...")
                file_bytes = st.session_state.file_bytes
                st.write("Executando limpeza profunda...")
                
                new_file = process_pdf(
                    file_bytes, top_margin, bottom_margin, 
                    edited_df.to_dict('records'),
                    inject_title_pauses, inject_normal_pauses,
                    ignore_pages_str=ignore_pages,
                    force_pages_str=force_pages,
                    output_format=output_format.lower(),
                    allowed_font_sizes=st.session_state.get('allowed_sizes', None)
                )
                status.update(label="✅ Concluído!", state="complete")
            
            ext = output_format.lower()
            orig_name = uploaded_file.name.rsplit('.', 1)[0]
            st.download_button(
                label=f"⬇️ BAIXAR {orig_name.upper()}.{ext}",
                data=new_file,
                file_name=f"limpo_{orig_name}.{ext}",
                mime="application/pdf" if ext == "pdf" else "text/plain",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Erro: {str(e)}")

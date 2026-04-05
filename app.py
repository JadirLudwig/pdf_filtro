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
st.markdown("Pré-processador inteligente de eBooks. Extrai texto de PDFs, aplica expansão de abreviaturas e re-injeta marcadores visuais para melhor leitura no TTS do *Livros Narrados*.")

# Layout
col_config, col_main = st.columns([1, 2])

with col_config:
    st.header("⚙️ Configurações")
    
    with st.expander("Controle Analítico de Páginas", expanded=True):
        st.write("Especifique páginas por número (ex: 1, 3, 5-7).")
        ignore_pages = st.text_input("🚫 Ignorar Páginas (removidas do PDF final)", help="Use isto para sumários ou notas do autor que devem ser ignoradas na narração.")
        force_pages = st.text_input("✅ Forçar Extração de Páginas", help="Força a ignorar o corte das margens nestas páginas, para capturar o texto todo se ele estiver batendo no rodapé/cabeçalho.")
    
    with st.expander("Margens de Corte (Cabeçalhos)", expanded=True):
        st.write("Corte as regiões da página que possuem numeração ou nome da editora recorrente.")
        top_margin = st.slider("Margem Superior a ignorar (%)", 0, 30, 8)
        bottom_margin = st.slider("Margem Inferior a ignorar (%)", 0, 30, 10)
    
    with st.expander("Estratégia de Pausas", expanded=True):
        inject_title_pauses = st.toggle("Pausar em Títulos/Capítulos", value=True, help="Detecta textos grandes via IA e coloca um '.' no final se não haver, forçando o TTS a dar uma pausa no cap.")
        inject_normal_pauses = st.toggle("Pausas Extras no Corpo do Texto", value=False, help="Injeta quebras duplas ao encontrar '; ' ou '. ', prolongando o silêncio nos pontos finais.")
    
    with st.expander("Tabela: Expansor de Abreviação", expanded=True):
        df_abrev = pd.DataFrame(load_abreviacoes())
        if df_abrev.empty:
            df_abrev = pd.DataFrame(columns=["origem", "destino"])
            
        edited_df = st.data_editor(df_abrev, num_rows="dynamic", use_container_width=True)
        if st.button("Salvar Tabela", use_container_width=True):
            save_abreviacoes(edited_df.to_dict('records'))
            st.success("Tabela salva!")
            
    with st.expander("Formato Final de Exportação", expanded=True):
        output_format = st.radio("Selecione o formato desejado:", ["TXT", "PDF"], index=0, help="O TXT é ideal e preferível para ingerir direto no Livros Narrados e em outros I.As. O PDF serve para leitura humana.")

    # Novo: Seletor de Estilos de Fonte
    st.header("🎨 Filtro de Estilo (Fontes)")
    st.write("Selecione quais tamanhos de texto manter. Desmarque tamanhos pequenos para ignorar notas de rodapé.")
    
    font_weights = {}
    if 'font_stats' not in st.session_state:
        st.session_state.font_stats = None

    uploaded_file = st.file_uploader("Selecione um Arquivo PDF Bruto", type=["pdf"], accept_multiple_files=False)
    
    if uploaded_file:
        if st.session_state.font_stats is None or st.session_state.last_uploaded != uploaded_file.name:
            with st.spinner("Analisando estilos do PDF..."):
                file_bytes = uploaded_file.read()
                st.session_state.font_stats = get_font_stats(file_bytes, ignore_pages)
                st.session_state.last_uploaded = uploaded_file.name
                st.session_state.file_bytes = file_bytes # Store to avoid re-reading
        
        if st.session_state.font_stats:
            # Ordenar por contagem de caracteres (mais frequentes primeiro)
            sorted_fonts = sorted(st.session_state.font_stats.items(), key=lambda x: x[1]['count'], reverse=True)
            
            allowed_sizes = []
            
            # Criando colunas para os filtros de fonte não ocuparem muito espaço vertical
            f_col1, f_col2 = st.columns(2)
            for idx, (size, data) in enumerate(sorted_fonts):
                label = f"{size}pt (Ex: '{data['sample']}...')"
                default_val = size >= 9.0
                
                # Alternar entre as colunas
                target_col = f_col1 if idx % 2 == 0 else f_col2
                if target_col.checkbox(label, value=default_val, key=f"font_{size}"):
                    allowed_sizes.append(size)
            
            st.session_state.allowed_sizes = allowed_sizes
        
with col_main:
    st.header("📄 Processar")
    
    if uploaded_file and st.button("Tratar Arquivo", type="primary"):
        abrev_lista = edited_df.to_dict('records')
        
        st.write(f"⏳ Otimizando **{uploaded_file.name}**...")
        try:
            # Use stored bytes
            file_bytes = st.session_state.file_bytes
            
            # Execute
            new_file = process_pdf(
                file_bytes, 
                top_margin, 
                bottom_margin, 
                abrev_lista, 
                inject_title_pauses, 
                inject_normal_pauses,
                ignore_pages_str=ignore_pages,
                force_pages_str=force_pages,
                output_format=output_format.lower(),
                allowed_font_sizes=st.session_state.get('allowed_sizes', None)
            )
            
            # Provide fresh File
            st.success(f"✔️ Processo computado com sucesso! Arquivo {output_format} otimizado pronto para narrações.")
            
            ext = output_format.lower()
            mime_t = "application/pdf" if ext == "pdf" else "text/plain"
            orig_name = uploaded_file.name.rsplit('.', 1)[0]
            
            st.download_button(
                label=f"⬇️ Baixar NOVO {orig_name}.{ext}",
                data=new_file,
                file_name=f"limpo_{orig_name}.{ext}",
                mime=mime_t,
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"Erro ao processar: {str(e)}")

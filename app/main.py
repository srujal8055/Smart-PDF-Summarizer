import os
import sys
import time

# Robust path handling: Add the workspace root to Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st
from app.parser import extract_pdf_text_and_metadata
from app.chunker import chunk_document
from app.summarizer import (
    generate_map_reduce_summary,
    verify_api_connection,
    get_api_key,
    get_model_name,
    get_groq_api_key,
    get_groq_model_name,
    get_cohere_api_key
)
from app.db_helper import (
    save_summary_log,
    get_all_summaries_history,
    get_summary_by_id,
    delete_summary_by_id
)
from app.exporter import generate_pdf_report

# Page Configuration
st.set_page_config(
    page_title="Multi-Format PDF Summarization Studio",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling injection
def inject_custom_css():
    st.markdown("""
    <style>
        /* Import Outfit or Inter font */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
        
        /* Apply fonts */
        html, body, [class*="css"], .stMarkdown {
            font-family: 'Outfit', 'Inter', sans-serif;
        }
        
        /* Vibrant header gradient */
        .header-container {
            background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #3b82f6 100%);
            padding: 30px;
            border-radius: 16px;
            color: white;
            margin-bottom: 25px;
            box-shadow: 0 4px 20px rgba(37, 99, 235, 0.15);
            text-align: center;
        }
        .header-title {
            font-size: 2.5rem;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.5px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .header-subtitle {
            font-size: 1.1rem;
            font-weight: 300;
            opacity: 0.9;
            margin-top: 10px;
        }
        
        /* Metric cards custom styling */
        .metric-card {
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid rgba(229, 231, 235, 0.5);
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px rgba(0, 0, 0, 0.05);
            border-color: rgba(37, 99, 235, 0.2);
        }
        .metric-val {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1e3a8a;
        }
        .metric-label {
            font-size: 0.9rem;
            color: #4b5563;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Custom styling for container panels */
        .glass-panel {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
        }
        
        /* Highlight sections */
        .badge {
            background-color: #dbeafe;
            color: #1e40af;
            padding: 4px 8px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 10px;
        }
        
        /* Sidebar styling additions */
        .sidebar-header {
            font-size: 1.25rem;
            font-weight: 700;
            color: #1e3a8a;
            margin-bottom: 15px;
        }
        
        /* Custom buttons spacing and hover animation */
        div.stButton > button {
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        ::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }
    </style>
    """, unsafe_allow_html=True)

# Call styling injection
inject_custom_css()

# uploaded_file managed on main page
if "uploaded_file" not in st.session_state:
    st.session_state["uploaded_file"] = None

if "current_summary" not in st.session_state:
    st.session_state["current_summary"] = None

uploaded_file = st.session_state["uploaded_file"]

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.markdown('<p class="sidebar-header">🛠️ Studio Control Panel</p>', unsafe_allow_html=True)

    st.markdown("---")

    # --- AI PROVIDER SWITCHER ---
    st.markdown('<p class="sidebar-header">🔑 AI Provider & API Keys</p>', unsafe_allow_html=True)

    if "ai_provider" not in st.session_state:
        st.session_state["ai_provider"] = "auto"

    provider_labels = {
        "auto": "Auto (Gemini → Groq → Cohere)",
        "gemini": "Gemini",
        "groq": "Groq",
        "cohere": "Cohere",
    }
    selected_label = st.selectbox(
        "Active provider",
        options=list(provider_labels.values()),
        index=list(provider_labels.keys()).index(st.session_state["ai_provider"]),
        help="Choose which AI provider handles summarization. 'Auto' falls back automatically if one fails."
    )
    st.session_state["ai_provider"] = [k for k, v in provider_labels.items() if v == selected_label][0]

    st.markdown("---")
    
    # Settings Configurations
    st.markdown('<p class="sidebar-header">⚙️ Summary Adjustments</p>', unsafe_allow_html=True)
    
    summary_format = st.selectbox(
        "Summary Format",
        options=["Executive Summary", "Action-Items Checklist", "Q&A Study Guide", "Core Timeline"],
        help="Choose the narrative style for the final output report."
    )
    
    chunk_size = st.slider(
        "Text Chunk Size (chars)",
        min_value=1500,
        max_value=5000,
        value=3000,
        step=500,
        help="Target size for mapping chunks."
    )
    
    chunk_overlap = st.slider(
        "Chunk Overlap (chars)",
        min_value=0,
        max_value=500,
        value=200,
        step=50,
        help="Overlap size to maintain context between chunks."
    )

    st.markdown("---")
    st.caption("Smart PDF Summarizer v1.0.0")
    st.caption("Assigned Student: Shaikh Ajimuddin")
    st.caption("Mentorship: Learn → Build → Integrate")

# --- MAIN APP LAYOUT ---

# Header Section
st.markdown("""
<div class="header-container">
    <h1 class="header-title">📄 Multi-Format PDF Summarization Studio</h1>
    <p class="header-subtitle">Analyze, parse, and condense documents of any size using manual Map-Reduce chunking & Gemini AI</p>
</div>
""", unsafe_allow_html=True)

# Define Tabs
tab_summarize, tab_history, tab_diagnostics = st.tabs([
    "🚀 Summarize Studio", 
    "📚 Saved Archives", 
    "🔧 System Diagnostics"
])

# ---------------------------------------------
# TAB 1: SUMMARIZE STUDIO
# ---------------------------------------------
with tab_summarize:
    if not uploaded_file:
        # ── FRONT PAGE: Upload + Format + Generate ─────────────
        col_l, col_c, col_r = st.columns([1, 3, 1])
        with col_c:
            # Upload box
            st.markdown("""
            <div style="
                border: 2px dashed #2563eb;
                border-radius: 20px;
                padding: 30px 25px 10px 25px;
                text-align: center;
                background: rgba(37,99,235,0.05);
                margin-bottom: 8px;
            ">
                <div style="font-size:3rem;">📄</div>
                <h3 style="color:#1e3a8a; margin:8px 0 4px 0; font-weight:700;">Upload Your PDF</h3>
                <p style="color:#6b7280; font-size:0.88rem; margin:0 0 12px 0;">
                    Drag & drop or click to browse · Max 200MB
                </p>
            </div>
            """, unsafe_allow_html=True)

            new_file = st.file_uploader(
                "Upload PDF",
                type=["pdf"],
                label_visibility="collapsed",
                key="front_uploader"
            )
            if new_file is not None:
                st.session_state["uploaded_file"] = new_file
                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)

            # Format selector
            st.markdown("**📋 Select Summary Format:**")
            format_choice = st.selectbox(
                "Format",
                ["Executive Summary", "Action-Items Checklist", "Q&A Study Guide", "Core Timeline"],
                label_visibility="collapsed"
            )
            summary_format = format_choice

            st.markdown("<br>", unsafe_allow_html=True)

            # Generate button — disabled until PDF uploaded
            st.button(
                "🚀 Generate Summarization Report",
                use_container_width=True,
                type="primary",
                disabled=True
            )
            st.caption("⬆️ Upload a PDF above to enable")

    else:
        # File loaded: display metadata
        file_bytes = uploaded_file.getvalue()
        file_size_kb = len(file_bytes) / 1024

        # Format selector + Generate button
        col_fmt, col_btn, col_clear = st.columns([3, 2, 1])
        with col_fmt:
            format_choice = st.selectbox(
                "📋 Summary Format",
                ["Executive Summary", "Action-Items Checklist", "Q&A Study Guide", "Core Timeline"],
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            start_btn = st.button("🚀 Generate Report", use_container_width=True, type="primary")
        with col_clear:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state["uploaded_file"] = None
                st.rerun()

        summary_format = format_choice
        
        # Read pages to get page counts immediately (Cached for performance)
        @st.cache_data(show_spinner=False)
        def parse_uploaded_pdf(file_data, name):
            return extract_pdf_text_and_metadata(file_data, name)
            
        with st.spinner("Extracting PDF structure and reading page maps..."):
            parse_result = parse_uploaded_pdf(file_bytes, uploaded_file.name)
            
        if not parse_result["success"]:
            st.error(f"❌ Failed to parse PDF: {parse_result['error']}")
        else:
            page_count = parse_result["page_count"]
            pages_dict = parse_result["pages"]
            
            # Show File Stats Cards
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">📁 File Name</div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #1e3a8a; margin-top:5px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                        {uploaded_file.name}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">📄 Page Count</div>
                    <div class="metric-val">{page_count}</div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                # Format file size nicely
                size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.2f} MB"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">⚖️ File Size</div>
                    <div class="metric-val">{size_str}</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)

            # Summarization execution
            if start_btn:
                # 1. Chunk document
                with st.spinner("Segmenting text into logical chunks..."):
                    chunks = chunk_document(pages_dict, max_chars=chunk_size, overlap=chunk_overlap)
                    total_chunks = len(chunks)
                    
                st.info(f"📋 Document segmented into **{total_chunks}** text chunks. Starting Map-Reduce Loop...")
                
                # 2. Setup Progress display
                progress_bar = st.progress(0.0)
                status_placeholder = st.empty()
                
                # Define progress callback
                def update_progress(current_step: int, total_steps: int, status_text: str):
                    progress_percentage = float(current_step) / float(total_steps)
                    progress_bar.progress(progress_percentage)
                    status_placeholder.markdown(f"⏳ **Pipeline Status:** {status_text}")
                
                # Run Map-Reduce Summarizer
                summarizer_response = generate_map_reduce_summary(
                    chunks, 
                    format_type=summary_format, 
                    provider=st.session_state.get("ai_provider", "auto"),
                    progress_callback=update_progress
                )
                
                if summarizer_response["success"]:
                    # Clean progress bars after completion
                    progress_bar.empty()
                    status_placeholder.empty()
                    st.success("🎉 Report compiled and logged to history archive successfully!")
                    
                    # 3. Log to SQLite
                    db_id = save_summary_log(
                        filename=uploaded_file.name,
                        file_size=len(file_bytes),
                        page_count=page_count,
                        summary_type=summary_format,
                        final_summary=summarizer_response["final_summary"],
                        intermediate_summaries=summarizer_response["intermediate_summaries"]
                    )
                    
                    # Store current session summary
                    st.session_state["current_summary"] = {
                        "db_id": db_id,
                        "filename": uploaded_file.name,
                        "page_count": page_count,
                        "summary_type": summary_format,
                        "final_summary": summarizer_response["final_summary"],
                        "intermediate_summaries": summarizer_response["intermediate_summaries"],
                        "chunks": chunks
                    }
                else:
                    progress_bar.empty()
                    status_placeholder.empty()
                    st.error(f"❌ Summarization failed: {summarizer_response['error']}")
            
            # Display current session summary result if it exists
            if st.session_state["current_summary"] is not None:
                cur = st.session_state["current_summary"]
                st.markdown("<hr>", unsafe_allow_html=True)
                
                # Layout: Side-by-side or collapsible panels
                st.markdown('<p class="sidebar-header">📊 Compiled Report Results</p>', unsafe_allow_html=True)
                
                col_left, col_right = st.columns([7, 5])
                
                with col_left:
                    st.markdown(f'<span class="badge">{cur["summary_type"]}</span>', unsafe_allow_html=True)
                    st.markdown("""
                    <div class="glass-panel" style="max-height: 600px; overflow-y: auto;">
                    """, unsafe_allow_html=True)
                    # Render Final Markdown Summary
                    st.markdown(cur["final_summary"])
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Download actions
                    st.markdown("##### 📥 Export Summarization Report")
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    
                    # Export Text
                    with btn_col1:
                        st.download_button(
                            label="📄 Download Text (.txt)",
                            data=cur["final_summary"],
                            file_name=f"summary_{cur['filename'].replace('.pdf', '')}_{cur['summary_type'].lower().replace(' ', '_')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                        
                    # Export Markdown
                    with btn_col2:
                        st.download_button(
                            label="🗂️ Download Markdown (.md)",
                            data=cur["final_summary"],
                            file_name=f"summary_{cur['filename'].replace('.pdf', '')}_{cur['summary_type'].lower().replace(' ', '_')}.md",
                            mime="text/markdown",
                            use_container_width=True
                        )
                        
                    # Export PDF
                    with btn_col3:
                        pdf_stream = generate_pdf_report(cur["filename"], cur["summary_type"], cur["final_summary"])
                        st.download_button(
                            label="📊 Download Styled PDF (.pdf)",
                            data=pdf_stream.getvalue(),
                            file_name=f"summary_{cur['filename'].replace('.pdf', '')}_{cur['summary_type'].lower().replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                with col_right:
                    st.markdown('<span class="badge" style="background-color:#fef3c7; color:#92400e;">Source Context & Citations</span>', unsafe_allow_html=True)
                    st.markdown("""
                    <div class="glass-panel" style="max-height: 600px; overflow-y: auto;">
                    """, unsafe_allow_html=True)
                    st.markdown("##### 🔗 Page-wise Citation Chunks")
                    st.caption("The document was divided into the following sections for mapping:")
                    
                    chunks_list = cur.get("chunks", [])
                    # If chunks are not stored in session (e.g. from history reload), we can show intermediate summaries instead
                    if chunks_list:
                        for chunk in chunks_list:
                            with st.expander(f"Chunk {chunk['index']} (Pages: {chunk['pages']} | Chars: {chunk['char_count']})"):
                                st.caption("Raw Input Content:")
                                st.code(chunk["text"], language="text")
                    else:
                        st.caption("No raw chunks stored in this history session.")
                        
                    # Show intermediate summaries
                    if cur.get("intermediate_summaries"):
                        st.markdown("##### 🧩 Intermediate Summaries (Map Phase Logs)")
                        for idx, summary_item in enumerate(cur["intermediate_summaries"]):
                            with st.expander(f"Intermediate Summary {idx + 1}"):
                                st.markdown(summary_item)
                                
                    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------
# TAB 2: SAVED ARCHIVES (SQL LOGS)
# ---------------------------------------------
with tab_history:
    st.markdown("### 📚 Archive History Logger")
    st.caption("Review, analyze, and retrieve previously generated multi-format summaries.")
    
    # Reload histories
    history_logs = get_all_summaries_history()
    
    if not history_logs:
        st.info("No saved summaries found in database. Once you summarize a document, it will appear here.")
    else:
        # Layout: Split into sidebar-like table selection and detail viewer
        history_col_left, history_col_right = st.columns([5, 7])
        
        selected_record_id = None
        
        with history_col_left:
            st.markdown("##### Select History Log")
            # Render a list of options with descriptive names
            options_dict = {}
            for row in history_logs:
                # Format string
                size_kb = row['file_size'] / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
                label = f"{row['filename']} ({row['summary_type']}) - {row['created_at'].split()[0]}"
                options_dict[row['id']] = label
                
            selected_record_id = st.radio(
                "Select a record to load:",
                options=list(options_dict.keys()),
                format_func=lambda x: options_dict[x]
            )
            
            # Action: Delete record button
            if selected_record_id:
                st.markdown("<br>", unsafe_allow_html=True)
                delete_btn = st.button("🗑️ Delete Selected History Log", type="secondary")
                if delete_btn:
                    deleted = delete_summary_by_id(selected_record_id)
                    if deleted:
                        st.success("Successfully deleted record.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to delete record.")
                        
        with history_col_right:
            if selected_record_id:
                detailed_record = get_summary_by_id(selected_record_id)
                if detailed_record:
                    st.markdown(f'<span class="badge">{detailed_record["summary_type"]}</span>', unsafe_allow_html=True)
                    st.markdown(f"#### 📁 {detailed_record['filename']}")
                    st.caption(f"**Pages:** {detailed_record['page_count']} | **Created:** {detailed_record['created_at']}")
                    
                    st.markdown("""
                    <div class="glass-panel" style="max-height: 450px; overflow-y: auto;">
                    """, unsafe_allow_html=True)
                    st.markdown(detailed_record["final_summary"])
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Download actions for history
                    st.markdown("##### 📥 Export History Log")
                    btn_h1, btn_h2, btn_h3 = st.columns(3)
                    
                    # Export Text
                    with btn_h1:
                        st.download_button(
                            label="📄 Download Text (.txt)",
                            data=detailed_record["final_summary"],
                            file_name=f"summary_{detailed_record['filename'].replace('.pdf', '')}_{detailed_record['summary_type'].lower().replace(' ', '_')}.txt",
                            mime="text/plain",
                            key=f"dl_txt_{detailed_record['id']}",
                            use_container_width=True
                        )
                        
                    # Export Markdown
                    with btn_h2:
                        st.download_button(
                            label="🗂️ Download Markdown (.md)",
                            data=detailed_record["final_summary"],
                            file_name=f"summary_{detailed_record['filename'].replace('.pdf', '')}_{detailed_record['summary_type'].lower().replace(' ', '_')}.md",
                            mime="text/markdown",
                            key=f"dl_md_{detailed_record['id']}",
                            use_container_width=True
                        )
                        
                    # Export PDF
                    with btn_h3:
                        pdf_stream = generate_pdf_report(detailed_record["filename"], detailed_record["summary_type"], detailed_record["final_summary"])
                        st.download_button(
                            label="📊 Download Styled PDF (.pdf)",
                            data=pdf_stream.getvalue(),
                            file_name=f"summary_{detailed_record['filename'].replace('.pdf', '')}_{detailed_record['summary_type'].lower().replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_{detailed_record['id']}",
                            use_container_width=True
                        )
                        
                    # Expand intermediate summaries
                    if detailed_record.get("intermediate_summaries"):
                        with st.expander("🧩 Intermediate Summaries (Map Phase Outputs)"):
                            for idx, s_item in enumerate(detailed_record["intermediate_summaries"]):
                                st.markdown(f"**Chunk {idx + 1} Summary:**")
                                st.markdown(s_item)
                                st.markdown("---")

# ---------------------------------------------
# TAB 3: SYSTEM DIAGNOSTICS
# ---------------------------------------------
with tab_diagnostics:
    st.markdown("### 🔧 Studio System Diagnostics")
    st.caption("Verify configuration parameters, database status, and AI provider connectivity.")
    
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
        st.markdown("##### API Configuration Status")
        active_provider = st.session_state.get("ai_provider", "auto")
        st.write(f"**Active provider:** `{provider_labels[active_provider]}`")

        gemini_key = get_api_key()
        groq_key = get_groq_api_key()
        cohere_key = get_cohere_api_key()

        st.write(f"**Gemini model:** `{get_model_name()}`")
        st.write("🔑 Gemini:", "**Configured** ✅" if gemini_key and gemini_key != "your_gemini_api_key_here" else "**Not configured** ⚠️")
        st.write(f"**Groq model:** `{get_groq_model_name()}`")
        st.write("🔑 Groq:", "**Configured** ✅" if groq_key and groq_key != "your_groq_api_key_here" else "**Not configured** ⚠️")
        st.write("🔑 Cohere:", "**Configured** ✅" if cohere_key and cohere_key != "your_cohere_api_key_here" else "**Not configured** ⚠️")
            
        test_conn_btn = st.button(f"🔍 Run ping test ({provider_labels[active_provider]})")
        if test_conn_btn:
            with st.spinner("Pinging API endpoint..."):
                ping_res = verify_api_connection(provider=active_provider)
            if ping_res["success"]:
                st.success(f"✅ Connection successful! Recieved: *'{ping_res['response']}'*")
                st.info(f"Active Model Endpoint: `{ping_res.get('model_used')}`")
                if "warning" in ping_res:
                    st.warning(ping_res["warning"])
            else:
                st.error(f"❌ Connection failed: {ping_res['error']}")
                
    with col_d2:
        st.markdown("##### Local Database Stats")
        try:
            total_records = len(history_logs)
            st.metric(label="Saved Records in Database", value=total_records)
            db_file_size = 0
            from database.db_manager import DB_PATH
            if os.path.exists(DB_PATH):
                db_file_size = os.path.getsize(DB_PATH) / 1024
            st.write(f"**Database File Location:** `{DB_PATH}`")
            st.write(f"**Database File Size:** `{db_file_size:.2f} KB`")
        except Exception as e:
            st.error(f"Failed to load database status: {str(e)}")
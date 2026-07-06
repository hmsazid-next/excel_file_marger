{\rtf1\ansi\ansicpg1252\cocoartf2870
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import streamlit as st\
import pandas as pd\
import io\
import re\
import difflib\
import chardet\
\
# --- Page Config ---\
st.set_page_config(page_title="PSP Statement Merger", page_icon="\uc0\u55357 \u56499 ", layout="wide")\
st.title("\uc0\u55357 \u56499  PSP Statement Merger & Data Cleaner")\
st.markdown("Upload multiple CSV/Excel PSP statements. The platform detects structural inconsistencies, lets you map columns, and merges them seamlessly. **Data is processed in memory and not stored.**")\
\
# --- Initialize Session State ---\
if 'files_data' not in st.session_state:\
    st.session_state.files_data = \{\} # Stores \{filename: dataframe\}\
if 'master_columns' not in st.session_state:\
    st.session_state.master_columns = []\
\
# --- Helper Functions ---\
def detect_encoding(file):\
    raw_data = file.read()\
    result = chardet.detect(raw_data)\
    file.seek(0)\
    return result['encoding']\
\
def clean_currency(val):\
    if pd.isna(val): return 0.0\
    if isinstance(val, (int, float)): return float(val)\
    val = str(val).replace(',', '')\
    val = re.sub(r'[^\\d.-]', '', val)\
    try: return float(val)\
    except ValueError: return 0.0\
\
def fuzzy_match_headers(headers_list, threshold=0.8):\
    """Clusters similar headers together to suggest mappings."""\
    unique_headers = list(set(headers_list))\
    mapping = \{\}\
    for h in unique_headers:\
        if h in mapping: continue\
        matches = difflib.get_close_matches(h, unique_headers, n=5, cutoff=threshold)\
        for m in matches:\
            mapping[m] = h\
    return mapping\
\
# --- Step 1: File Upload ---\
st.header("1. Upload Statements")\
uploaded_files = st.file_uploader("Drop CSV or Excel files here", type=['csv', 'xlsx', 'xls'], accept_multiple_files=True)\
\
if uploaded_files:\
    for file in uploaded_files:\
        if file.name not in st.session_state.files_data:\
            try:\
                if file.name.endswith('.csv'):\
                    enc = detect_encoding(file)\
                    df = pd.read_csv(file, encoding=enc)\
                else:\
                    df = pd.read_excel(file)\
                \
                # Basic cleaning: Drop fully empty rows\
                df.dropna(how='all', inplace=True)\
                st.session_state.files_data[file.name] = df\
            except Exception as e:\
                st.error(f"Error reading \{file.name\}: \{e\}")\
\
if st.session_state.files_data:\
    st.success(f"Successfully loaded \{len(st.session_state.files_data)\} files.")\
    \
    # --- Step 2: Inconsistency Detection ---\
    st.header("2. Inconsistency Detection & Mapping")\
    \
    all_headers = []\
    for fname, df in st.session_state.files_data.items():\
        all_headers.extend(df.columns.tolist())\
        \
    # Generate fuzzy mapping suggestions\
    suggested_mapping = fuzzy_match_headers(all_headers)\
    unique_headers = sorted(list(set(all_headers)))\
    \
    with st.expander("\uc0\u55357 \u56589  View Detected Inconsistencies", expanded=True):\
        col1, col2 = st.columns(2)\
        with col1:\
            st.write("**Total unique headers found across all files:**", len(unique_headers))\
        with col2:\
            st.write("**Files processed:**", len(st.session_state.files_data))\
            \
        # Display headers per file for comparison\
        header_data = []\
        for fname, df in st.session_state.files_data.items():\
            header_data.append(\{"File": fname, "Columns": ", ".join(df.columns.tolist()), "Column Count": len(df.columns)\})\
        st.dataframe(pd.DataFrame(header_data), use_container_width=True)\
\
    # --- Step 3: Column Reconciliation UI ---\
    st.subheader("Map Columns to a Standard Structure")\
    st.markdown("Select the master columns to include in the final merge. The system will auto-map similar columns (e.g., 'Transaction ID' and 'txn_id'). You can manually adjust mappings.")\
    \
    selected_master_cols = st.multiselect("Select Master Columns for Final Output", options=unique_headers)\
    \
    mapping_dict = \{\}\
    if selected_master_cols:\
        st.write("#### Mapping Configuration")\
        for master_col in selected_master_cols:\
            st.markdown(f"**Master Column:** `\{master_col\}`")\
            # Find best suggestion\
            suggestion = difflib.get_close_matches(master_col, unique_headers, n=1, cutoff=0.6)\
            default_idx = unique_headers.index(suggestion[0]) if suggestion else 0\
            \
            # Create a dropdown for each file to map to this master column\
            cols = st.columns(len(st.session_state.files_data))\
            for idx, (fname, df) in enumerate(st.session_state.files_data.items()):\
                with cols[idx]:\
                    st.caption(f"**\{fname\}**")\
                    file_cols = ["-- Ignore --"] + df.columns.tolist()\
                    default_file_idx = 0\
                    if master_col in df.columns:\
                        default_file_idx = file_cols.index(master_col)\
                    elif suggestion and suggestion[0] in df.columns:\
                        default_file_idx = file_cols.index(suggestion[0])\
                        \
                    selected = st.selectbox(f"Map to \{master_col\}", file_cols, index=default_file_idx, key=f"\{fname\}_\{master_col\}")\
                    if selected != "-- Ignore --":\
                        mapping_dict[(fname, master_col)] = selected\
\
    # --- Step 4: Merge Strategy ---\
    st.header("3. Merge & Clean Data")\
    merge_type = st.selectbox("Select Merge Type", ["Append (Stack Rows)", "Join (Merge on Key)"])\
    \
    clean_amounts = st.checkbox("Auto-clean Currency/Amount columns (remove $, \'80, commas)", value=True)\
    clean_dates = st.checkbox("Auto-parse Dates to YYYY-MM-DD", value=True)\
    drop_footer_totals = st.checkbox("Attempt to drop 'Total' summary rows", value=True)\
\
    if st.button("\uc0\u55357 \u56960  Process and Merge Data", type="primary"):\
        merged_df = pd.DataFrame()\
        \
        if merge_type == "Append (Stack Rows)":\
            # Build list of mapped dataframes\
            mapped_dfs = []\
            for fname, df in st.session_state.files_data.items():\
                temp_df = pd.DataFrame()\
                for master_col in selected_master_cols:\
                    source_col = mapping_dict.get((fname, master_col))\
                    if source_col and source_col in df.columns:\
                        temp_df[master_col] = df[source_col]\
                    else:\
                        temp_df[master_col] = None\
                temp_df['Source_File'] = fname\
                mapped_dfs.append(temp_df)\
            \
            if mapped_dfs:\
                merged_df = pd.concat(mapped_dfs, ignore_index=True)\
        \
        elif merge_type == "Join (Merge on Key)":\
            st.warning("Join requires selecting a key column. For this demo, we append.")\
            # Append fallback for simplicity in this script\
            mapped_dfs = []\
            for fname, df in st.session_state.files_data.items():\
                temp_df = pd.DataFrame()\
                for master_col in selected_master_cols:\
                    source_col = mapping_dict.get((fname, master_col))\
                    if source_col and source_col in df.columns:\
                        temp_df[master_col] = df[source_col]\
                    else:\
                        temp_df[master_col] = None\
                mapped_dfs.append(temp_df)\
            if mapped_dfs:\
                merged_df = pd.concat(mapped_dfs, ignore_index=True)\
\
        # Apply Cleaning Logic\
        if not merged_df.empty:\
            if drop_footer_totals:\
                # Drop rows where the first column contains 'total' (case insensitive)\
                first_col = merged_df.columns[0]\
                merged_df = merged_df[~merged_df[first_col].astype(str).str.contains('total', case=False, na=False)]\
            \
            if clean_dates:\
                for col in merged_df.columns:\
                    if 'date' in col.lower() or 'time' in col.lower():\
                        merged_df[col] = pd.to_datetime(merged_df[col], errors='coerce').dt.strftime('%Y-%m-%d')\
            \
            if clean_amounts:\
                for col in merged_df.columns:\
                    if 'amount' in col.lower() or 'fee' in col.lower() or 'total' in col.lower():\
                        merged_df[col] = merged_df[col].apply(clean_currency)\
\
            st.session_state.merged_df = merged_df\
            st.success("Merge and Cleaning Complete!")\
\
    # --- Step 5: Preview & Export ---\
    if 'merged_df' in st.session_state and not st.session_state.merged_df.empty:\
        st.header("4. Preview & Export")\
        \
        df_final = st.session_state.merged_df\
        st.write(f"**Final Row Count:** \{len(df_final)\} | **Final Column Count:** \{len(df_final.columns)\}")\
        \
        st.dataframe(df_final.head(100), use_container_width=True)\
        \
        st.subheader("Download Merged File")\
        export_format = st.radio("Select Export Format", ["Excel (.xlsx)", "CSV (.csv)"], horizontal=True)\
        \
        if export_format == "Excel (.xlsx)":\
            output = io.BytesIO()\
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:\
                df_final.to_excel(writer, index=False, sheet_name='Merged_PSP_Data')\
            st.download_button(\
                label="\uc0\u55357 \u56549  Download Excel",\
                data=output.getvalue(),\
                file_name="merged_psp_statements.xlsx",\
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"\
            )\
        else:\
            csv = df_final.to_csv(index=False).encode('utf-8')\
            st.download_button(\
                label="\uc0\u55357 \u56549  Download CSV",\
                data=csv,\
                file_name="merged_psp_statements.csv",\
                mime='text/csv'\
            )}
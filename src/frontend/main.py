import sys
import os
import streamlit as st

# Add the project root to Python path for module imports
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


st.set_page_config(page_title="Auto OMOP Mapper", layout="wide", page_icon="🗺️")

import_page = st.Page(
    "./ui/import_data.py",
    url_path="import",
    title="Import Data",
    icon=":material/upload:",
)
search_page = st.Page(
    "./ui/search.py", url_path="search", title="Search", icon=":material/search:"
)
mapping_page = st.Page(
    "./ui/map.py",
    url_path="mapping",
    title="Map Concepts",
    icon=":material/table_view:",
)
commit_page = st.Page(
    "./ui/commit.py",
    url_path="commit",
    title="Check and Commit",
    icon=":material/data_check:",
)
config_page = st.Page(
    "./ui/config.py",
    url_path="config",
    title="Configuration",
    icon=":material/settings:",
)

pg = st.navigation([import_page, search_page, mapping_page, commit_page, config_page])
pg.run()

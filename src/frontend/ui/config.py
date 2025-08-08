import streamlit as st
from src.backend.config_manager import get_config_manager


def render_config_page():
    st.title("⚙️ Configuration")

    st.markdown("""
    Configure the LLM and embedding models used by the Auto OMOP Mapper.
    
    **Important**: Changing embedding model or dimensions will require creating a new vector collection 
    and re-embedding all concepts.
    """)

    config_manager = get_config_manager()
    current_config = config_manager.get_config()

    st.divider()

    # Current Configuration Display
    with st.expander("📋 Current Configuration", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Vector Store:**")
            st.write(f"- Collection: `{current_config['vector_store']['name']}`")
            st.write(
                f"- Embedding Model: `{current_config['vector_store']['embeddings']}`"
            )
            st.write(f"- Dimensions: `{current_config['vector_store']['dims']}`")
            st.write(f"- URL: `{current_config['vector_store']['url']}`")

        with col2:
            st.write("**LLM Reranker:**")
            st.write(f"- Model: `{current_config['reranker']['model']}`")

    st.divider()

    # Configuration Form
    st.subheader("🔧 Update Configuration")

    with st.form("config_form"):
        col1, col2 = st.columns(2)

        with col1:
            st.write("### LLM Model")
            llm_models = config_manager.get_llm_models()
            current_llm = current_config["reranker"]["model"]

            new_llm_model = st.selectbox(
                "Select LLM Model",
                options=llm_models,
                index=llm_models.index(current_llm) if current_llm in llm_models else 0,
                help="Model used for concept reranking and mapping suggestions",
            )

            st.write("### Vector Store Settings")
            current_url = current_config["vector_store"]["url"]
            new_qdrant_url = st.text_input(
                "Qdrant URL",
                value=current_url,
                help="URL of your Qdrant vector database instance",
            )

        with col2:
            st.write("### Embedding Model")
            embedding_models = config_manager.get_embedding_models()
            current_embedding = current_config["vector_store"]["embeddings"]
            current_dims = current_config["vector_store"]["dims"]

            new_embedding_model = st.selectbox(
                "Select Embedding Model",
                options=list(embedding_models.keys()),
                index=list(embedding_models.keys()).index(current_embedding)
                if current_embedding in embedding_models
                else 0,
                help="Model used to create vector embeddings for similarity search",
            )

            # Dimensions selection
            available_dims = [512, 1024, 1536, 2048, 3072]

            new_dims = st.selectbox(
                "Select Dimensions",
                options=available_dims,
                index=available_dims.index(current_dims)
                if current_dims in available_dims
                else 0,
                help=f"Higher dimensions provide better accuracy but are slower. Max for {new_embedding_model}: {max(available_dims)}",
            )

            st.warning("""
            ⚠️ **Note if changing embedding configuration!**
            
            This will require:
            1. Creating a new vector collection
            2. Re-embedding all concepts (this may take time and cost money)
            3. Previous embeddings will be preserved but not used
            """)

        # Check if embedding config changed
        embedding_changed = (
            new_embedding_model != current_config["vector_store"]["embeddings"]
            or new_dims != current_config["vector_store"]["dims"]
        )

        # Check if URL changed
        url_changed = new_qdrant_url != current_config["vector_store"]["url"]

        if embedding_changed:
            new_collection_name = config_manager.create_new_collection_name(
                new_embedding_model, new_dims
            )
            st.write(f"**New collection name:** `{new_collection_name}`")

            confirm_embedding_change = st.checkbox(
                "I understand that changing embedding settings requires re-embedding all concepts",
                key="confirm_embedding",
            )
        else:
            confirm_embedding_change = True
            new_collection_name = current_config["vector_store"]["name"]

        st.divider()

        # Submit buttons
        col1, col2, _ = st.columns([1, 1, 2])

        submitted = col1.form_submit_button(
            "💾 Save Configuration",
            type="primary",
            disabled=embedding_changed and not confirm_embedding_change,
        )

        if col2.form_submit_button("🔄 Reset to Defaults"):
            # Reset to file defaults
            st.rerun()

    if submitted:
        try:
            # Prepare updates
            updates = {}

            # Always update LLM model
            if new_llm_model != current_config["reranker"]["model"]:
                updates["reranker.model"] = new_llm_model

            # Update Qdrant URL if changed
            if url_changed:
                updates["vector_store.url"] = new_qdrant_url

            # Update embedding config if changed
            if embedding_changed:
                updates["vector_store.embeddings"] = new_embedding_model
                updates["vector_store.dims"] = new_dims
                updates["vector_store.name"] = new_collection_name

            if updates:
                # Save configuration
                config_manager.update_config(updates)

                st.success("✅ Configuration updated successfully!")

                if embedding_changed:
                    st.info("""
                    🔄 **Next Steps:**
                    1. Go to "Import Data" → "Embedding Management"
                    2. Click "Embed Standard Concepts" to populate the new collection
                    3. The new embedding model will be used automatically
                    """)

                # Clear cached resources
                st.cache_resource.clear()
                config_manager.clear_config_info_cache()

                st.balloons()

            else:
                st.info("No changes detected in configuration.")

        except Exception as e:
            st.error(f"❌ Error updating configuration: {str(e)}")


render_config_page()

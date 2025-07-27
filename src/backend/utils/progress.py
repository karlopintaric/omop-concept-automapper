import streamlit as st
from src.backend.utils.logging import logger


class StreamlitProgressTracker:
    def __init__(
        self,
        total_count: int,
        message_template: str = "Embedded {current}/{total} concepts...",
    ):
        self.total_count = total_count
        self.current_count = 0
        self.message_template = message_template

        try:
            self.progress_bar = st.progress(0)
            self.status_text = st.empty()
            self.enabled = True
        except Exception:
            logger.error("Error initializing Streamlit progress", exc_info=True)
            self.progress_bar = None
            self.status_text = None
            self.enabled = False

    def update(self, increment: int, custom_message: str = None):
        if not self.enabled or not self.progress_bar:
            return

        self.current_count += increment
        progress = min(self.current_count / self.total_count, 1.0)

        self.progress_bar.progress(progress)

        message = (
            custom_message
            if custom_message is not None
            else self.message_template.format(
                current=self.current_count, total=self.total_count
            )
        )

        self.status_text.text(message)

    def complete(self, final_message: str = "Embedding complete!"):
        if self.enabled and self.status_text:
            self.status_text.text(final_message)

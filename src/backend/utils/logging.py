import logging
import sys
import streamlit as st

logger = logging.getLogger("streamlit_app")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)


def log_and_show_error(user_message: str, exc: Exception):
    """
    Log the full exception with traceback and show a user-friendly error in Streamlit.

    Args:
        user_message: A clear message to show the user.
        exc: The caught exception instance.
    """
    logger.error(user_message, exc_info=True)
    st.error(f"{user_message}: {exc}")


def log_and_show_success(message: str):
    """
    Log an info-level success message and show a Streamlit success banner.

    Args:
        message: The message to log and display to the user.
    """
    logger.info(message)
    st.success(message)


def log_and_show_warning(message: str):
    """
    Log a warning-level message and show a Streamlit warning banner.

    Args:
        message: The warning message to log and display.
    """
    logger.warning(message)
    st.warning(message)

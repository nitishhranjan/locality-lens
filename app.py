import streamlit as st
from config.config import APP_NAME

def main():
    st.set_page_config(page_title=APP_NAME, page_icon="🏘️")
    st.title(f"Welcome to {APP_NAME}")
    st.write("Modular template initialized successfully!")

if __name__ == "__main__":
    main()

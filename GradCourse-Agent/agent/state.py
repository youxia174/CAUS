import streamlit as st


def init_state():
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("plan", None)
    st.session_state.setdefault("trace", [])
    st.session_state.setdefault("excluded_codes", [])


def add_message(role, content):
    st.session_state.messages.append({"role": role, "content": content})

import streamlit as st
import time

# --- Section 1 ---
st.header("Section 1")
st.write("Your content here.")

# --- Section 2 ---
st.header("Section 2")
st.write("More content here.")

# --- Section 3: Camera ---
st.header("Section 3: Camera Demo")

if 'camera_on' not in st.session_state:
    st.session_state['camera_on'] = False

if st.button("Turn on camera for 10 seconds"):
    st.session_state['camera_on'] = True
    st.session_state['start_time'] = time.time()

if st.session_state.get('camera_on', False):
    picture = st.camera_input("Take a picture!")
    elapsed = time.time() - st.session_state['start_time']
    if elapsed >= 10:
        st.session_state['camera_on'] = False
        st.success("Camera off! 10 seconds passed.")

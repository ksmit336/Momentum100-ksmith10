import streamlit as st
st.set_page_config(page_title="Momentum 100")
st.title("Momentum 100 - Test")
st.write("If you see this and a button below, the app is working!")

if st.button("Calculate Momentum 100 - TEST", type="primary"):
    st.success("Button works! Now we can add the full logic back.")
    st.write("Your app URL is live.")

st.write("GitHub files loaded OK")

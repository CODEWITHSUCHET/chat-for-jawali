import streamlit as st

st.set_page_config(page_title="Secrets Debugger", page_icon="🕵️")
st.title("🕵️ Secrets Debugger")

st.info("This is a temporary app to check if secrets are loaded correctly.")

st.header("Checking Secrets...")

# Check for the Turso Database URL
if "TURSO_DB_URL" in st.secrets:
    st.success("✅ Found TURSO_DB_URL!")
    st.write("The URL is:", st.secrets["TURSO_DB_URL"])
else:
    st.error("❌ TURSO_DB_URL secret is MISSING!")

# Check for the Turso Auth Token
if "TURSO_DB_AUTH_TOKEN" in st.secrets:
    st.success("✅ Found TURSO_DB_AUTH_TOKEN!")
    # For security, we only show the length, not the full token
    token_length = len(st.secrets["TURSO_DB_AUTH_TOKEN"])
    st.write(f"The Token is present and its length is: {token_length}")
else:
    st.error("❌ TURSO_DB_AUTH_TOKEN secret is MISSING!")

# Check for the Admin Password
if "ADMIN_PASS" in st.secrets:
    st.success("✅ Found ADMIN_PASS!")
else:
    st.error("❌ ADMIN_PASS secret is MISSING!")

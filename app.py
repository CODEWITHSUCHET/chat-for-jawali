import streamlit as st
import os
import requests
import bleach
from datetime import datetime, timedelta
from libsql_experimental import connect

# --- Setup DB ---
# Connects to your Turso cloud database
try:
    conn = connect(
        st.secrets["TURSO_DB_URL"],
        auth_token=st.secrets["TURSO_DB_AUTH_TOKEN"]
    )
    c = conn.cursor()
    
    # Run setup queries (user_ips table is removed)
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            text TEXT,
            timestamp TEXT,
            ip TEXT
        )
    ''')
    conn.commit()
    st.sidebar.success("Connected to Cloud DB")

except Exception as e:
    st.error(f"Failed to connect to the database: {e}")
    st.stop()

# --- (INDIA VALA TIME ) ---
def get_current_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- Get user IP ---
def get_ip():
    try:
        return requests.get('https://api64.ipify.org', timeout=5).text
    except requests.exceptions.RequestException:
        return "127.0.0.1"

# --- Admin ---
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", st.secrets.get("ADMIN_PASS"))
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# --- Pagination State ---
if "page" not in st.session_state:
    st.session_state.page = 0

# --- Streamlit Page ---
st.set_page_config(page_title="Chat for Jawali", page_icon="💬")
st.title("💬 Chat for Jawali")

# --- Admin Sidebar ---
with st.sidebar:
    st.header("Admin Login")
    password = st.text_input("Enter admin password", type="password", key="admin_password")
    if st.button("Login"):
        if password == ADMIN_PASSWORD:
            st.session_state.admin_logged_in = True
            st.rerun()
        else:
            st.error("Wrong password")
    if st.session_state.admin_logged_in:
        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

# --- User Info ---
with st.form("chat_form", clear_on_submit=True):
    name = st.text_input("Your Name")
    text = st.text_area("Message")
    submitted = st.form_submit_button("Send")

if submitted:
    # The check for the daily limit has been removed.
    if not name.strip() or not text.strip():
        st.warning("Name and message cannot be empty.")
    else:
        user_ip = get_ip()
        clean_name = bleach.clean(name.strip())
        clean_text = bleach.clean(text.strip())
        timestamp = get_current_ist_time().strftime('%Y-%m-%d %H:%M:%S')

        # We removed the query to the user_ips table.
        c.execute("INSERT INTO messages (name, text, timestamp, ip) VALUES (?, ?, ?, ?)",
                      (clean_name, clean_text, timestamp, user_ip))
        conn.commit()
        st.success("Message sent!")
        st.rerun()

# --- Display Messages with Pagination ---
st.markdown("### 📜 Chat History")
MESSAGES_PER_PAGE = 25
offset = st.session_state.page * MESSAGES_PER_PAGE

messages = c.execute(
    "SELECT name, text, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
    (MESSAGES_PER_PAGE, offset)
).fetchall()

if not messages and st.session_state.page == 0:
    st.info("No messages yet. Be the first to post!")
else:
    for name, text, timestamp in messages:
        st.markdown(f"**{name}**: {text} _(at {timestamp})_")

# Pagination buttons
col1, col2 = st.columns(2)
with col1:
    if st.session_state.page > 0:
        if st.button("⬅️ Previous Page"):
            st.session_state.page -= 1
            st.rerun()
with col2:
    c.execute("SELECT COUNT(id) FROM messages")
    # Add a check to ensure fetchone() does not return None
    count_result = c.fetchone()
    total_messages = count_result[0] if count_result else 0
    if total_messages > (st.session_state.page + 1) * MESSAGES_PER_PAGE:
        if st.button("Next Page ➡️"):
            st.session_state.page += 1
            st.rerun()

# --- Admin Tools ---
if st.session_state.admin_logged_in:
    st.markdown("---")
    st.markdown("### 👮 Admin Tools")

    st.subheader("Delete Individual Messages")
    admin_messages = c.execute(
        "SELECT id, name, text, timestamp, ip FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
        (MESSAGES_PER_PAGE, offset)
    ).fetchall()

    for msg_id, name, text, timestamp, ip in admin_messages:
        with st.expander(f"ID: {msg_id} | User: {name} | IP: {ip}"):
            st.write(f"_{timestamp}_")
            st.text(text)
            if st.button(f"Delete Message ID {msg_id}", key=f"delete_{msg_id}"):
                c.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                conn.commit()
                st.success(f"Deleted message ID {msg_id}")
                st.rerun()

    st.subheader("🚨 Danger Zone")
    if st.button("Delete ALL Messages"):
        c.execute("DELETE FROM messages")
        # The user_ips table is no longer used, but we can leave this for safety
        c.execute("DELETE FROM user_ips") 
        conn.commit()
        st.success("All messages have been deleted.")
        st.rerun()

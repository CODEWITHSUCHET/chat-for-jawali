import streamlit as st
import os
import requests
import bleach
from datetime import datetime, timedelta
import libsql_client

# --- Setup DB ---
# Connects to your Turso cloud database using secrets
try:
    db_url = st.secrets["TURSO_DB_URL"]
    db_token = st.secrets["TURSO_DB_AUTH_TOKEN"]
    
    client = libsql_client.create_client(url=db_url, auth_token=db_token)
    
    # Run setup queries
    client.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            text TEXT,
            timestamp TEXT,
            ip TEXT
        )
    ''')
    client.execute('''
        CREATE TABLE IF NOT EXISTS user_ips (
            ip TEXT PRIMARY KEY,
            last_message_date TEXT
        )
    ''')
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
st.set_page_config(page_title="Chat for Jawali", page_icon="💬") # <-- CHANGED
st.title("💬 Chat for Jawali") # <-- CHANGED

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
    user_ip = get_ip()
    today = get_current_ist_time().strftime('%Y-%m-%d')
    
    # Check message limit
    rs = client.execute("SELECT last_message_date FROM user_ips WHERE ip = ?", (user_ip,))
    row = rs.rows[0] if rs.rows else None
    already_sent_today = row and row[0] == today

    if not name.strip() or not text.strip():
        st.warning("Name and message cannot be empty.")
    elif already_sent_today:
        st.error("You can only send 1 message per day from this IP.")
    else:
        clean_name = bleach.clean(name.strip())
        clean_text = bleach.clean(text.strip())
        timestamp = get_current_ist_time().strftime('%Y-%m-%d %H:%M:%S')

        client.execute("INSERT INTO messages (name, text, timestamp, ip) VALUES (?, ?, ?, ?)",
                      (clean_name, clean_text, timestamp, user_ip))
        client.execute("INSERT OR REPLACE INTO user_ips (ip, last_message_date) VALUES (?, ?)",
                      (user_ip, today))
        st.success("Message sent!")

# --- Display Messages with Pagination ---
st.markdown("### 📜 Chat History")
MESSAGES_PER_PAGE = 25
offset = st.session_state.page * MESSAGES_PER_PAGE

rs = client.execute(
    "SELECT name, text, timestamp FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
    (MESSAGES_PER_PAGE, offset)
)
messages = rs.rows

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
    rs = client.execute("SELECT COUNT(id) FROM messages")
    total_messages = rs.rows[0][0] if rs.rows else 0
    if total_messages > (st.session_state.page + 1) * MESSAGES_PER_PAGE:
        if st.button("Next Page ➡️"):
            st.session_state.page += 1
            st.rerun()

# --- Admin Tools ---
if st.session_state.admin_logged_in:
    st.markdown("---")
    st.markdown("### 👮 Admin Tools")

    st.subheader("Delete Individual Messages")
    rs_admin = client.execute(
        "SELECT id, name, text, timestamp, ip FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
        (MESSAGES_PER_PAGE, offset)
    )
    admin_messages = rs_admin.rows

    for msg_id, name, text, timestamp, ip in admin_messages:
        with st.expander(f"ID: {msg_id} | User: {name} | IP: {ip}"):
            st.write(f"_{timestamp}_")
            st.text(text)
            if st.button(f"Delete Message ID {msg_id}", key=f"delete_{msg_id}"):
                client.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                st.success(f"Deleted message ID {msg_id}")
                st.rerun()

    st.subheader("🚨 Danger Zone")
    if st.button("Delete ALL Messages"):
        client.execute("DELETE FROM messages")
        client.execute("DELETE FROM user_ips")
        st.success("All messages and IP records have been deleted.")
        st.rerun()
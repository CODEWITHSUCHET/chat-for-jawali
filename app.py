import streamlit as st
import os
import requests
import bleach
from datetime import datetime, timedelta
from libsql_experimental import connect
import urllib.parse # Import for URL encoding

# --- DESIGN AND STYLING (CSS) ---
st.markdown("""
<style>
/* Main app background */
[data-testid="stAppViewContainer"] {
    background-image: url("https://i.pinimg.com/736x/8c/98/99/8c98994518b575bfd8c949e91d20548b.jpg");
    background-size: cover;
}
/* Make the main content area slightly transparent */
.main .block-container {
    background-color: rgba(255, 255, 255, 0.9); /* White with 90% opacity */
    border-radius: 20px;
    padding: 2rem;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
/* Individual message bubble with a more distinct shape */
.chat-bubble {
    background-color: #ffffff; /* White background for bubbles */
    border-radius: 15px;
    padding: 12px 18px;
    max-width: 80%;
    align-self: flex-start;
    word-wrap: break-word;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    border: 1px solid #e9e9e9;
}
/* User avatar image */
.chat-avatar {
    width: 45px;
    height: 45px;
    border-radius: 50%;
    margin-right: 12px;
    border: 2px solid #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
/* Row containing avatar and bubble */
.chat-row {
    display: flex;
    align-items: flex-start;
    margin-bottom: 15px;
}
/* User name style */
.chat-name {
    font-weight: bold;
    font-size: 1rem;
    margin-bottom: 4px;
    color: #0d6efd;
}
/* Timestamp style - subtle and at the bottom */
.chat-timestamp {
    font-size: 0.75rem;
    color: #6c757d;
    text-align: right;
    margin-top: 8px;
}
/* Footer style */
.footer {
    text-align: center;
    padding-top: 2rem;
    color: gray;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)


# --- Setup DB ---
try:
    conn = connect(
        st.secrets["TURSO_DB_URL"],
        auth_token=st.secrets["TURSO_DB_AUTH_TOKEN"]
    )
    c = conn.cursor()
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

# --- Functions ---
def get_current_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_ip():
    try:
        return requests.get('https://api64.ipify.org', timeout=5).text
    except requests.exceptions.RequestException:
        return "127.0.0.1"

# --- Session State ---
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "page" not in st.session_state:
    st.session_state.page = 0

# --- Streamlit Page ---
st.set_page_config(page_title="Chat for Jawali", page_icon="💬")

# --- Admin Sidebar ---
with st.sidebar:
    st.header("Admin Login")
    password = st.text_input("Enter admin password", type="password", key="admin_password")
    if st.button("Login"):
        if password == st.secrets.get("ADMIN_PASS"):
            st.session_state.admin_logged_in = True
            st.rerun()
        else:
            st.error("Wrong password")
    if st.session_state.admin_logged_in:
        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

# --- Main App Area ---
st.title("💬 Chat for Jawali")
st.write("") 

# --- User Info Form ---
with st.form("chat_form", clear_on_submit=True):
    name = st.text_input("Your Name", placeholder="Enter your name...")
    text = st.text_area("Message", placeholder="Type your message here...")
    submitted = st.form_submit_button("Send Message")

if submitted:
    if not name.strip() or not text.strip():
        st.warning("Name and message cannot be empty.")
    else:
        user_ip = get_ip()
        clean_name = bleach.clean(name.strip())
        clean_text = bleach.clean(text.strip())
        timestamp = get_current_ist_time().strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT INTO messages (name, text, timestamp, ip) VALUES (?, ?, ?, ?)",
                      (clean_name, clean_text, timestamp, user_ip))
        conn.commit()
        st.rerun()

st.divider()

# --- Display Messages with new design ---
st.markdown("### Chat History")
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
        # ** NEW ** Create a dynamic avatar URL based on the user's name
        name_for_avatar = urllib.parse.quote_plus(name)
        avatar_url = f"https://ui-avatars.com/api/?name={name_for_avatar}&background=random&color=fff"
        
        chat_html = f"""
        <div class="chat-row">
            <img src="{avatar_url}" class="chat-avatar">
            <div class="chat-bubble">
                <div class="chat-name">{name}</div>
                <div>{text}</div>
                <div class="chat-timestamp">{timestamp}</div>
            </div>
        </div>
        """
        st.markdown(chat_html, unsafe_allow_html=True)

# --- Pagination ---
st.write("") 
col1, col2 = st.columns(2)
with col1:
    if st.session_state.page > 0:
        if st.button("⬅️ Previous Page"):
            st.session_state.page -= 1
            st.rerun()
with col2:
    c.execute("SELECT COUNT(id) FROM messages")
    count_result = c.fetchone()
    total_messages = count_result[0] if count_result else 0
    if total_messages > (st.session_state.page + 1) * MESSAGES_PER_PAGE:
        if st.button("Next Page ➡️"):
            st.session_state.page += 1
            st.rerun()

# --- NEW FOOTER SECTION ---
st.divider()
st.markdown("<div class='footer'>CODEMONK BY STAYMONK</div>", unsafe_allow_html=True)


# --- Admin Tools ---
if st.session_state.admin_logged_in:
    with st.sidebar:
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
            conn.commit()
            st.success("All messages have been deleted.")
            st.rerun()

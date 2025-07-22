import streamlit as st
import os
import requests
import bleach
from datetime import datetime, timedelta
from libsql_experimental import connect
import pandas as pd  # Import Pandas for data handling
import altair as alt # Import Altair for charting

# --- DESIGN AND STYLING (CSS) ---
st.markdown("""
<style>
/* Center the main content */
.main .block-container {
    max-width: 800px;
    padding-top: 2rem;
    padding-bottom: 2rem;
}
/* Style the title */
h1 {
    text-align: center;
    color: #4A4A4A;
}
/* Style the image/logo */
.stImage {
    margin: auto;
    width: 250px;
}
/* Style the chat history container */
[data-testid="stVerticalBlock"] > [data-testid="stMarkdownContainer"] {
    background-color: #f0f2f6;
    border-radius: 10px;
    padding: 1rem 1.5rem;
    margin-bottom: 1rem;
    border: 1px solid #e6e6e6;
}
/* Style the Send button */
.stButton>button {
    width: 100%;
    border: none;
    background-color: #007bff;
    color: white;
    border-radius: 5px;
}
.stButton>button:hover {
    background-color: #0056b3;
    color: white;
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
st.title("💬 Chat for Jawali")
st.image("1.png") 

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

# --- NEW GRAPHICS SECTION ---
with st.expander("📊 View Chat Activity"):
    try:
        # Query the database to get message counts per day
        query = "SELECT DATE(timestamp) as date, COUNT(id) as message_count FROM messages GROUP BY DATE(timestamp) ORDER BY date"
        activity_df = pd.read_sql_query(query, conn)
        
        if not activity_df.empty:
            st.write("#### Messages Per Day")
            
            # Create a bar chart with Altair
            chart = alt.Chart(activity_df).mark_bar().encode(
                x=alt.X('date:T', title='Date'),
                y=alt.Y('message_count:Q', title='Number of Messages'),
                tooltip=['date:T', 'message_count:Q']
            ).properties(
                title='Daily Message Volume'
            )
            
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Not enough data to display a chart yet.")
            
    except Exception as e:
        st.warning(f"Could not load chart: {e}")


# --- User Info Form ---
with st.form("chat_form", clear_on_submit=True):
    name = st.text_input("Your Name")
    text = st.text_area("Message")
    submitted = st.form_submit_button("Send")

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
        st.success("Message sent!")
        st.rerun()

st.divider()

# --- Display Messages ---
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
        c.execute("DELETE FROM user_ips") 
        conn.commit()
        st.success("All messages have been deleted.")
        st.rerun()

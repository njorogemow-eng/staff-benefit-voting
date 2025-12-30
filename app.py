import gradio as gr
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta

# ================= TIMEZONE (KENYA) =================
KENYA_TZ = timezone(timedelta(hours=3))  # EAT (UTC+3)

# ================= SETTINGS =================
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

VOTING_DEADLINE = datetime(2026, 1, 16, 23, 59, tzinfo=KENYA_TZ)

# ================= DATABASE =================
conn = sqlite3.connect("votes.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS votes (
    member_id TEXT PRIMARY KEY,
    full_name TEXT,
    location TEXT,
    reg_fee TEXT,
    monthly TEXT,
    timestamp TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute("INSERT OR IGNORE INTO settings VALUES ('manual_close', 'false')")
conn.commit()

# ================= MEMBER VALIDATION =================
members_df = pd.read_csv("members.csv")
valid_members = set(members_df["MemberID"].astype(str))

# ================= HELPERS =================
def manual_closed():
    cursor.execute("SELECT value FROM settings WHERE key='manual_close'")
    return cursor.fetchone()[0] == "true"

def voting_open():
    now = datetime.now(KENYA_TZ)
    if manual_closed():
        return False
    return now <= VOTING_DEADLINE

def countdown_text():
    now = datetime.now(KENYA_TZ)
    if now > VOTING_DEADLINE:
        return "⛔ Voting is CLOSED"
    remaining = VOTING_DEADLINE - now
    days = remaining.days
    hours = remaining.seconds // 3600
    return f"⏳ Voting closes in {days} days, {hours} hours (Kenya Time)"

# ================= CORE LOGIC =================
def submit_vote(member_id, full_name, location, reg_fee, monthly):
    if not voting_open():
        return "❌ Voting is closed.", results_table(), chart_plot(), countdown_text()

    if member_id not in valid_members:
        return "❌ Invalid Member ID.", results_table(), chart_plot(), countdown_text()

    cursor.execute("SELECT 1 FROM votes WHERE member_id=?", (member_id,))
    if cursor.fetchone():
        return "❌ You have already voted.", results_table(), chart_plot(), countdown_text()

    cursor.execute(
        "INSERT INTO votes VALUES (?, ?, ?, ?, ?, ?)",
        (member_id, full_name, location, reg_fee, monthly, datetime.now(KENYA_TZ).isoformat())
    )
    conn.commit()

    return "✅ Vote submitted successfully.", results_table(), chart_plot(), countdown_text()

def results_table():
    df = pd.read_sql("SELECT * FROM votes", conn)
    return pd.DataFrame({
        "Item": ["Registration Fee", "Registration Fee", "Monthly Contribution", "Monthly Contribution"],
        "Option": ["Yes", "No", "500 KSH", "1000 KSH"],
        "Votes": [
            (df["reg_fee"] == "Yes").sum(),
            (df["reg_fee"] == "No").sum(),
            (df["monthly"] == "500 KSH").sum(),
            (df["monthly"] == "1000 KSH").sum()
        ]
    })

def chart_plot():
    df = pd.read_sql("SELECT * FROM votes", conn)
    fig, ax = plt.subplots()

    if df.empty:
        ax.text(0.5, 0.5, "No votes yet", ha="center", va="center")
        return fig

    data = {
        "Reg Fee Yes": (df["reg_fee"] == "Yes").sum(),
        "Reg Fee No": (df["reg_fee"] == "No").sum(),
        "500 KSH": (df["monthly"] == "500 KSH").sum(),
        "1000 KSH": (df["monthly"] == "1000 KSH").sum()
    }

    ax.bar(data.keys(), data.values())
    ax.set_title("Live Voting Results")
    return fig

def export_excel(user, password):
    if user != ADMIN_USER or password != ADMIN_PASS:
        return None
    df = pd.read_sql("SELECT * FROM votes", conn)
    file = "voting_results.xlsx"
    df.to_excel(file, index=False)
    return file

def close_voting(user, password):
    if user == ADMIN_USER and password == ADMIN_PASS:
        cursor.execute("UPDATE settings SET value='true' WHERE key='manual_close'")
        conn.commit()
        return "🔒 Voting manually closed."
    return "❌ Invalid admin credentials."

# ================= UI =================
with gr.Blocks(title="Staff Benefit Scheme Voting") as demo:
    gr.Markdown("# 🗳️ Staff Benefit Scheme – Live Voting")
    time_display = gr.Markdown(countdown_text())

    with gr.Tab("Vote"):
        member_id = gr.Textbox(label="Member ID")
        full_name = gr.Textbox(label="Full Name")
        location = gr.Dropdown(["Nairobi", "Amboseli", "Mara"], label="Location")
        reg_fee = gr.Dropdown(["Yes", "No"], label="Introduce Registration Fee (KES 200)")
        monthly = gr.Dropdown(["500 KSH", "1000 KSH"], label="Monthly Contribution")

        submit = gr.Button("Submit Vote")
        status = gr.Textbox(label="Status", interactive=False)
        results = gr.Dataframe(interactive=False)
        chart = gr.Plot()

        submit.click(
            submit_vote,
            inputs=[member_id, full_name, location, reg_fee, monthly],
            outputs=[status, results, chart, time_display]
        )

        demo.load(results_table, outputs=results)
        demo.load(chart_plot, outputs=chart)
        demo.load(countdown_text, outputs=time_display)

    with gr.Tab("Admin"):
        admin_user = gr.Textbox(label="Admin Username")
        admin_pass = gr.Textbox(label="Admin Password", type="password")

        close_btn = gr.Button("Close Voting Now")
        close_status = gr.Textbox(interactive=False)

        export_btn = gr.Button("Export Results to Excel")
        file_out = gr.File()

        close_btn.click(close_voting, inputs=[admin_user, admin_pass], outputs=close_status)
        export_btn.click(export_excel, inputs=[admin_user, admin_pass], outputs=file_out)

demo.launch(server_name="0.0.0.0", server_port=7860)

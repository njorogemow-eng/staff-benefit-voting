import gradio as gr
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime
import pytz
import re
import os

# ================== SETTINGS ==================
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

KENYA_TZ = pytz.timezone("Africa/Nairobi")
VOTING_DEADLINE = KENYA_TZ.localize(datetime(2026, 1, 16, 23, 59))
VOTING_MANUALLY_CLOSED = False

DB_FILE = "votes.db"

# ================== DATABASE ==================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
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
conn.commit()

# ================== HELPERS ==================
def kenya_now():
    return datetime.now(KENYA_TZ)

def voting_open():
    if VOTING_MANUALLY_CLOSED:
        return False
    return kenya_now() <= VOTING_DEADLINE

def validate_member_id(member_id):
    pattern = r"^OLK\d{3}$"
    if not re.match(pattern, member_id):
        return False
    number = int(member_id[3:])
    return 1 <= number <= 400

# ================== CORE LOGIC ==================
def submit_vote(member_id, full_name, location, reg_fee, monthly):
    if not voting_open():
        return "❌ Voting is closed.", results_table(), chart_plot(), countdown_text()

    if not validate_member_id(member_id):
        return "❌ Invalid Member ID. Use OLK001 – OLK400.", results_table(), chart_plot(), countdown_text()

    cursor.execute("SELECT * FROM votes WHERE member_id=?", (member_id,))
    if cursor.fetchone():
        return "❌ This Member ID has already voted.", results_table(), chart_plot(), countdown_text()

    cursor.execute(
        "INSERT INTO votes VALUES (?, ?, ?, ?, ?, ?)",
        (member_id, full_name, location, reg_fee, monthly, kenya_now().strftime("%Y-%m-%d %H:%M:%S"))
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
    fig, ax = plt.subplots(figsize=(6,4))

    if df.empty:
        ax.text(0.5, 0.5, "No votes yet", ha="center", va="center")
        return fig

    data = {
        "Reg Fee Yes": (df["reg_fee"] == "Yes").sum(),
        "Reg Fee No": (df["reg_fee"] == "No").sum(),
        "500 KSH": (df["monthly"] == "500 KSH").sum(),
        "1000 KSH": (df["monthly"] == "1000 KSH").sum()
    }

    ax.bar(data.keys(), data.values(), color=["green", "red", "blue", "orange"])
    ax.set_title("Live Voting Results")
    ax.set_ylabel("Votes")
    return fig

def countdown_text():
    if not voting_open():
        return "❌ Voting is CLOSED"
    remaining = VOTING_DEADLINE - kenya_now()
    days = remaining.days
    hours = remaining.seconds // 3600
    return f"🕒 Voting closes in {days} days, {hours} hours (Kenya Time)"

# ================== ADMIN ==================
def admin_export(user, password):
    if user != ADMIN_USER or password != ADMIN_PASS:
        return None
    df = pd.read_sql("SELECT * FROM votes", conn)
    file = "voting_results.xlsx"
    df.to_excel(file, index=False)
    return file

def admin_clear(user, password):
    if user != ADMIN_USER or password != ADMIN_PASS:
        return "❌ Invalid admin credentials"
    cursor.execute("DELETE FROM votes")
    conn.commit()
    return "✅ All voting results cleared"

def admin_close(user, password):
    global VOTING_MANUALLY_CLOSED
    if user != ADMIN_USER or password != ADMIN_PASS:
        return "❌ Invalid admin credentials"
    VOTING_MANUALLY_CLOSED = True
    return "🔒 Voting has been manually closed"

# ================== UI ==================
with gr.Blocks(css="""
body { background: linear-gradient(to right, #e3f2fd, #ffffff); }
h1 { color: #0d47a1; }
""") as demo:

    gr.Markdown("# 🗳️ **Staff Benefit Scheme – Live Voting**")
    gr.Markdown("**Valid Member IDs:** OLK001 – OLK400")

    with gr.Tab("Vote"):
        member_id = gr.Textbox(label="Member ID (OLK001 – OLK400)")
        full_name = gr.Textbox(label="Full Name")
        location = gr.Dropdown(["Nairobi", "Amboseli", "Mara"], label="Location")
        reg_fee = gr.Dropdown(["Yes", "No"], label="Introduce Registration Fee (KES 200)")
        monthly = gr.Dropdown(["500 KSH", "1000 KSH"], label="Monthly Contribution")

        submit_btn = gr.Button("Submit Vote", variant="primary")
        status = gr.Textbox(label="Status", interactive=False)

        countdown = gr.Markdown()
        results = gr.Dataframe(interactive=False)
        chart = gr.Plot()

        submit_btn.click(
            submit_vote,
            inputs=[member_id, full_name, location, reg_fee, monthly],
            outputs=[status, results, chart, countdown]
        )

        demo.load(results_table, outputs=results)
        demo.load(chart_plot, outputs=chart)
        demo.load(countdown_text, outputs=countdown)

    with gr.Tab("Admin Panel"):
        admin_user = gr.Textbox(label="Admin Username")
        admin_pass = gr.Textbox(label="Admin Password", type="password")

        with gr.Row():
            export_btn = gr.Button("⬇ Download Excel")
            clear_btn = gr.Button("🗑 Clear Results")
            close_btn = gr.Button("🔒 Close Voting")

        admin_msg = gr.Textbox(label="Admin Status", interactive=False)
        admin_file = gr.File()

        export_btn.click(admin_export, [admin_user, admin_pass], admin_file)
        clear_btn.click(admin_clear, [admin_user, admin_pass], admin_msg)
        close_btn.click(admin_close, [admin_user, admin_pass], admin_msg)

demo.launch(server_name="0.0.0.0", server_port=7860)

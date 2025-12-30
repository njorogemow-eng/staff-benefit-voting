import gradio as gr
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime

# ================= SETTINGS =================
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
VOTING_DEADLINE = datetime(2025, 1, 20, 23, 59)

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
conn.commit()

# ================= MEMBER LIST =================
members_df = pd.read_csv("members.csv")
valid_members = set(members_df["MemberID"].astype(str))

# ================= FUNCTIONS =================
def voting_open():
    return datetime.now() <= VOTING_DEADLINE

def submit_vote(member_id, full_name, location, reg_fee, monthly):
    if not voting_open():
        return "❌ Voting is closed.", results_table(), chart_plot()

    if member_id not in valid_members:
        return "❌ Invalid Member ID.", results_table(), chart_plot()

    cursor.execute("SELECT * FROM votes WHERE member_id=?", (member_id,))
    if cursor.fetchone():
        return "❌ You have already voted.", results_table(), chart_plot()

    cursor.execute(
        "INSERT INTO votes VALUES (?, ?, ?, ?, ?, ?)",
        (member_id, full_name, location, reg_fee, monthly, str(datetime.now()))
    )
    conn.commit()

    return "✅ Vote submitted successfully.", results_table(), chart_plot()

def results_table():
    df = pd.read_sql("SELECT * FROM votes", conn)
    if df.empty:
        return pd.DataFrame({
            "Item": ["Registration Fee", "Registration Fee", "Monthly Contribution", "Monthly Contribution"],
            "Option": ["Yes", "No", "500 KSH", "1000 KSH"],
            "Votes": [0, 0, 0, 0]
        })

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
        ax.text(0.5, 0.5, "No votes yet", ha="center")
        return fig

    data = {
        "Yes": (df["reg_fee"] == "Yes").sum(),
        "No": (df["reg_fee"] == "No").sum(),
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

# ================= UI =================
with gr.Blocks(title="Staff Benefit Scheme Voting") as demo:
    gr.Markdown("# 🗳️ Staff Benefit Scheme – Live Voting")

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
            outputs=[status, results, chart]
        )

        demo.load(results_table, outputs=results)
        demo.load(chart_plot, outputs=chart)

    with gr.Tab("Admin"):
        admin_user = gr.Textbox(label="Admin Username")
        admin_pass = gr.Textbox(label="Admin Password", type="password")
        export_btn = gr.Button("Export Results to Excel")
        file_out = gr.File()

        export_btn.click(export_excel, inputs=[admin_user, admin_pass], outputs=file_out)

demo.launch(server_name="0.0.0.0", server_port=7860)

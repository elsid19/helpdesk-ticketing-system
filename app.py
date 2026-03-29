import csv
import os
import sqlite3
from datetime import datetime
from io import StringIO

from flask import (
    Flask,
    Response,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "helpdesk.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"


CATEGORY_OPTIONS = [
    "Hardware",
    "Software",
    "Network",
    "Account Access",
    "Email",
    "Printer",
    "Security",
]

PRIORITY_OPTIONS = ["Low", "Medium", "High", "Critical"]
STATUS_FLOW = ["Open", "In Progress", "Resolved", "Closed"]


def normalize_enum(value, allowed_values):
    """Normalize user input to a canonical enum value (case-insensitive)."""
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    for item in allowed_values:
        if cleaned.lower() == item.lower():
            return item
    return None


SEED_TICKETS = [
    {
        "requester_name": "Carlos Rivera",
        "department": "Sales",
        "issue_title": "User cannot connect to corporate Wi-Fi (SSID not visible)",
        "description": "User in 4th floor conference area cannot see corp SSID on Windows 11 laptop; guest SSID is visible.",
        "category": "Network",
        "priority": "High",
        "status": "Open",
        "assigned_technician": "",
    },
    {
        "requester_name": "Emily Chen",
        "department": "Finance",
        "issue_title": "Outlook stuck in offline mode (OST sync issue)",
        "description": "Outlook shows Working Offline; OST last updated yesterday. Send/Receive does not resume sync.",
        "category": "Email",
        "priority": "High",
        "status": "In Progress",
        "assigned_technician": "Tech Maya",
    },
    {
        "requester_name": "David Patel",
        "department": "Remote Operations",
        "issue_title": "VPN fails with authentication error (AAD/credentials)",
        "description": "Always On VPN prompts repeatedly then fails with authentication error after password change.",
        "category": "Network",
        "priority": "Critical",
        "status": "In Progress",
        "assigned_technician": "Tech Sam",
    },
    {
        "requester_name": "Olivia Martinez",
        "department": "Operations",
        "issue_title": "Printer offline on Windows 11 (spooler/service)",
        "description": "HP LaserJet queue stays Offline. Print Spooler service was found stopped on affected workstation.",
        "category": "Printer",
        "priority": "Medium",
        "status": "Open",
        "assigned_technician": "",
    },
    {
        "requester_name": "Marcus Lee",
        "department": "HR",
        "issue_title": "Account locked after multiple failed logins (AD policy)",
        "description": "Domain user account auto-locked after failed logins from mapped laptop and mobile mail client.",
        "category": "Account Access",
        "priority": "High",
        "status": "Resolved",
        "assigned_technician": "Tech Alex",
    },
    {
        "requester_name": "Sarah Nguyen",
        "department": "Marketing",
        "issue_title": "Laptop performance degraded after security update",
        "description": "Boot time > 8 minutes and browser freezes; endpoint scan and startup apps need review.",
        "category": "Hardware",
        "priority": "Medium",
        "status": "Open",
        "assigned_technician": "",
    },
    {
        "requester_name": "John Williams",
        "department": "Engineering",
        "issue_title": "Software installation request: Wireshark",
        "description": "Requires Wireshark and Npcap for packet capture training lab; admin approval attached.",
        "category": "Software",
        "priority": "Low",
        "status": "Closed",
        "assigned_technician": "Tech Nina",
    },
    {
        "requester_name": "Priya Shah",
        "department": "Legal",
        "issue_title": "MFA prompt not received on company phone",
        "description": "Microsoft Authenticator notifications stopped after iOS update; user can sign in only with backup code.",
        "category": "Security",
        "priority": "High",
        "status": "Open",
        "assigned_technician": "",
    },
    {
        "requester_name": "Ethan Brooks",
        "department": "Support",
        "issue_title": "Shared drive access denied after group policy refresh",
        "description": "Access to \\fileserver\\Support denied for user despite expected AD group membership.",
        "category": "Account Access",
        "priority": "Medium",
        "status": "In Progress",
        "assigned_technician": "Tech Maya",
    },
    {
        "requester_name": "Rachel Green",
        "department": "Executive",
        "issue_title": "Teams camera not detected during meetings",
        "description": "Logitech webcam not listed in Teams app; device appears intermittently in Device Manager.",
        "category": "Hardware",
        "priority": "Medium",
        "status": "Resolved",
        "assigned_technician": "Tech Alex",
    },
    {
        "requester_name": "Daniel Kim",
        "department": "Customer Success",
        "issue_title": "New hire cannot access Salesforce",
        "description": "SSO login succeeds but app authorization fails; role mapping may be missing in IdP group sync.",
        "category": "Account Access",
        "priority": "High",
        "status": "Open",
        "assigned_technician": "",
    },
    {
        "requester_name": "Ariana Lopez",
        "department": "Procurement",
        "issue_title": "Email attachment blocked by security policy",
        "description": "Vendor invoice attachment quarantined due to macro policy; needs safe-release validation.",
        "category": "Security",
        "priority": "Medium",
        "status": "Open",
        "assigned_technician": "",
    },
]


@app.template_filter("fmt_dt")
def fmt_dt(value):
    if not value:
        return "-"
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        return value


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def valid_status_transition(current_status, new_status):
    if new_status not in STATUS_FLOW:
        return False
    if current_status == new_status:
        return True

    allowed = {
        "Open": ["In Progress"],
        "In Progress": ["Resolved"],
        "Resolved": ["Closed"],
        "Closed": [],
    }
    return new_status in allowed.get(current_status, [])


def generate_ticket_id(db):
    year = datetime.now().year
    prefix = f"HD-{year}-"
    row = db.execute(
        "SELECT ticket_id FROM tickets WHERE ticket_id LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefix}%",),
    ).fetchone()
    if not row:
        return f"{prefix}0001"

    last_number = int(row["ticket_id"].split("-")[-1])
    return f"{prefix}{last_number + 1:04d}"


def log_audit(db, ticket_pk, action, details):
    db.execute(
        """
        INSERT INTO audit_logs (ticket_pk, action, details, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (ticket_pk, action, details, now_str()),
    )


def initialize_database():
    os.makedirs(DATABASE_DIR, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            requester_name TEXT NOT NULL,
            department TEXT NOT NULL,
            issue_title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('Hardware','Software','Network','Account Access','Email','Printer','Security')),
            priority TEXT NOT NULL CHECK (priority IN ('Low','Medium','High','Critical')),
            status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','In Progress','Resolved','Closed')),
            assigned_technician TEXT,
            resolution_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_pk INTEGER NOT NULL,
            author TEXT NOT NULL,
            note_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(ticket_pk) REFERENCES tickets(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_pk INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(ticket_pk) REFERENCES tickets(id)
        );
        """
    )

    count = db.execute("SELECT COUNT(*) AS count FROM tickets").fetchone()["count"]
    if count == 0:
        for seed in SEED_TICKETS:
            created = now_str()
            ticket_id = generate_ticket_id(db)
            resolved_at = created if seed["status"] == "Resolved" else None
            db.execute(
                """
                INSERT INTO tickets (
                    ticket_id, requester_name, department, issue_title, description,
                    category, priority, status, assigned_technician,
                    created_at, updated_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    seed["requester_name"],
                    seed["department"],
                    seed["issue_title"],
                    seed["description"],
                    seed["category"],
                    seed["priority"],
                    seed["status"],
                    seed["assigned_technician"],
                    created,
                    created,
                    resolved_at,
                ),
            )
            ticket_pk = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            log_audit(db, ticket_pk, "Ticket Seeded", "Initial sample data inserted")

        # Add a few seed notes for realism
        db.execute(
            "INSERT INTO notes (ticket_pk, author, note_text, created_at) VALUES (2, 'Tech Maya', 'Checked mailbox quota and profile health. Monitoring sync.', ?)",
            (now_str(),),
        )
        db.execute(
            "INSERT INTO notes (ticket_pk, author, note_text, created_at) VALUES (5, 'Tech Sam', 'Validated VPN gateway reachability. Investigating client config mismatch.', ?)",
            (now_str(),),
        )

    db.commit()
    db.close()


@app.context_processor
def inject_layout_context():
    return {"last_updated_label": datetime.now().strftime("%b %d, %Y %I:%M %p")}


@app.route("/")
def dashboard():
    db = get_db()

    status_filter = normalize_enum(request.args.get("status", ""), STATUS_FLOW) or ""
    priority_filter = normalize_enum(request.args.get("priority", ""), PRIORITY_OPTIONS) or ""
    search_query = request.args.get("q", "").strip()
    sort_order = request.args.get("sort", "newest")

    where_clauses = []
    params = []

    if status_filter:
        where_clauses.append("status = ?")
        params.append(status_filter)

    if priority_filter:
        where_clauses.append("priority = ?")
        params.append(priority_filter)

    if search_query:
        where_clauses.append("(issue_title LIKE ? OR requester_name LIKE ?)")
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard])

    query = "SELECT * FROM tickets"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    if sort_order == "oldest":
        query += " ORDER BY created_at ASC"
    else:
        sort_order = "newest"
        query += " ORDER BY created_at DESC"

    tickets = db.execute(query, params).fetchall()

    metrics = {
        "total": db.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"],
        "open": db.execute("SELECT COUNT(*) AS c FROM tickets WHERE status = 'Open'").fetchone()["c"],
        "in_progress": db.execute("SELECT COUNT(*) AS c FROM tickets WHERE status = 'In Progress'").fetchone()["c"],
        "resolved": db.execute("SELECT COUNT(*) AS c FROM tickets WHERE status = 'Resolved'").fetchone()["c"],
        "high_priority": db.execute(
            "SELECT COUNT(*) AS c FROM tickets WHERE priority IN ('High', 'Critical')"
        ).fetchone()["c"],
    }

    return render_template(
        "dashboard.html",
        tickets=tickets,
        metrics=metrics,
        status_filter=status_filter,
        priority_filter=priority_filter,
        search_query=search_query,
        sort_order=sort_order,
        status_options=STATUS_FLOW,
        priority_options=PRIORITY_OPTIONS,
    )


@app.route("/tickets/new", methods=["GET", "POST"])
def new_ticket():
    if request.method == "POST":
        db = get_db()

        requester_name = request.form.get("requester_name", "").strip()
        department = request.form.get("department", "").strip()
        issue_title = request.form.get("issue_title", "").strip()
        description = request.form.get("description", "").strip()
        category_raw = request.form.get("category", "")
        priority_raw = request.form.get("priority", "")
        category = normalize_enum(category_raw, CATEGORY_OPTIONS)
        priority = normalize_enum(priority_raw, PRIORITY_OPTIONS)

        missing_fields = []
        required = {
            "Requester Name": requester_name,
            "Department": department,
            "Issue Title": issue_title,
            "Description": description,
            "Category": category,
            "Priority": priority,
        }
        for label, value in required.items():
            if not value:
                missing_fields.append(label)

        if missing_fields:
            flash(f"Missing required fields: {', '.join(missing_fields)}", "error")
            return render_template(
                "new_ticket.html",
                category_options=CATEGORY_OPTIONS,
                priority_options=PRIORITY_OPTIONS,
            )

        if category not in CATEGORY_OPTIONS or priority not in PRIORITY_OPTIONS:
            flash("Invalid category or priority selection.", "error")
            return render_template(
                "new_ticket.html",
                category_options=CATEGORY_OPTIONS,
                priority_options=PRIORITY_OPTIONS,
            )

        ts = now_str()
        ticket_id = generate_ticket_id(db)
        db.execute(
            """
            INSERT INTO tickets (
                ticket_id, requester_name, department, issue_title, description,
                category, priority, status, assigned_technician,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', '', ?, ?)
            """,
            (
                ticket_id,
                requester_name,
                department,
                issue_title,
                description,
                category,
                priority,
                ts,
                ts,
            ),
        )
        ticket_pk = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        log_audit(db, ticket_pk, "Ticket Created", f"Ticket created by requester: {requester_name}")
        db.commit()

        flash(f"Ticket {ticket_id} created successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template(
        "new_ticket.html",
        category_options=CATEGORY_OPTIONS,
        priority_options=PRIORITY_OPTIONS,
    )


@app.route("/tickets/<int:ticket_pk>")
def ticket_detail(ticket_pk):
    db = get_db()
    ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_pk,)).fetchone()

    if not ticket:
        flash("Ticket not found.", "error")
        return redirect(url_for("dashboard"))

    notes = db.execute(
        "SELECT * FROM notes WHERE ticket_pk = ? ORDER BY created_at DESC", (ticket_pk,)
    ).fetchall()

    audit_logs = db.execute(
        "SELECT * FROM audit_logs WHERE ticket_pk = ? ORDER BY created_at DESC", (ticket_pk,)
    ).fetchall()

    return render_template(
        "ticket_detail.html",
        ticket=ticket,
        notes=notes,
        audit_logs=audit_logs,
        status_options=STATUS_FLOW,
        priority_options=PRIORITY_OPTIONS,
    )


@app.route("/tickets/<int:ticket_pk>/update", methods=["POST"])
def update_ticket(ticket_pk):
    db = get_db()
    ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_pk,)).fetchone()

    if not ticket:
        flash("Ticket not found.", "error")
        return redirect(url_for("dashboard"))

    assigned_technician = request.form.get("assigned_technician", "").strip()
    priority_raw = request.form.get("priority", ticket["priority"])
    status_raw = request.form.get("status", ticket["status"])
    priority = normalize_enum(priority_raw, PRIORITY_OPTIONS)
    status = normalize_enum(status_raw, STATUS_FLOW)
    note_author = request.form.get("note_author", "Technician").strip() or "Technician"
    note_text = request.form.get("note_text", "").strip()
    resolution_notes = request.form.get("resolution_notes", "").strip()

    if priority not in PRIORITY_OPTIONS:
        flash("Invalid priority selected.", "error")
        return redirect(url_for("ticket_detail", ticket_pk=ticket_pk))

    if not valid_status_transition(ticket["status"], status):
        flash(
            f"Invalid status transition: {ticket['status']} → {status}. Follow Open → In Progress → Resolved → Closed.",
            "error",
        )
        return redirect(url_for("ticket_detail", ticket_pk=ticket_pk))

    updated_at = now_str()
    resolved_at = ticket["resolved_at"]

    if ticket["status"] != "Resolved" and status == "Resolved":
        resolved_at = updated_at

    # Keep existing resolution notes unless user adds/replaces text.
    final_resolution_notes = resolution_notes if resolution_notes else ticket["resolution_notes"]

    db.execute(
        """
        UPDATE tickets
        SET assigned_technician = ?, priority = ?, status = ?,
            resolution_notes = ?, updated_at = ?, resolved_at = ?
        WHERE id = ?
        """,
        (
            assigned_technician,
            priority,
            status,
            final_resolution_notes,
            updated_at,
            resolved_at,
            ticket_pk,
        ),
    )

    change_summary = []
    if assigned_technician != (ticket["assigned_technician"] or ""):
        change_summary.append(f"Assigned technician updated to '{assigned_technician or 'Unassigned'}'")
    if priority != ticket["priority"]:
        change_summary.append(f"Priority changed {ticket['priority']} → {priority}")
    if status != ticket["status"]:
        change_summary.append(f"Status changed {ticket['status']} → {status}")

    if resolution_notes:
        change_summary.append("Resolution notes updated")

    if note_text:
        db.execute(
            """
            INSERT INTO notes (ticket_pk, author, note_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (ticket_pk, note_author, note_text, updated_at),
        )
        change_summary.append("Technician note added")

    details = "; ".join(change_summary) if change_summary else "No major field changes"
    log_audit(db, ticket_pk, "Ticket Updated", details)

    db.commit()
    flash("Ticket updated successfully.", "success")
    return redirect(url_for("ticket_detail", ticket_pk=ticket_pk))


@app.route("/tickets/export.csv")
def export_csv():
    db = get_db()
    tickets = db.execute(
        """
        SELECT ticket_id, requester_name, department, issue_title, category,
               priority, status, assigned_technician, created_at, updated_at, resolved_at
        FROM tickets
        ORDER BY created_at DESC
        """
    ).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Ticket ID",
            "Requester",
            "Department",
            "Title",
            "Category",
            "Priority",
            "Status",
            "Assigned Technician",
            "Created At",
            "Updated At",
            "Resolved At",
        ]
    )
    for t in tickets:
        writer.writerow(
            [
                t["ticket_id"],
                t["requester_name"],
                t["department"],
                t["issue_title"],
                t["category"],
                t["priority"],
                t["status"],
                t["assigned_technician"],
                t["created_at"],
                t["updated_at"],
                t["resolved_at"],
            ]
        )

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=helpdesk_tickets.csv"},
    )


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
else:
    initialize_database()

import os
import csv
import io
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    jsonify,
    send_file,
)

from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "PORTFOLIO_SECRET_KEY",
    "development-only-change-this-secret"
)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
ADMIN_ROLE = "Super Admin"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "portfolio.db")
BACKUP_DIR = os.path.join(BASE_DIR, "database_backups")

os.makedirs(BACKUP_DIR, exist_ok=True)


# ============================================================
# TIME
# ============================================================

def india_time():
    """Return current India time."""
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


def current_time_string():
    return india_time().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    # Make SQLite safer
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# ============================================================
# DATABASE CREATION
# IMPORTANT:
# This function ALWAYS checks/creates every required table.
# ============================================================

def create_database():

    conn = get_db()

    try:

        # ----------------------------------------------------
        # CONTACT MESSAGES TABLE
        # ----------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT DEFAULT '',
                message TEXT NOT NULL,
                ip_address TEXT DEFAULT '',
                analysis_level TEXT DEFAULT 'Low',
                analysis_reason TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # ACTIVITY LOGS TABLE
        # ----------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                ip_address TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # SECURITY EVENTS TABLE
        # ----------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                severity TEXT DEFAULT 'Low',
                created_at TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # ADMIN USERS TABLE
        # ----------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'Admin',
                created_at TEXT NOT NULL
            )
        """)

        # ----------------------------------------------------
        # NOTIFICATIONS TABLE
        # ----------------------------------------------------

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                notification_type TEXT DEFAULT 'info',
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()

        # ----------------------------------------------------
        # ENSURE ADMIN USER EXISTS
        # ----------------------------------------------------

        existing_admin = conn.execute(
            "SELECT id FROM admin_users WHERE username = ?",
            (ADMIN_USERNAME,)
        ).fetchone()

        if not existing_admin:

            password_hash = generate_password_hash(ADMIN_PASSWORD)

            conn.execute("""
                INSERT INTO admin_users
                (username, password_hash, role, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                ADMIN_USERNAME,
                password_hash,
                ADMIN_ROLE,
                current_time_string()
            ))

            conn.commit()

    finally:
        conn.close()


# Create database BEFORE serving requests.
create_database()


# ============================================================
# LOGIN SECURITY
# ============================================================

failed_login_attempts = {}
contact_rate_limit = {}


def is_admin_logged_in():
    return session.get("admin_logged_in") is True


def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not is_admin_logged_in():
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return wrapper


# ============================================================
# ACTIVITY LOG
# ============================================================

def log_activity(action, ip_address=""):

    try:

        conn = get_db()

        conn.execute("""
            INSERT INTO activity_logs
            (action, ip_address, created_at)
            VALUES (?, ?, ?)
        """, (
            action,
            ip_address,
            current_time_string()
        ))

        conn.commit()
        conn.close()

    except Exception as error:
        print("Activity log error:", error)


# ============================================================
# SECURITY EVENT
# ============================================================

def log_security_event(
    event_type,
    description,
    ip_address="",
    severity="Low"
):

    try:

        conn = get_db()

        conn.execute("""
            INSERT INTO security_events
            (event_type, description, ip_address, severity, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            event_type,
            description,
            ip_address,
            severity,
            current_time_string()
        ))

        conn.commit()
        conn.close()

    except Exception as error:
        print("Security event error:", error)


# ============================================================
# AI-STYLE MESSAGE ANALYSIS
# ============================================================

def analyze_message(message):

    text = (message or "").lower()

    high_words = [
        "hack",
        "hacking",
        "attack",
        "password",
        "steal",
        "stolen",
        "malware",
        "virus",
        "exploit",
        "sql injection",
        "ddos",
        "unauthorized",
        "threat",
    ]

    medium_words = [
        "urgent",
        "problem",
        "issue",
        "error",
        "complaint",
        "help",
        "security",
    ]

    high_found = [word for word in high_words if word in text]
    medium_found = [word for word in medium_words if word in text]

    if high_found:

        return (
            "High",
            "Security-related keywords detected: "
            + ", ".join(high_found[:5])
        )

    if medium_found:

        return (
            "Medium",
            "Important keywords detected: "
            + ", ".join(medium_found[:5])
        )

    return (
        "Low",
        "No high-risk keywords detected."
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template("index.html")


# ============================================================
# CONTACT
# ============================================================

@app.route("/contact", methods=["POST"])
def contact():

    # --------------------------------------------------------
    # Make sure DB tables exist even after deployment/restart.
    # This is the important Render fix.
    # --------------------------------------------------------

    create_database()

    ip_address = request.headers.get(
        "X-Forwarded-For",
        request.remote_addr or ""
    )

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    # --------------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------------

    if not name or not email or not message:

        flash(
            "Please fill all required fields.",
            "error"
        )

        return redirect(url_for("home") + "#contact")

    # --------------------------------------------------------
    # SIMPLE RATE LIMIT
    # Maximum 3 messages in 60 seconds per IP
    # --------------------------------------------------------

    now = time.time()

    previous_requests = contact_rate_limit.get(
        ip_address,
        []
    )

    previous_requests = [
        timestamp
        for timestamp in previous_requests
        if now - timestamp < 60
    ]

    if len(previous_requests) >= 3:

        log_security_event(
            "Contact Rate Limit",
            "Too many contact form submissions.",
            ip_address,
            "Medium"
        )

        flash(
            "Too many messages. Please try again later.",
            "error"
        )

        return redirect(url_for("home") + "#contact")

    previous_requests.append(now)

    contact_rate_limit[ip_address] = previous_requests

    # --------------------------------------------------------
    # MESSAGE ANALYSIS
    # --------------------------------------------------------

    analysis_level, analysis_reason = analyze_message(
        message
    )

    # --------------------------------------------------------
    # SAVE MESSAGE
    # --------------------------------------------------------

    conn = get_db()

    conn.execute("""
        INSERT INTO messages
        (
            name,
            email,
            subject,
            message,
            ip_address,
            analysis_level,
            analysis_reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        email,
        subject,
        message,
        ip_address,
        analysis_level,
        analysis_reason,
        current_time_string()
    ))

    conn.commit()

    # --------------------------------------------------------
    # NOTIFICATION
    # --------------------------------------------------------

    conn.execute("""
        INSERT INTO notifications
        (
            title,
            message,
            notification_type,
            is_read,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        "New Contact Message",
        f"New message received from {name}.",
        "contact",
        0,
        current_time_string()
    ))

    conn.commit()
    conn.close()

    # --------------------------------------------------------
    # SECURITY LOG FOR HIGH-RISK MESSAGE
    # --------------------------------------------------------

    if analysis_level == "High":

        log_security_event(
            "High Risk Contact",
            analysis_reason,
            ip_address,
            "High"
        )

    flash(
        "Your message has been sent successfully!",
        "success"
    )

    return redirect(url_for("home") + "#contact")


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if is_admin_logged_in():

        return redirect(url_for("admin_dashboard"))

    ip_address = request.headers.get(
        "X-Forwarded-For",
        request.remote_addr or ""
    )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        current_timestamp = time.time()

        # ----------------------------------------------------
        # LOCKOUT CHECK
        # ----------------------------------------------------

        attempt_data = failed_login_attempts.get(
            ip_address
        )

        if attempt_data:

            attempts = attempt_data["attempts"]
            locked_until = attempt_data["locked_until"]

            if locked_until > current_timestamp:

                remaining = int(
                    locked_until - current_timestamp
                )

                flash(
                    f"Too many failed attempts. "
                    f"Try again in {remaining} seconds.",
                    "error"
                )

                return render_template(
                    "admin_login.html"
                )

        # ----------------------------------------------------
        # CHECK ADMIN
        # ----------------------------------------------------

        conn = get_db()

        admin = conn.execute("""
            SELECT *
            FROM admin_users
            WHERE username = ?
        """, (
            username,
        )).fetchone()

        conn.close()

        valid_login = False

        if admin:

            try:

                valid_login = check_password_hash(
                    admin["password_hash"],
                    password
                )

            except Exception:

                valid_login = False

        # ----------------------------------------------------
        # FALLBACK ENV LOGIN
        # ----------------------------------------------------

        if (
            username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            valid_login = True

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if valid_login:

            failed_login_attempts.pop(
                ip_address,
                None
            )

            session.clear()

            session["admin_logged_in"] = True
            session["admin_username"] = username
            session["admin_role"] = ADMIN_ROLE

            log_activity(
                "Login Successful",
                ip_address
            )

            return redirect(
                url_for("admin_dashboard")
            )

        # ----------------------------------------------------
        # FAILED LOGIN
        # ----------------------------------------------------

        data = failed_login_attempts.get(
            ip_address,
            {
                "attempts": 0,
                "locked_until": 0
            }
        )

        data["attempts"] += 1

        if data["attempts"] >= 5:

            data["locked_until"] = (
                current_timestamp + 300
            )

            log_security_event(
                "Login Lockout",
                "Five failed login attempts.",
                ip_address,
                "High"
            )

        failed_login_attempts[ip_address] = data

        log_activity(
            "Login Failed",
            ip_address
        )

        flash(
            "Invalid username or password.",
            "error"
        )

    return render_template(
        "admin_login.html"
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    ip_address = request.headers.get(
        "X-Forwarded-For",
        request.remote_addr or ""
    )

    log_activity(
        "Logout",
        ip_address
    )

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    create_database()

    conn = get_db()

    # Messages
    messages = conn.execute("""
        SELECT *
        FROM messages
        ORDER BY id DESC
    """).fetchall()

    # Logs
    logs = conn.execute("""
        SELECT *
        FROM activity_logs
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()

    # Security events
    security_events = conn.execute("""
        SELECT *
        FROM security_events
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    # Notifications
    notifications = conn.execute("""
        SELECT *
        FROM notifications
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    # Statistics
    total_messages = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
    """).fetchone()["count"]

    high_risk = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE analysis_level = 'High'
    """).fetchone()["count"]

    medium_risk = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE analysis_level = 'Medium'
    """).fetchone()["count"]

    low_risk = conn.execute("""
        SELECT COUNT(*) AS count
        FROM messages
        WHERE analysis_level = 'Low'
    """).fetchone()["count"]

    total_logins = conn.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action = 'Login Successful'
    """).fetchone()["count"]

    failed_logins = conn.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE action = 'Login Failed'
    """).fetchone()["count"]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        messages=messages,
        logs=logs,
        security_events=security_events,
        notifications=notifications,
        total_messages=total_messages,
        high_risk=high_risk,
        medium_risk=medium_risk,
        low_risk=low_risk,
        total_logins=total_logins,
        failed_logins=failed_logins,
        admin_username=session.get(
            "admin_username",
            ADMIN_USERNAME
        ),
        admin_role=session.get(
            "admin_role",
            ADMIN_ROLE
        )
    )


# ============================================================
# ADMIN LOGS
# ============================================================

@app.route("/admin/logs")
@admin_required
def admin_logs():

    conn = get_db()

    logs = conn.execute("""
        SELECT *
        FROM activity_logs
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_logs.html",
        logs=logs
    )


# ============================================================
# DELETE MESSAGE
# ============================================================

@app.route(
    "/admin/message/delete/<int:message_id>",
    methods=["POST"]
)
@admin_required
def delete_message(message_id):

    conn = get_db()

    message = conn.execute("""
        SELECT *
        FROM messages
        WHERE id = ?
    """, (
        message_id,
    )).fetchone()

    if message:

        conn.execute("""
            DELETE FROM messages
            WHERE id = ?
        """, (
            message_id,
        ))

        conn.commit()

        log_activity(
            f"Deleted Message #{message_id}",
            request.remote_addr or ""
        )

    conn.close()

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# CSV EXPORT
# ============================================================

@app.route("/admin/export/csv")
@admin_required
def export_csv():

    conn = get_db()

    messages = conn.execute("""
        SELECT *
        FROM messages
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Name",
        "Email",
        "Subject",
        "Message",
        "IP Address",
        "Analysis Level",
        "Analysis Reason",
        "Created At"
    ])

    for message in messages:

        writer.writerow([
            message["id"],
            message["name"],
            message["email"],
            message["subject"],
            message["message"],
            message["ip_address"],
            message["analysis_level"],
            message["analysis_reason"],
            message["created_at"]
        ])

    log_activity(
        "Exported Contact Messages CSV",
        request.remote_addr or ""
    )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=contact_messages.csv"
        }
    )


# ============================================================
# DATABASE BACKUP
# ============================================================

@app.route("/admin/backup")
@admin_required
def backup_database():

    create_database()

    timestamp = india_time().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_file = os.path.join(
        BACKUP_DIR,
        f"portfolio_backup_{timestamp}.db"
    )

    source = sqlite3.connect(DATABASE)
    destination = sqlite3.connect(backup_file)

    try:

        source.backup(destination)

    finally:

        destination.close()
        source.close()

    log_activity(
        "Database Backup Created",
        request.remote_addr or ""
    )

    return send_file(
        backup_file,
        as_attachment=True,
        download_name=os.path.basename(
            backup_file
        )
    )


# ============================================================
# DATABASE RESTORE
# ============================================================

@app.route(
    "/admin/restore",
    methods=["POST"]
)
@admin_required
def restore_database():

    uploaded_file = request.files.get(
        "database_file"
    )

    if not uploaded_file:

        flash(
            "Please select a database backup file.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    if not uploaded_file.filename.lower().endswith(
        ".db"
    ):

        flash(
            "Only .db files are allowed.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    temp_backup = os.path.join(
        BACKUP_DIR,
        "uploaded_restore.db"
    )

    uploaded_file.save(temp_backup)

    # Validate SQLite database
    try:

        test_conn = sqlite3.connect(
            temp_backup
        )

        result = test_conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()

        test_conn.close()

        if not result or result[0] != "ok":

            os.remove(temp_backup)

            flash(
                "Invalid or corrupted database file.",
                "error"
            )

            return redirect(
                url_for("admin_dashboard")
            )

    except Exception:

        if os.path.exists(temp_backup):
            os.remove(temp_backup)

        flash(
            "Could not read database file.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # Backup current DB before restore
    timestamp = india_time().strftime(
        "%Y%m%d_%H%M%S"
    )

    safety_backup = os.path.join(
        BACKUP_DIR,
        f"before_restore_{timestamp}.db"
    )

    if os.path.exists(DATABASE):

        source = sqlite3.connect(DATABASE)
        destination = sqlite3.connect(
            safety_backup
        )

        try:

            source.backup(destination)

        finally:

            destination.close()
            source.close()

    # Replace database
    try:

        if os.path.exists(DATABASE):
            os.remove(DATABASE)

        os.replace(
            temp_backup,
            DATABASE
        )

        create_database()

        log_activity(
            "Database Restored",
            request.remote_addr or ""
        )

        flash(
            "Database restored successfully.",
            "success"
        )

    except Exception as error:

        print(
            "Database restore error:",
            error
        )

        flash(
            "Database restore failed.",
            "error"
        )

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# PDF REPORT
# ============================================================

@app.route("/admin/report")
@app.route("/admin/generate-report")
@admin_required
def generate_report():

    try:

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
        )
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet

    except ImportError:

        return (
            "ReportLab is not installed.",
            500
        )

    conn = get_db()

    messages = conn.execute("""
        SELECT *
        FROM messages
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    output = io.BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=A4
    )

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "Sakthi Narendran - Portfolio Report",
            styles["Title"]
        )
    )

    story.append(
        Spacer(1, 15)
    )

    story.append(
        Paragraph(
            f"Generated: {current_time_string()}",
            styles["Normal"]
        )
    )

    story.append(
        Spacer(1, 15)
    )

    data = [
        [
            "ID",
            "Name",
            "Email",
            "Risk",
            "Date"
        ]
    ]

    for message in messages:

        data.append([
            str(message["id"]),
            message["name"][:25],
            message["email"][:30],
            message["analysis_level"],
            message["created_at"]
        ])

    table = Table(
        data,
        repeatRows=1
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.grey
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),
        ])
    )

    story.append(table)

    document.build(story)

    output.seek(0)

    log_activity(
        "Generated PDF Report",
        request.remote_addr or ""
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="portfolio_report.pdf",
        mimetype="application/pdf"
    )


# ============================================================
# REAL-TIME NOTIFICATIONS
# ============================================================

@app.route("/admin/notifications")
@admin_required
def notifications_api():

    conn = get_db()

    notifications = conn.execute("""
        SELECT *
        FROM notifications
        WHERE is_read = 0
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    conn.close()

    data = []

    for notification in notifications:

        data.append({
            "id": notification["id"],
            "title": notification["title"],
            "message": notification["message"],
            "type": notification["notification_type"],
            "created_at": notification["created_at"]
        })

    return jsonify({
        "count": len(data),
        "notifications": data
    })


# ============================================================
# MARK NOTIFICATIONS AS READ
# ============================================================

@app.route(
    "/admin/notifications/read",
    methods=["POST"]
)
@admin_required
def mark_notifications_read():

    conn = get_db()

    conn.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE is_read = 0
    """)

    conn.commit()
    conn.close()

    return jsonify({
        "success": True
    })


# ============================================================
# SYSTEM HEALTH
# ============================================================

@app.route("/admin/health")
@admin_required
def system_health():

    try:

        create_database()

        conn = get_db()

        conn.execute(
            "SELECT 1"
        ).fetchone()

        conn.close()

        database_status = "Healthy"

    except Exception as error:

        database_status = f"Error: {error}"

    return jsonify({
        "status": "Online",
        "database": database_status,
        "time": current_time_string()
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return (
        render_template(
            "index.html"
        ),
        404
    )


@app.errorhandler(500)
def internal_server_error(error):

    print(
        "Internal Server Error:",
        error
    )

    return (
        "Internal Server Error. Please check Render logs.",
        500
    )


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    create_database()

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )

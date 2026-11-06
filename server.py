import os
import json
import smtplib
from email.message import EmailMessage
import http.server
import socketserver
import psycopg2

PORT = int(os.environ.get("PORT", 8000))
DATABASE_URL = os.environ.get("DATABASE_URL")
SMTP_USER = os.environ.get("SMTP_USER", "reports@arch-dome.com")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
SMTP_HOST = os.environ.get("SMTP_HOST", "mail.arch-dome.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))

def get_db_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def save_waitlist_entry(conn, email: str, new_program: str):
    clean_email = email.strip().lower()
    clean_program = new_program.strip()
    cur = conn.cursor()
    try:
        cur.execute("SELECT interested_programs FROM public.program_waitlist WHERE LOWER(email) = LOWER(%s)", (clean_email,))
        row = cur.fetchone()

        if row:
            current_programs = row[0] if row[0] else ""
            programs_list = [p.strip() for p in current_programs.split(',') if p.strip()]
            if clean_program in programs_list:
                cur.close()
                return "exists"
            
            programs_list.append(clean_program)
            updated_programs = ",".join(programs_list)
            cur.execute("""
                UPDATE public.program_waitlist 
                SET interested_programs = %s, created_at = NOW() 
                WHERE LOWER(email) = LOWER(%s)
            """, (updated_programs, clean_email))
            conn.commit()
            cur.close()
            return "updated"
        else:
            cur.execute("""
                INSERT INTO public.program_waitlist (email, interested_programs)
                VALUES (%s, %s)
            """, (clean_email, clean_program))
            conn.commit()
            cur.close()
            return "new"
    except Exception as e:
        conn.rollback()
        cur.close()
        raise e

def send_waitlist_email(to_email, program_name):
    if not APP_PASSWORD:
        return False

    msg = EmailMessage()
    msg["Subject"] = f"تم تأكيد حجزك - DOME AI ({program_name}) 🏗️"
    msg["From"] = f"DOME Team <{SMTP_USER}>"
    msg["To"] = to_email
    msg.set_content(f"مرحباً بك في DOME.\nتم تسجيل بريدك بنجاح في قائمة انتظار: {program_name}.\nسنبلغك فور الإطلاق.")

    html_body = f"""
    <div style="direction: rtl; text-align: right; font-family: sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 10px; border-top: 5px solid #BD583B;">
            <h2 style="color: #274055; margin-top: 0;">أهلاً بك في DOME AI 👋</h2>
            <p style="font-size: 16px; color: #555;">لقد تم تسجيل بريدك بنجاح في قائمة الانتظار الخاصة بـ:</p>
            <div style="background-color: #eef2f5; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center; border: 1px dashed #BD583B;">
                <h3 style="color: #BD583B; margin: 0;">{program_name}</h3>
            </div>
            <p style="font-size: 14px; color: #666;">ستصلك دعوة ورابط خاص فور إطلاق النسخة الرسمية لتجربتها مجاناً.</p>
        </div>
    </div>
    """
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, APP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("Mail error:", e)
        return False

class LandingHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/waitlist":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                email = data.get("email", "").strip()
                prog_key = data.get("program", "v2").strip()

                prog_display = "🏗️ مقايسة وحساب الكميات (V2)" if prog_key == "v2" else "👷 المساعد الشخصي للمهندس (V3)"

                conn = get_db_connection()
                if not conn:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "message": "Database not configured"}).encode("utf-8"))
                    return

                status = save_waitlist_entry(conn, email, prog_key)

                # تسجيل الحدث في جدول user_events ليظهر للأونر
                try:
                    cur_ev = conn.cursor()
                    cur_ev.execute("""
                        INSERT INTO public.user_events (session_id, user_id, ip_address, event_type, details, timestamp)
                        VALUES (%s, NULL, %s, %s, %s, NOW())
                    """, ("landing_modal", self.client_address[0], "join_waitlist", f"Joined {prog_key.upper()} Waitlist: {email}"))
                    conn.commit()
                    cur_ev.close()
                except Exception:
                    pass

                conn.close()

                if status in ["new", "updated"]:
                    send_waitlist_email(email, prog_display)

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": status}).encode("utf-8"))

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

with socketserver.TCPServer(("", PORT), LandingHandler) as httpd:
    print(f"Serving Landing Page at port {PORT}")
    httpd.serve_forever()

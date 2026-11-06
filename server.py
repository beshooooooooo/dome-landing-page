import os
import json
import smtplib
from email.message import EmailMessage
from http.server import HTTPServer, SimpleHTTPRequestHandler
import psycopg2
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SMTP_USER = os.getenv("SMTP_USER", "reports@arch-dome.com")
APP_PASSWORD = os.getenv("APP_PASSWORD")
SMTP_HOST = os.getenv("SMTP_HOST", "mail.arch-dome.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))


def send_waitlist_email(to_email: str, program_name: str) -> bool:
    """إرسال إيميل تأكيد الحجز الرسمي بتنسيق HTML احترافي."""
    if not APP_PASSWORD:
        return False

    msg = EmailMessage()
    msg["Subject"] = f"تم تأكيد حجزك - DOME AI ({program_name}) 🏗️"
    msg["From"] = f"DOME Team <{SMTP_USER}>"
    msg["To"] = to_email

    text_body = f"مرحباً بك في DOME.\nتم تسجيل بريدك في قائمة انتظار: {program_name}.\nسنبلغك فور الإطلاق."
    msg.set_content(text_body)

    html_body = f"""
    <div style="direction: rtl; text-align: right; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 10px; border-top: 5px solid #BD583B; box-shadow: 0 4px 10px rgba(0,0,0,0.08);">
            <h2 style="color: #274055; margin-top: 0;">أهلاً بك في DOME AI 👋</h2>
            <p style="font-size: 16px; color: #555; line-height: 1.5;">شكراً لاهتمامك وثقتك بنا. لقد تم تسجيل بريدك بنجاح في قائمة الانتظار الخاصة بـ:</p>

            <div style="background-color: #eef2f5; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center; border: 1px dashed #BD583B;">
                <h3 style="color: #BD583B; margin: 0; font-size: 18px;">{program_name}</h3>
            </div>

            <p style="font-size: 14px; color: #666; line-height: 1.6;">
                <strong>ماذا سيحدث الآن؟</strong><br>
                أنت الآن في قائمة الأولوية، وستصلك دعوة ورابط خاص فور إطلاق النسخة الرسمية للحصول على تجربة مجانية حصرية قبل الجميع.
            </p>

            <hr style="border: 0; border-top: 1px solid #eee; margin: 25px 0;">
            <p style="font-size: 12px; color: #999; text-align: center; line-height: 1.6;">
                فريق عمل Arch-Dome AI<br>
                <a href="https://arch-dome.com" style="color: #BD583B; text-decoration: none; font-weight: bold;">www.arch-dome.com</a>
            </p>
        </div>
    </div>
    """
    msg.add_alternative(html_body, subtype="html")

    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.login(SMTP_USER, APP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.starttls()
                smtp.login(SMTP_USER, APP_PASSWORD)
                smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"❌ Mail send error: {e}")
        return False


def save_to_waitlist(email: str, program_name: str) -> str:
    """
    المنطق الذكي المتطابق مع المنصة:
    1. فحص هل الإيميل مسجل مسبقاً لنفس البرنامج -> إرجاع 'exists'
    2. إضافة البرنامج إذا كان مسجلاً لبرنامج آخر -> إرجاع 'updated'
    3. تسجيل جديد بالكامل -> إرجاع 'new'
    4. تسجيل الحدث في user_events ليظهر في لوحة تحكم الأونر في 'مهتمين V2/V3'.
    5. إرسال إيميل التأكيد الرسمي للعميل.
    """
    if not DATABASE_URL or not email:
        return "error"

    clean_email = email.strip().lower()
    # توحيد الرمز ليتطابق مع قاعدة البيانات (v2 أو v3)
    prog_key = "v2" if "2" in program_name else ("v3" if "3" in program_name else program_name.strip().lower())
    prog_display = "🏗️ مقايسة وحساب الكميات (V2)" if prog_key == "v2" else "👷 المساعد الشخصي للمهندس (V3)"

    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()

        cur.execute("SELECT interested_programs FROM public.program_waitlist WHERE LOWER(email) = LOWER(%s)", (clean_email,))
        row = cur.fetchone()

        if row:
            current_programs = row[0] or ""
            programs_list = [p.strip() for p in current_programs.split(',') if p.strip()]

            # فحص التكرار: هل سجل في هذا البرنامج مسبقاً؟
            if prog_key in programs_list or program_name in programs_list:
                cur.close()
                conn.close()
                return "exists"

            # إضافة البرنامج لقائمته
            programs_list.append(prog_key)
            updated_programs = ",".join(programs_list)
            cur.execute(
                "UPDATE public.program_waitlist SET interested_programs = %s, created_at = NOW() WHERE LOWER(email) = LOWER(%s)",
                (updated_programs, clean_email)
            )
            status = "updated"
        else:
            # عميل جديد بالكامل
            cur.execute(
                "INSERT INTO public.program_waitlist (email, interested_programs) VALUES (%s, %s)",
                (clean_email, prog_key)
            )
            status = "new"

        # تسجيل الحدث في user_events ليظهر في داشبورد الأونر تحت "مهتمين V2/V3"
        try:
            cur.execute(
                """
                INSERT INTO public.user_events (session_id, user_id, ip_address, event_type, details, timestamp)
                VALUES (%s, NULL, %s, %s, %s, NOW())
                """,
                ("landing_page", "landing", "join_waitlist", f"Joined {prog_key.upper()} Waitlist: {clean_email}")
            )
        except Exception as e_ev:
            print(f"Notice: event log skipped: {e_ev}")

        conn.commit()
        cur.close()
        conn.close()

        # إرسال إيميل التأكيد للعميل
        send_waitlist_email(clean_email, prog_display)

        return status

    except Exception as e:
        print(f"❌ خطأ أثناء حفظ قائمة الانتظار: {e}")
        return "error"


class CustomHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # منع التخزين المؤقت لضمان تحديث الصفحة دائماً
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        # دعم CORS لو تم الطلب من أي نطاق آخر
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/waitlist":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode("utf-8"))
                email = data.get("email", "").strip()
                program = data.get("program", "v2")

                status_result = save_to_waitlist(email, program)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {"status": status_result}
                self.wfile.write(json.dumps(response).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run():
    port = int(os.environ.get("PORT", 8080))
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, CustomHandler)
    print(f"🚀 Arch-Dome Landing server running on port {port}...")
    httpd.serve_forever()


if __name__ == "__main__":
    run()

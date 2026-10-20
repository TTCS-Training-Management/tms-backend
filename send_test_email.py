import smtplib
from email.mime.text import MIMEText
from app import app

def check_email_connection():
    print("=" * 60)
    print("KIEM TRA TRUC TIEP TOI GOOGLE GMAIL (SSL 465)")
    print("=" * 60)
    user = app.config.get("MAIL_USERNAME")
    pwd = app.config.get("MAIL_PASSWORD")
    print(f"User: {user}")
    print(f"Password: {pwd}")
    print("-" * 60)
    
    try:
        print("Dang ket noi toi smtp.gmail.com:465...")
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
        print("Dang dang nhap vao Google...")
        server.login(user, pwd)
        print(">>> DANG NHAP THANH CONG! <<<")
        
        msg = MIMEText("Xin chao Viet Nong!\n\nEmail nay duoc gui tu he thong dat lai mat khau Flask cua ban!")
        msg["Subject"] = "[TEST] Xac nhan gui email dat lai mat khau thanh cong"
        msg["From"] = user
        msg["To"] = user
        
        print("Dang gui thu...")
        server.send_message(msg)
        server.quit()
        print("\n>>> DA GUI THANH CONG! Hay kiem tra hop thu den beo810206@gmail.com! <<<")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print("\n[!] GOOGLE TU CHOI DANG NHAP (Loi 535 BadCredentials):")
        print(f"Code: {e.smtp_code} - Message: {e.smtp_error.decode('utf-8', errors='ignore')}")
        print("\n=> Nguyen nhan: Google bat buoc dung App Password (16 chu cai).")
        print("=> Link lay ma: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"\n[!] Loi ket noi: {e}")
        return False

if __name__ == "__main__":
    check_email_connection()

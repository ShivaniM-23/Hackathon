import os
import time
import imaplib
import email
from email.header import decode_header
import json
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")
API_URL = "http://localhost:8000/api/investigate"
INBOX_FILE = "vendor_inbox.json"

if not GMAIL_USER or not GMAIL_PASS:
    logger.error("GMAIL_USER or GMAIL_APP_PASSWORD not set in .env")
    exit(1)

def _load_inbox():
    if os.path.exists(INBOX_FILE):
        with open(INBOX_FILE, "r") as f:
            return json.load(f)
    return []

def _save_inbox(data):
    with open(INBOX_FILE, "w") as f:
        json.dump(data, f, indent=4)

def extract_domain(sender_email):
    """Extract domain from email address, ignoring common free providers."""
    domain = sender_email.split('@')[-1].lower()
    free_providers = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
    if domain in free_providers:
        return None
    return f"https://www.{domain}"

def check_mail():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")

        # Search for UNSEEN emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            return
            
        email_ids = messages[0].split()
        if not email_ids:
            return

        inbox_data = _load_inbox()
        
        for e_id in email_ids:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                        
                    sender = msg.get("From")
                    sender_email = sender.split("<")[-1].replace(">", "").strip()
                    
                    logger.info(f"New UNSEEN email from: {sender_email} - Subject: {subject}")
                    
                    target_url = extract_domain(sender_email)
                    if target_url:
                        logger.info(f"Extracted vendor domain: {target_url}. Starting automation...")
                        
                        # Trigger automated investigation
                        try:
                            res = httpx.post(API_URL, json={"url": target_url}, timeout=10)
                            if res.status_code == 200:
                                job_id = res.json().get("job_id")
                                
                                # Save to inbox for frontend automation page
                                new_entry = {
                                    "id": str(time.time()),
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "sender": sender,
                                    "email": sender_email,
                                    "subject": subject,
                                    "target_url": target_url,
                                    "job_id": job_id
                                }
                                inbox_data.insert(0, new_entry)
                                _save_inbox(inbox_data)
                                logger.info(f"Investigation Job {job_id} launched for {target_url}.")
                        except Exception as e:
                            logger.error(f"Failed to trigger investigation API: {e}")
                            
        mail.logout()
    except Exception as e:
        logger.error(f"IMAP Error: {e}")

if __name__ == "__main__":
    logger.info(f"Started Gmail Watcher for {GMAIL_USER}. Polling for UNSEEN vendor emails...")
    while True:
        check_mail()
        time.sleep(15)
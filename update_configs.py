import requests
import re
from urllib.parse import quote

# 1. تنظیمات
# لیست لینک‌های اشتراکی که می‌خواهید از آن‌ها کانفیگ بگیرید
# لینک‌های خود را در اینجا جایگزین کنید
SUBSCRIPTION_URLS = [
    "https://v2.alicivil.workers.dev/?list=fi&count=500&shuffle=true&unique=false",
    "https://raw.githubusercontent.com/yebekhe/vpn-fail/refs/heads/main/sub-link.txt",
    "https://example.com/sub3",
    "https://example.com/sub4",
    "https://example.com/sub5",
]

# نام جدید برای همه کانفیگ‌ها
NEW_NAME = "☬SHΞN™ 💾"

# فایل HTML هدف که باید به‌روزرسانی شود
TARGET_HTML_FILE = "Index.html"

# نشانگرهایی برای پیدا کردن بخش کانفیگ‌ها در فایل HTML
# خطی که بخش هدر با آن تمام می‌شود
HEADER_END_MARKER = "#hiddify-config:"
# خطی که بخش فوتر (اسکریپت) با آن شروع می‌شود
FOOTER_START_MARKER = "<script>"

def fetch_and_process_configs():
    """
    از تمام لینک‌ها کانفیگ‌ها را دانلود، پردازش و یکپارچه می‌کند.
    """
    all_configs = set()  # استفاده از set برای حذف خودکار موارد تکراری

    # الگو برای پیدا کردن پروتکل‌های مختلف
    protocol_pattern = re.compile(r'^(vless|vmess|ss|trojan|tuic|hy2|ssr)://')

    for url in SUBSCRIPTION_URLS:
        try:
            print(f"در حال دریافت کانفیگ از: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # بررسی خطا در درخواست
            content = response.text

            for line in content.splitlines():
                line = line.strip()
                if protocol_pattern.match(line):
                    # حذف نام قبلی (هر چیزی بعد از #)
                    base_config = line.split('#')[0]
                    # افزودن نام جدید به صورت URL-encoded
                    encoded_name = quote(NEW_NAME)
                    new_config_line = f"{base_config}#{encoded_name}"
                    all_configs.add(new_config_line)
        except requests.RequestException as e:
            print(f"خطا در دریافت اطلاعات از {url}: {e}")

    return list(all_configs)


def update_html_file(new_configs):
    """
    فایل HTML را با لیست جدید کانفیگ‌ها به‌روزرسانی می‌کند.
    """
    try:
        with open(TARGET_HTML_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # پیدا کردن موقعیت هدر و فوتر
        header_end_index = -1
        footer_start_index = -1

        for i, line in enumerate(lines):
            if HEADER_END_MARKER in line:
                header_end_index = i
            if FOOTER_START_MARKER in line:
                footer_start_index = i
                break
        
        if header_end_index == -1 or footer_start_index == -1:
            print("خطا: نشانگرهای شروع یا پایان در فایل HTML پیدا نشد.")
            return

        # ساخت محتوای جدید
        header = lines[:header_end_index + 1]
        footer = lines[footer_start_index:]
        
        # اضافه کردن یک خط خالی بین هدر و کانفیگ‌ها
        header.append('\n')

        # تبدیل لیست کانفیگ‌ها به رشته با خطوط جدید
        configs_content = [config + '\n' for config in new_configs]
        
        new_content_lines = header + configs_content + footer

        with open(TARGET_HTML_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_content_lines)

        print(f"فایل {TARGET_HTML_FILE} با {len(new_configs)} کانفیگ جدید با موفقیت به‌روزرسانی شد.")

    except FileNotFoundError:
        print(f"خطا: فایل {TARGET_HTML_FILE} پیدا نشد.")
    except Exception as e:
        print(f"یک خطای غیرمنتظره رخ داد: {e}")


if __name__ == "__main__":
    configs = fetch_and_process_configs()
    if configs:
        update_html_file(configs)
          

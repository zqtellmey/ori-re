import os
import sys
import time
import platform
import requests
from seleniumbase import SB

# ==================== 配置区 ====================
# Telegram 开关：True 为开启截图发送，False 为关闭
ENABLE_TELEGRAM_SCREENSHOTS = True

# 代理服务器配置
PROXY_URL = os.getenv("PROXY_SOCKS5", "socks5://127.0.0.1:10808")

# 从环境变量（GitHub Repository Secrets）中获取敏感网址和账号密码
LOGIN_URL = os.getenv("LOGIN_URL")
API_SERVER_URL = os.getenv("API_SERVER_URL")
SERVER_PANEL_URL = os.getenv("SERVER_PANEL_URL")
EMAIL = os.getenv("ORI_EMAIL")
PASSWORD = os.getenv("ORI_PASSWORD")
TG_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# ===============================================

def send_telegram_photo(sb, step_name):
    """如果开关打开，则通过代理截图并发送到 Telegram，统一加上 [Ori] 前缀"""
    if not ENABLE_TELEGRAM_SCREENSHOTS:
        return
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print(f"[Telegram] 未配置 Bot Token 或 Chat ID，跳过截图发送: {step_name}")
        return
    
    try:
        screenshot_path = f"screenshot_{int(time.time())}.png"
        sb.save_screenshot(screenshot_path)
        
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
        proxies = {
            "http": PROXY_URL,
            "https": PROXY_URL
        }
        caption_text = f"[Ori] 步骤截图: {step_name}"
        with open(screenshot_path, "rb") as photo_file:
            response = requests.post(
                url,
                data={"chat_id": TG_CHAT_ID, "caption": caption_text},
                files={"photo": photo_file},
                proxies=proxies,
                timeout=30
            )
        if response.status_code == 200:
            print(f"[Telegram] 成功发送步骤截图: {step_name}")
        else:
            print(f"[Telegram] 发送截图失败: {response.text}")
            
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
    except Exception as e:
        print(f"[Telegram] 发送截图异常: {e}")

def remove_ads(sb):
    """去广告模块：每次进行任何操作前先调用一次，删除指定的浮动 iframe 广告"""
    try:
        ad_script = """
        (function() {
            const ad_iframes = document.querySelectorAll('iframe');
            ad_iframes.forEach(el => {
                if (el.style.position === 'fixed' && el.style.zIndex === '2147483647') {
                    el.remove();
                }
            });
        })();
        """
        sb.execute_script(ad_script)
        print("[广告清除] 已执行去广告清理。")
    except Exception as e:
        print(f"[广告清除] 执行时出现异常: {e}")

# --- 针对对话框内 iframe 的精准点击与检测机制 ---
def handle_dialog_turnstile(sb):
    """先切入 turnstile iframe，再直接点击 checkbox 并检查状态"""
    try:
        for attempt in range(1, 6):
            print(f"[INFO] ⏱️ [对话框 CF 第 {attempt} 轮] 尝试切入 iframe 并点击验证...")
            sb.sleep(3)
            
            # 1. 尝试切入包含 turnstile 的 iframe
            switched = False
            try:
                if sb.is_element_visible('iframe[src*="turnstile"]'):
                    sb.switch_to_frame('iframe[src*="turnstile"]')
                    switched = True
            except Exception:
                pass

            # 2. 在 iframe 内部直接点击 checkbox
            if switched:
                try:
                    sb.click('input[type="checkbox"]')
                    print("[INFO] 已在 iframe 内部点击 checkbox。")
                except Exception:
                    try:
                        sb.execute_script('let cb = document.querySelector(\'input[type="checkbox"]\'); if(cb) cb.click();')
                    except Exception:
                        pass

            # 3. 检查是否已经打上勾
            is_checked = False
            try:
                is_checked = sb.is_checked('input[type="checkbox"]')
            except Exception:
                try:
                    is_checked = sb.execute_script('return document.querySelector(\'input[type="checkbox"]\').checked;')
                except Exception:
                    pass

            # 4. 无论如何，操作完先切回主文档
            if switched:
                try:
                    sb.switch_to_default_content()
                except Exception:
                    pass

            if is_checked:
                print("[INFO] ✅ 对话框内第二个 Cloudflare 验证已成功通过（已打勾）！")
                return True
            else:
                print(f"[INFO] ⏳ [对话框 CF 第 {attempt} 轮] 尚未勾选，准备重试...")
                
        return False
    except Exception as e:
        print(f"[WARN] 处理对话框 iframe 验证时发生异常: {e}")
        try:
            sb.switch_to_default_content()
        except Exception:
            pass
        return False

def main():
    # 尝试引入虚拟屏支持
    display = None
    if platform.system().lower() == "linux" and not os.environ.get("DISPLAY"):
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=False, size=(1280, 2400))
            display.start()
            os.environ["DISPLAY"] = display.new_display_var
            print("[INFO] 🖥️ Xvfb 虚拟纵向长屏桌面已成功启动 (1280x2400)")
        except Exception as e:
            print(f"[ERROR] 虚拟显示启动失败: {e}")

    try:
        # 使用 SeleniumBase 的 UC (Undetected ChromeDriver) 模式
        with SB(uc=True, test=True, headless=False, proxy=PROXY_URL) as sb:
            sb.driver.set_window_size(1280, 2400)
            sb.driver.set_page_load_timeout(40)

            print("=== 1. 访问登录页面 ===")
            remove_ads(sb)
            sb.open(LOGIN_URL)
            time.sleep(3)
            send_telegram_photo(sb, "1_访问登录页面")

            print("=== 2. 输入登录信息 ===")
            remove_ads(sb)
            sb.type('input[name="username"]', EMAIL)
            time.sleep(1)
            sb.type('input[name="password"]', PASSWORD)
            time.sleep(1)
            send_telegram_photo(sb, "2_输入账号密码")

            print("=== 3. 处理登录 Cloudflare 人机验证 ===")
            for attempt in range(1, 5):
                remove_ads(sb)
                print(f"尝试第 {attempt} 次点击登录 CF 验证...")
                try:
                    sb.click('input[type="checkbox"]')
                except Exception:
                    try:
                        sb.uc_gui_click_captcha()
                    except Exception:
                        pass
                
                time.sleep(3)
                
                is_checked = False
                try:
                    is_checked = sb.is_checked('input[type="checkbox"]')
                except Exception:
                    try:
                        is_checked = sb.execute_script('return document.querySelector(\'input[type="checkbox"]\').checked;')
                    except Exception:
                        pass

                if is_checked:
                    print("登录 Cloudflare 人机验证已通过！")
                    break
                else:
                    print("验证尚未通过，准备重试...")

            send_telegram_photo(sb, "3_完成登录人机验证")

            print("=== 4. 点击 Sign In 按钮 ===")
            remove_ads(sb)
            sb.click('button[type="submit"]')
            time.sleep(5)
            send_telegram_photo(sb, "4_登录后主页")

            print("=== 5. 通过 API 获取服务器状态 ===")
            cookies = sb.get_cookies()
            session = requests.Session()
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'])
            
            session.proxies = {
                "http": PROXY_URL,
                "https": PROXY_URL
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json"
            }
            
            response = session.get(API_SERVER_URL, headers=headers)
            if response.status_code != 200:
                print(f"API 请求失败，状态码: {response.status_code}")
                send_telegram_photo(sb, "5_API请求失败")
                return
                
            data = response.json()
            attributes = data.get("attributes", {})
            renewable = attributes.get("renewable", False)
            renewal_days = attributes.get("renewal", 999)
            
            print(f"服务器状态检查 -> renewable: {renewable}, renewal 剩余天数: {renewal_days}")
            send_telegram_photo(sb, f"5_服务器状态检查(剩余{renewal_days}天)")

            # 如果 renewable 为 true 并且剩余天数符合条件
            if renewable and renewal_days <= 7:
                print("满足续期条件，开始前往续期页面...")
                remove_ads(sb)
                sb.open(SERVER_PANEL_URL)
                time.sleep(3)
                send_telegram_photo(sb, "6_到达服务器详情页")

                print("检查页面上是否存在 Renew 按钮...")
                remove_ads(sb)
                
                has_renew_button = False
                try:
                    js_check_script = """
                    (function() {
                        const buttons = document.querySelectorAll('button');
                        for (let btn of buttons) {
                            if (btn.innerText.includes('Renew')) {
                                return true;
                            }
                        }
                        return false;
                    })();
                    """
                    has_renew_button = sb.execute_script(js_check_script)
                except Exception:
                    has_renew_button = False

                if has_renew_button:
                    print("检测到 Renew 按钮，准备点击...")
                    remove_ads(sb)
                    try:
                        sb.click('xpath://button[contains(., "Renew")]')
                    except Exception:
                        remove_ads(sb)
                        sb.execute_script("""
                            const buttons = document.querySelectorAll('button');
                            for (let btn of buttons) {
                                if (btn.innerText.includes('Renew')) {
                                    btn.click();
                                    break;
                                }
                            }
                        """)
                    
                    time.sleep(3)
                    send_telegram_photo(sb, "7_点击Renew之后")

                    print("检查并点击弹窗中的 Read Article 按钮...")
                    remove_ads(sb)
                    
                    clicked_read_article = False
                    try:
                        sb.click('xpath://button[contains(., "Read Article")]')
                        clicked_read_article = True
                    except Exception:
                        try:
                            remove_ads(sb)
                            js_read_script = """
                            (function() {
                                const buttons = document.querySelectorAll('button');
                                for (let btn of buttons) {
                                    if (btn.innerText.includes('Read Article')) {
                                        btn.click();
                                        return true;
                                    }
                                }
                                return false;
                            })();
                            """
                            clicked_read_article = sb.execute_script(js_read_script)
                        except Exception as e:
                            print(f"点击 Read Article 按钮时发生异常: {e}")

                    if clicked_read_article:
                        print("成功点击 Read Article 按钮。")
                    else:
                        print("提示：未能在弹窗中找到 Read Article 按钮。")

                    # 点击 Read Article 按钮后等待 20 秒
                    print("已点击 Read Article，等待 20 秒...")
                    time.sleep(20)
                    send_telegram_photo(sb, "8_点击ReadArticle等待20秒后")

                    print("=== 6. 处理对话框内 iframe 中的第二个 Cloudflare 人机验证 ===")
                    remove_ads(sb)
                    passed = handle_dialog_turnstile(sb)
                    
                    if not passed:
                        print("错误：对话框内的第二个 Cloudflare 人机验证未成功通过！")
                        send_telegram_photo(sb, "9_第二个人机验证未通过")
                        return

                    send_telegram_photo(sb, "9_完成第二个人机验证")

                    print("=== 7. 点击 Claim Renewal 按钮 ===")
                    remove_ads(sb)
                    
                    clicked_claim = False
                    try:
                        sb.click('xpath://button[contains(., "Claim Renewal")]')
                        clicked_claim = True
                    except Exception:
                        try:
                            remove_ads(sb)
                            js_claim_script = """
                            (function() {
                                const buttons = document.querySelectorAll('button');
                                for (let btn of buttons) {
                                    if (btn.innerText.includes('Claim Renewal')) {
                                        btn.click();
                                        break;
                                    }
                                }
                            })();
                            """
                            clicked_claim = sb.execute_script(js_claim_script)
                        except Exception as e:
                            print(f"点击 Claim Renewal 按钮时发生异常: {e}")

                    if clicked_claim:
                        print("成功点击 Claim Renewal 按钮。")
                    else:
                        print("提示：未能在对话框中找到 Claim Renewal 按钮。")

                    # 点击 Claim Renewal 后等待 5 秒
                    print("等待 5 秒后查询续期结果...")
                    time.sleep(5)
                    send_telegram_photo(sb, "10_点击ClaimRenewal之后")

                    print("再次通过 API 验证是否续期成功...")
                    check_response = session.get(API_SERVER_URL, headers=headers)
                    if check_response.status_code == 200:
                        new_data = check_response.json().get("attributes", {})
                        new_renewal_days = new_data.get("renewal")
                        print(f"续期后的剩余天数: {new_renewal_days}")
                        send_telegram_photo(sb, f"11_最终续期完成(新剩余天数{new_renewal_days}天)")
                else:
                    print("提示：当前页面未找到 Renew 按钮（可能还未到可续期时间或无需续期），跳过点击操作。")
                    send_telegram_photo(sb, "7_未找到Renew按钮跳过")
            else:
                print("当前不需要续期（renewable 为 false 或剩余天数大于设定阈值）。")
                send_telegram_photo(sb, "6_当前无需续期跳过操作")
    finally:
        if display:
            display.stop()
            print("[INFO] 虚拟显示服务已释放")

if __name__ == "__main__":
    main()

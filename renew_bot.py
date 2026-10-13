import os
import time
import requests
from seleniumbase import SB

# ==================== 配置区 ====================
# Telegram 开关：True 为开启截图发送，False 为关闭
ENABLE_TELEGRAM_SCREENSHOTS = True

# 代理服务器配置
PROXY_URL = "socks5://127.0.0.1:10808"

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
    """去广告模块：每次进行任何操作前先调用一次，删除指定的浮动 iframe 广告（使用块级作用域避免重复声明）"""
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

def main():
    # 使用 SeleniumBase 的 UC (Undetected ChromeDriver) 模式，配置代理和有头模式 (headless=False)
    with SB(uc=True, test=True, headless=False, proxy=PROXY_URL) as sb:
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
                sb.uc_gui_click_captcha()
            except Exception:
                try:
                    remove_ads(sb)
                    sb.click('input[type="checkbox"]')
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

        # 如果 renewable 为 true 并且剩余天数符合条件（测试时可设为 <= 7，实际使用建议改为 <= 2）
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

                print("=== 6. 处理 Read Article 之后的第二个 Cloudflare 人机验证 ===")
                for attempt in range(1, 5):
                    remove_ads(sb)
                    print(f"尝试第 {attempt} 次点击第二个 CF 验证...")
                    try:
                        sb.uc_gui_click_captcha()
                    except Exception:
                        try:
                            remove_ads(sb)
                            sb.click('input[type="checkbox"]')
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
                        print("第二个 Cloudflare 人机验证已通过！")
                        break
                    else:
                        print("验证尚未通过，准备重试...")

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
                                    return true;
                                }
                            }
                            return false;
                        })();
                        """
                        clicked_claim = sb.execute_script(js_claim_script)
                    except Exception as e:
                        print(f"点击 Claim Renewal 按钮时发生异常: {e}")

                if clicked_claim:
                    print("成功点击 Claim Renewal 按钮。")
                else:
                    print("提示：未能在页面上找到 Claim Renewal 按钮。")

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

if __name__ == "__main__":
    main()

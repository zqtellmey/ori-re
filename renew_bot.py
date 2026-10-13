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
    """去广告模块：精简逻辑，删除指定的浮动 iframe 广告"""
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

def handle_login_turnstile(sb):
    """登录页面的 CF 验证处理逻辑"""
    try:
        for attempt in range(1, 6):
            print(f"[INFO] ⏱️ [登录CF第 {attempt} 轮] 检查验证状态...")
            has_turnstile = sb.execute_script('return document.querySelector("input[name=\'cf-turnstile-response\']") !== null')
            
            if has_turnstile:
                print(f"[INFO] 🛡️ [登录CF第 {attempt} 轮] 发现验证框，触发点击...")
                sb.uc_gui_click_captcha()
                sb.sleep(4)
            else:
                print(f"[INFO] 🟢 [登录CF第 {attempt} 轮] 未检测到验证输入框。")

            is_passed = sb.execute_script('''
                (function() {
                    let respInput = document.querySelector("input[name='cf-turnstile-response']");
                    if (respInput && respInput.value && respInput.value.length > 0) return true;
                    let cb = document.querySelector('input[type="checkbox"]');
                    if (cb && cb.checked) return true;
                    return false;
                })();
            ''')

            if is_passed:
                print("[INFO] ✅ 登录 Cloudflare 人机验证已成功通过！")
                sb.sleep(2)
                return True
            else:
                sb.sleep(3)
        return False
    except Exception as e:
        print(f"[WARN] 登录 CF 验证异常: {e}")
        return False

def handle_modal_turnstile(sb):
    """针对弹窗内 Cloudflare Turnstile 的精准 iframe 穿透处理函数"""
    try:
        for attempt in range(1, 6):
            print(f"\n[INFO] 🔍 --- [对话框CF排查第 {attempt} 轮] ---")
            
            # 1. 检查 Token 是否已经生成
            has_response_input = sb.is_element_present('input[name="cf-turnstile-response"]')
            if has_response_input:
                try:
                    token_val = sb.execute_script("""
                        (function() {
                            let el = document.querySelector("input[name='cf-turnstile-response']");
                            return el ? el.value : '';
                        })();
                    """)
                    if token_val and len(token_val) > 10:
                        print(f"[INFO] ✅ 检测到 Token 已生成，第二个人机验证已成功通过！")
                        return True
                except Exception:
                    pass

            # 2. 尝试显式寻找并切入 Turnstile 对应的 iframe 内部进行点击
            print(f"[INFO] 🎯 正在寻找 Cloudflare 验证 iframe 并尝试点击...")
            clicked = False
            try:
                iframes = sb.find_elements("iframe")
                for index, frame in enumerate(iframes):
                    src = frame.get_attribute("src") or ""
                    if "challenges.cloudflare.com" in src or "turnstile" in src:
                        print(f"[INFO] 找到了目标验证 iframe (索引: {index})，准备切入...")
                        sb.switch_to_frame(frame)
                        if sb.is_element_present('input[type="checkbox"]'):
                            sb.click('input[type="checkbox"]')
                            clicked = True
                            print("[INFO] 成功点击了 iframe 内的验证复选框！")
                        else:
                            sb.execute_script("let box = document.querySelector('body'); if(box) box.click();")
                            clicked = True
                            print("[INFO] 已通过 JS 触发 iframe 内部点击。")
                        
                        sb.switch_to_default_content()
                        break
            except Exception as e:
                print(f"[DEBUG] iframe 交互过程提示: {e}")
                try:
                    sb.switch_to_default_content()
                except:
                    pass

            if not clicked:
                print(f"[INFO] 🖱️ 未能直接切入 iframe，触发 SeleniumBase 底层 GUI 物理点击兜底...")
                try:
                    sb.uc_gui_click_captcha()
                except Exception as e:
                    print(f"[DEBUG] uc_gui_click_captcha 提示: {e}")

            sb.sleep(4)
            
            # 3. 再次校验 Token
            if sb.is_element_present('input[name="cf-turnstile-response"]'):
                try:
                    token_val = sb.execute_script("""
                        (function() {
                            let el = document.querySelector("input[name='cf-turnstile-response']");
                            return el ? el.value : '';
                        })();
                    """)
                    if token_val and len(token_val) > 10:
                        print(f"[INFO] ✅ 验证成功，已捕获有效 Token！")
                        return True
                except Exception:
                    pass

        print("[WARN] ❌ 对话框内第二个人机验证在 5 轮排查后仍未通过。")
        try:
            sb.save_screenshot("debug_modal_turnstile.png")
            print("[INFO] 📸 已保存现场截图到 debug_modal_turnstile.png")
        except Exception:
            pass
        return False

    except Exception as e:
        print(f"[ERROR] 💥 handle_modal_turnstile 发生重大异常: {e}")
        return False

def main():
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
        remove_ads(sb)
        handle_login_turnstile(sb)
        send_telegram_photo(sb, "3_完成登录人机验证")

        print("=== 4. 点击 Sign In 按钮 ===")
        remove_ads(sb)
        sb.click('button[type="submit"]')
        time.sleep(6)
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
                try:
                    sb.click('xpath://button[contains(., "Renew")]')
                except Exception:
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
                
                clicked_read_article = False
                try:
                    sb.click('xpath://button[contains(., "Read Article")]')
                    clicked_read_article = True
                except Exception:
                    try:
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

                print("已点击 Read Article，等待 25 秒后转储当前页面的源码并发送至 Telegram...")
                time.sleep(25)
                send_telegram_photo(sb, "8_点击ReadArticle等待25秒后")

                # 转储当前网页源码，并直接通过 Telegram 发送文件
                try:
                    page_html = sb.get_page_source()
                    dump_filename = f"page_dump_{int(time.time())}.html"
                    with open(dump_filename, "w", encoding="utf-8") as f:
                        f.write(page_html)
                    print(f"[INFO] 📄 当前页面源码已成功转储: {dump_filename}")

                    if ENABLE_TELEGRAM_SCREENSHOTS and TG_BOT_TOKEN and TG_CHAT_ID:
                        doc_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendDocument"
                        proxies = {"http": PROXY_URL, "https": PROXY_URL}
                        with open(dump_filename, "rb") as doc_file:
                            requests.post(
                                doc_url,
                                data={"chat_id": TG_CHAT_ID, "caption": f"[Ori] 25秒后页面源码Dump: {dump_filename}"},
                                files={"document": doc_file},
                                proxies=proxies,
                                timeout=30
                            )
                        print("[Telegram] 已成功将源码 HTML 文件发送至 Telegram！")
                except Exception as e:
                    print(f"[WARN] 转储或发送源码异常: {e}")

                print("=== 6. 严格检查并处理对话框内的第二个 Cloudflare 人机验证 ===")
                remove_ads(sb)
                
                # 严格的前置校验：确保页面上确实存在验证元素或目标容器
                element_found = sb.execute_script("""
                    (function() {
                        let respInput = document.querySelector('input[name="cf-turnstile-response"]');
                        let checkbox = document.querySelector('input[type="checkbox"]');
                        let modalPortal = document.querySelector('#modal-portal');
                        
                        if (respInput || checkbox || (modalPortal && modalPortal.innerHTML.trim() !== '')) {
                            return true;
                        }
                        return false;
                    })();
                """)

                if not element_found:
                    print("[ERROR] ❌ 严格检查失败：当前页面未检测到第二个人机验证元素或目标对话框！")
                    send_telegram_photo(sb, "9_未找到第二个人机验证元素")
                    return

                print("[INFO] ✅ 已成功锁定人机验证元素，开始执行交互...")
                passed = handle_modal_turnstile(sb)
                
                if not passed:
                    print("错误：对话框内的第二个 Cloudflare 人机验证未成功通过，终止程序！")
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
                print("提示：当前页面未找到 Renew 按钮，跳过点击操作。")
                send_telegram_photo(sb, "7_未找到Renew按钮跳过")
        else:
            print("当前不需要续期。")
            send_telegram_photo(sb, "6_当前无需续期跳过操作")

if __name__ == "__main__":
    main()

import os
import sys
import time
import platform
import requests
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from seleniumbase import SB

# --- 全局配置 ---
OUTPUT_DIR = Path("output/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CN_TZ = timezone(timedelta(hours=8))

# --- 从环境读取变量 ---
LOGIN_URL = os.environ.get("LOGIN_URL", "").strip()
API_SERVER_URL = os.environ.get("API_SERVER_URL", "").strip()
SERVER_PANEL_URL = os.environ.get("SERVER_PANEL_URL", "").strip()
EMAIL = os.environ.get("ORI_EMAIL", "").strip()
PASSWORD = os.environ.get("ORI_PASSWORD", "").strip()
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
PROXY_SOCKS5 = os.environ.get("PROXY_SOCKS5", "").strip()

# --- 看门狗安全中断 ---
def watchdog(timeout_seconds: int):
    time.sleep(timeout_seconds)
    print(f"\n[WATCHDOG] 脚本执行超过 {timeout_seconds}s，正在执行暴力中断...")
    os._exit(0)

def cn_now() -> datetime:
    return datetime.now(CN_TZ)

def cn_time_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return cn_now().strftime(fmt)

def is_linux(): 
    return platform.system().lower() == "linux"

# --- 设置纵向超长虚拟桌面 ---
def setup_display():
    if is_linux() and not os.environ.get("DISPLAY"):
        try:
            from pyvirtualdisplay import Display
            d = Display(visible=False, size=(1280, 2400))
            d.start()
            os.environ["DISPLAY"] = d.new_display_var
            print("[INFO] 🖥️ Xvfb 虚拟纵向长屏桌面已成功启动 (1280x2400)")
            return d
        except Exception as e:
            print(f"[ERROR] 虚拟显示启动失败: {e}")
            sys.exit(1)
    return None

def shot(name: str) -> str:
    return str(OUTPUT_DIR / f"{cn_now().strftime('%H%M%S')}-{name}.png")

def notify(ok: bool, stage: str, msg: str = "", img: str = None):
    if not TG_BOT_TOKEN or not TG_CHAT_ID: 
        print("[WARN] TG 配置缺失，跳过通知。")
        return
    try:
        text = f"🔔 [Ori] {'✅' if ok else '❌'} {stage}\n{msg}\n⏰ {cn_time_str()}"
        requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage", json={"chat_id": TG_CHAT_ID, "text": text}, timeout=10)
        if img and Path(img).exists():
            with open(img, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto", data={"chat_id": TG_CHAT_ID}, files={"photo": f}, timeout=15)
    except Exception as e: 
        print(f"[ERROR] 发送 TG 通知失败: {e}")

# --- 参考脚本的高效过检机制（专门用于对话框内的第二个人机） ---
def handle_turnstile_exact_replica(sb) -> bool:
    try:
        for attempt in range(1, 3):
            print(f"[INFO] ⏱️ [对话框 CF 第 {attempt} 轮检测] 等待 5 秒等待拦截层加载...")
            sb.sleep(5)
            
            has_turnstile = sb.execute_script('return document.querySelector("input[name=\'cf-turnstile-response\']") !== null')
            
            if has_turnstile: 
                print(f"[INFO] 🛡️ [对话框 CF 第 {attempt} 轮] 发现 Cloudflare Turnstile 人机验证框！")
                sb.save_screenshot(shot(f"modal_cf_detected_{attempt}"))
                
                print(f"[INFO] ⚡ [对话框 CF 第 {attempt} 轮] 正在启动物理级 uc_gui_click_captcha() 穿透点击...")
                sb.uc_gui_click_captcha()
                
                print(f"[INFO] ⏳ [对话框 CF 第 {attempt} 轮] 物理点击完成，等待 5 秒让状态同步...")
                sb.sleep(5)
            else:
                print(f"[INFO] 🟢 [对话框 CF 第 {attempt} 轮] 当前视图未检测到 CF 拦截框。")
        
        return True
    except Exception as e: 
        print(f"[WARN] 穿透 CF 验证时发生异常: {e}")
        return False

# --- 去广告模块 ---
def remove_ads(sb):
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

# --- 恢复您原本稳定好用的登录逻辑 ---
def login(sb, user: str, pwd: str) -> bool:
    print(f"[INFO] 正在建立安全连接进入登录页面...")
    try:
        remove_ads(sb)
        sb.open(LOGIN_URL)
        time.sleep(3)
        
        init_login_shot = shot("init_opened_login_page")
        sb.save_screenshot(init_login_shot)
        notify(True, "登录页初始加载成功", "已成功打开登录页面，正在准备处理表单。", init_login_shot)

        print("=== 2. 输入登录信息 ===")
        remove_ads(sb)
        sb.type('input[name="username"]', user)
        time.sleep(1)
        sb.type('input[name="password"]', pwd)
        time.sleep(1)

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

        print("=== 4. 点击 Sign In 按钮 ===")
        remove_ads(sb)
        sb.click('button[type="submit"]')
        time.sleep(5)
        
        current_url = sb.get_current_url()
        print(f"[INFO] 登录判定完成，当前 URL: {current_url}")
        return "auth/login" not in current_url and "login" not in current_url
    except Exception as e:
        print(f"[WARN] 登录环节发生异常: {e}")
        try:
            sb.save_screenshot(shot("login_exception"))
        except:
            pass
        return False

def main():
    dog = threading.Thread(target=watchdog, args=(400,), daemon=True)
    dog.start()

    if not EMAIL or not PASSWORD or not LOGIN_URL:
        print("[ERROR] 必须在 Secrets 中配置对应的账号密码及网址变量")
        sys.exit(1)
    
    display = setup_display()

    try:
        opts = {"uc": True, "test": True, "locale": "zh", "headed": True, "timeout_multiplier": 0.5}
        if PROXY_SOCKS5: 
            opts["proxy"] = PROXY_SOCKS5
            print(f"[INFO] 代理通道已接入: {PROXY_SOCKS5}")
        
        with SB(**opts) as sb:
            sb.driver.set_window_size(1280, 2400)
            sb.driver.set_page_load_timeout(40)
            
            if login(sb, EMAIL, PASSWORD):
                print("✅ 成功突围至后台。")
                
                print("=== 5. 通过 API 获取服务器状态 ===")
                cookies = sb.get_cookies()
                session = requests.Session()
                for cookie in cookies:
                    session.cookies.set(cookie['name'], cookie['value'])
                
                if PROXY_SOCKS5:
                    session.proxies = {"http": PROXY_SOCKS5, "https": PROXY_SOCKS5}
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                }
                
                response = session.get(API_SERVER_URL, headers=headers)
                if response.status_code != 200:
                    print(f"API 请求失败，状态码: {response.status_code}")
                    return
                    
                data = response.json()
                attributes = data.get("attributes", {})
                renewable = attributes.get("renewable", False)
                renewal_days = attributes.get("renewal", 999)
                
                print(f"服务器状态检查 -> renewable: {renewable}, renewal 剩余天数: {renewal_days}")

                if renewable and renewal_days <= 7:
                    print("满足续期条件，开始前往续期页面...")
                    remove_ads(sb)
                    sb.open(SERVER_PANEL_URL)
                    time.sleep(3)

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

                        print("检查并点击弹窗中的 Read Article 按钮...")
                        remove_ads(sb)
                        clicked_read_article = sb.execute_script("""
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
                        """)
                        
                        if clicked_read_article:
                            print("成功点击 Read Article 按钮。")
                        
                        print("已点击 Read Article，等待 20 秒...")
                        time.sleep(20)

                        print("=== 6. 调度双重 CF 穿透机制处理对话框内的第二个人机验证 ===")
                        remove_ads(sb)
                        handle_turnstile_exact_replica(sb)

                        print("=== 7. 点击 Claim Renewal 按钮 ===")
                        remove_ads(sb)
                        sb.execute_script("""
                            (function() {
                                const buttons = document.querySelectorAll('button');
                                for (let btn of buttons) {
                                    if (btn.innerText.includes('Claim Renewal')) {
                                        btn.click();
                                        break;
                                    }
                                }
                            })();
                        """)
                        time.sleep(5)
                        
                        final_shot = shot("renew_final_status")
                        sb.save_screenshot(final_shot)
                        notify(True, "续期流程执行完毕", f"已完成续期操作，最新剩余天数检查中...", final_shot)
                    else:
                        print("提示：当前页面未找到 Renew 按钮。")
                else:
                    print("当前不需要续期。")
            else:
                raise Exception("未通过第一阶段的登录检查，地址仍为登录页。")

    except Exception as e:
        print(f"[FATAL] 全局中断异常: {e}")
        err_shot = shot("fatal_error")
        try:
            sb.save_screenshot(err_shot)
        except:
            pass
        notify(False, "脚本中断", f"运行异常错误: {str(e)}", err_shot)
    finally:
        if display: 
            display.stop()
            print("[INFO] 虚拟显示服务已释放")

    print("[INFO] 续期任务正常退出。")
    os._exit(0)

if __name__ == "__main__":
    main()

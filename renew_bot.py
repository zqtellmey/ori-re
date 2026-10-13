def handle_modal_turnstile(sb):
    """升级版对话框 CF 验证：强制滚动到可视区域中心并进行精确物理点击"""
    try:
        for attempt in range(1, 6):
            print(f"[INFO] ⏱️ [对话框CF第 {attempt} 轮] 检查弹窗中的人机验证...")
            
            # 1. 强力滚动定位：把验证组件滚动到视图正中心，确保 uc_gui_click_captcha 能点到
            try:
                sb.execute_script('''
                    let iframe = document.querySelector('iframe[src*="turnstile"]') || document.querySelector('iframe');
                    if (iframe) {
                        iframe.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    } else {
                        let widget = document.querySelector('.cf-turnstile') || document.querySelector('input[type="checkbox"]');
                        if (widget) widget.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                ''')
                time.sleep(1)
            except Exception:
                pass

            # 2. 触发物理点击
            try:
                sb.uc_gui_click_captcha()
            except Exception:
                pass

            # 3. 检查是否通过
            is_passed = sb.execute_script('''
                (function() {
                    let resp = document.querySelector("input[name='cf-turnstile-response']");
                    if (resp && resp.value && resp.value.length > 0) return true;
                    
                    let iframes = document.querySelectorAll('iframe');
                    for (let f of iframes) {
                        try {
                            let innerDoc = f.contentDocument || f.contentWindow.document;
                            let innerResp = innerDoc.querySelector("input[name='cf-turnstile-response']");
                            if (innerResp && innerResp.value && innerResp.value.length > 0) return true;
                            let innerCb = innerDoc.querySelector('input[type="checkbox"]');
                            if (innerCb && innerCb.checked) return true;
                        } catch(err) {}
                    }
                    return false;
                })();
            ''')

            if is_passed:
                print("[INFO] ✅ 对话框内第二个 Cloudflare 人机验证已成功通过！")
                sb.sleep(2)
                return True
            else:
                print(f"[INFO] ⏳ [对话框CF第 {attempt} 轮] 验证还在进行中，继续等待...")
                sb.sleep(4)
                
        print("[WARN] ⚠️ 对话框 CF 验证超时未能确认通过。")
        return False
    except Exception as e:
        print(f"[WARN] 处理对话框 CF 验证时发生异常: {e}")
        return False

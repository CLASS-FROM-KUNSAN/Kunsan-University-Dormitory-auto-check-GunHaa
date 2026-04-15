import os
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

# 1. 환경 변수 로드
USER_ID = os.environ.get('USER_ID')
USER_PW = os.environ.get('USER_PW')

# 완료 기록을 저장할 파일 이름
DONE_FILE = "check_done_today_Primary.txt"

def is_already_done():
    """오늘 이미 성공했는지 확인하는 함수"""
    if os.path.exists(DONE_FILE):
        with open(DONE_FILE, "r") as f:
            last_date = f.read().strip()
            if last_date == datetime.now().strftime("%Y-%m-%d"):
                return True
    return False

def mark_as_done():
    """오늘 성공했음을 기록하는 함수"""
    with open(DONE_FILE, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d"))


async def run():
    # 실행하자마자 오늘 이미 했는지 검사
    if is_already_done():
        print("✅ 오늘 일일체크를 이미 완료했습니다. 프로그램을 종료합니다.")
        return 

    async with async_playwright() as p:
        # 1. 브라우저 실행
        print("🚀 브라우저를 실행합니다...")
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            java_script_enabled=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
            
        print("1. 로그인 페이지 접속 및 로그인...")
        await page.goto("https://kis.kunsan.ac.kr/login.do", wait_until="networkidle")

        # 아이디 및 비밀번호 입력
        print("   - 입력창 대기 중...")
        try:
            id_input = page.locator("input#id, input[name='id'], input[type='text']").first
            await id_input.wait_for(state="visible", timeout=15000)
            await id_input.fill(USER_ID)
            
            pw_input = page.locator("input#pw, input[name='pw'], input[type='password']").first
            await pw_input.fill(USER_PW) 
            
            print("   - 정보 입력 완료")
            
            await asyncio.gather(
                page.wait_for_load_state("networkidle"),
                page.keyboard.press("Enter")
            )
            
        except Exception as e:
            print(f"❌ 입력창을 찾을 수 없습니다: {e}")
            await page.screenshot(path="login_error.png")
            await browser.close()
            return

        # 중복 로그인 팝업 처리
        try:
            await asyncio.sleep(2)
            confirm_btn = page.get_by_role("button", name="확인")
            if await confirm_btn.is_visible(timeout=3000):
                await confirm_btn.click()
                print("   - 중복 로그인 확인 클릭")
        except: 
            pass

        # 2. 통합정보 클릭 및 새 탭 감지
        print("2. '통합정보' 클릭 및 새 창 전환 대기...")
        try:
            target_element = page.locator("text='통합정보'").first
            await target_element.wait_for(state="visible", timeout=15000)
            
            async with context.expect_page(timeout=30000) as new_page_info:
                await target_element.dispatch_event("click")
            
            new_tab = await new_page_info.value
            await new_tab.wait_for_load_state("networkidle")
            print("   - 새 창 전환 성공!")
        except Exception as e:
            print(f"❌ 새 창 전환 실패: {e}")
            await browser.close()
            return

        # 3. 학생서비스 탭 클릭
        print("3. '학생서비스' 탭 클릭 중...")
        await asyncio.sleep(5) 
        await new_tab.get_by_text("학생서비스").first.click()

        # 4. 학생생활관 -> 일일체크신청 클릭
        print("4. '학생생활관' -> '일일체크신청' 찾는 중...")

        try:
            # '학생생활관' 클릭 시도
            dorm_menu = new_tab.get_by_text("학생생활관").first
            await dorm_menu.scroll_into_view_if_needed() # 화면 안으로 가져오기
            await dorm_menu.click(force=True)
            print("   - '학생생활관' 클릭 완료")
    
            # 잠시 대기 후 '일일체크신청' 찾기
            # 만약 프레임 문제라면 아래 줄에서 에러가 날 것입니다.
            target = new_tab.get_by_text("일일체크신청").last
    
            # 요소가 나타날 때까지 대기 (최대 10초)
            await target.wait_for(state="attached", timeout=10000)
            await target.click()
            print("✅ '일일체크신청' 클릭 성공!")

        except Exception as e:
            print(f"❌ 실패 원인: {e}")
            # 실패한 순간의 화면을 저장합니다. (GitHub Actions Artifacts에서 확인 가능)
            await new_tab.screenshot(path="error_debug.png", full_page=True)
            print("📸 디버깅용 스크린샷 'error_debug.png' 저장됨")
            raise e # 에러를 다시 던져서 전체 프로세스 중단
    
        # 5. 저장 및 예 클릭
        print("5. '저장' 버튼 클릭 시도...")
        await asyncio.sleep(5) 

        try:
            save_button = new_tab.locator("button:has-text('저장'), input[value='저장'], .btn_save").first
            await save_button.wait_for(state="visible", timeout=15000)
            await save_button.click(force=True)
            print("   - 저장 버튼 클릭 성공!")

        except Exception as e:
            print(f"❌ 저장 버튼을 못 찾았습니다. 프레임 내 수동 탐색 시도...")
            found = False
            for frame in new_tab.frames:
                try:
                    target = frame.get_by_role("button", name="저장").or_(frame.locator("text='저장'"))
                    if await target.count() > 0:
                        await target.first.click()
                        print("   - 프레임 내부에서 저장 버튼 발견 및 클릭!")
                        found = True
                        break
                except: 
                    continue
            
            if not found:
                print("❌ 모든 방법으로도 저장 버튼을 찾을 수 없습니다.")
                await new_tab.screenshot(path="save_button_missing.png")
                await browser.close()
                return

        # 6. '예' 버튼 팝업 독립적 처리
        print("6. 최종 팝업 처리 시작 (엔터키 및 모든 버튼 탐색)...")
        await asyncio.sleep(2) 

        final_success = False
        
        # 1단계: 엔터키 강제 입력
        await new_tab.keyboard.press("Enter")
        print("   - [시도] 엔터키 입력 완료")
        await asyncio.sleep(1)

        # 2단계: 모든 프레임을 뒤져서 수락 버튼 클릭
        for _ in range(10): 
            for f in new_tab.frames:
                try:
                    btns = f.locator("button, input[type='button'], input[type='submit'], a.btn")
                    count = await btns.count()
                    
                    for i in range(count):
                        target = btns.nth(i)
                        txt = await target.inner_text()
                        val = await target.get_attribute("value") or ""
                        
                        if any(x in (txt + val) for x in ["예", "확인", "OK", "yes"]):
                            await target.click(force=True)
                            print(f"   - [성공] '{txt or val}' 버튼을 찾아 클릭했습니다!")
                            final_success = True
                            break
                except: 
                    continue
            
            if final_success: 
                break
            await asyncio.sleep(0.5)

        # 3단계: 브라우저 기본 대화상자 처리
        if not final_success:
            try:
                new_tab.on("dialog", lambda dialog: dialog.accept())
                print("   - [시도] 브라우저 대화상자 자동 수락 시도")
            except: 
                pass

        print("🎉 ✅ 팝업 처리를 완료했습니다. 결과를 확인합니다.")
        await asyncio.sleep(2)
      
        # 7. 사용자 최종 확인 단계
        print("📸 최종 처리 결과를 스크린샷으로 저장합니다...")
        await asyncio.sleep(2)
        
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CHECK_{now}_Primary.png"
        
        await new_tab.screenshot(path=filename)

        # 오늘 성공했음을 파일에 기록
        mark_as_done()
        
        print("\n" + "="*50)
        print(f"✅ 저장 완료: {filename}")
        print("👀 브라우저 화면에서 '일일체크'가 정상적으로 되었는지 확인하세요.")
        print("="*50)

        # 5초 대기 후 깔끔하게 종료
        await asyncio.sleep(5) 
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

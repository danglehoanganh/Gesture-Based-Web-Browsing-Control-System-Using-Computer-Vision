import cv2
import time
import json
import asyncio
import websockets
import threading
import joblib
import base64
import os
from typing import Any
from collections import deque, Counter
from mediapipe.python.solutions import hands as mp_hands
from mediapipe.python.solutions import drawing_utils as mp_draw

from gesture_utils import (
    get_landmark_point,
    detect_swipe,
    extract_landmark_features,
    count_fingers,
    detect_rule_based_gesture
)


from smoothing import MovingAverageSmoother


# ==============================
# CẤU HÌNH
# ==============================

CAMERA_ID = 0
MODEL_PATH = os.path.join(os.path.dirname(__file__), "gesture_model.pkl")

CONFIDENCE_THRESHOLD = 0.70

CLICK_COOLDOWN = 1.0
SCROLL_COOLDOWN = 0.5
SWIPE_COOLDOWN = 0.8

clients = set()

latest_data = {
    "gesture": "NONE",
    "right_cursor_x": 0.5,
    "right_cursor_y": 0.5,
    "left_cursor_x": 0.5,
    "left_cursor_y": 0.5,
    "active_hand": "NONE",
    "confidence": 0.0,
    "camera_frame": "",
    "fps": 0.0,
}




label_map = {
    0: "NONE",
    1: "CLICK",
    2: "SCROLL_DOWN",
    3: "SCROLL_UP",
}

gesture_buffer = {"Right": deque(maxlen=10), "Left": deque(maxlen=10)}
x_history = {"Right": deque(maxlen=10), "Left": deque(maxlen=10)}

last_click_time = 0
last_scroll_time = 0
last_swipe_time = 0

# Load model with fallback
model = None
try:
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        print(f"✅ Đã load model từ {MODEL_PATH}")
    else:
        print(f"⚠️ Không tìm thấy model tại {MODEL_PATH}, sử dụng rule-based detection")
except Exception as e:
    print(f"⚠️ Lỗi load model: {e}, sử dụng rule-based detection")


# ==============================
# LÀM MƯỢT GESTURE
# ==============================

def smooth_gesture(raw_gesture, hand):
    # Only keep allowed gestures
    if raw_gesture not in ["NONE", "CLICK", "SCROLL_DOWN", "SCROLL_UP", "NEXT", "PREV"]:
        raw_gesture = "NONE"
    gesture_buffer[hand].append(raw_gesture)

    if len(gesture_buffer[hand]) < 4:
        return "NONE"

    most_common, count = Counter(gesture_buffer[hand]).most_common(1)[0]

    # Giảm ngưỡng để tránh kẹt NONE khi gesture dao động
    if most_common != "NONE" and count >= 4:
        return most_common

    return "NONE"


# ==============================
# WEBSOCKET
# ==============================

async def websocket_handler(websocket):
    clients.add(websocket)
    print("🌐 Web đã kết nối")

    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)
        print("🌐 Web đã ngắt kết nối")


async def websocket_server():
    async with websockets.serve(websocket_handler, "localhost", 8765):
        print("🚀 WebSocket chạy tại ws://localhost:8765")
        await asyncio.Future()


async def broadcast_loop():
    while True:
        if clients:
            message = json.dumps(latest_data)
            disconnected = []

            for client in list(clients):
                try:
                    await client.send(message)
                except:
                    disconnected.append(client)

            for client in disconnected:
                clients.remove(client)

        await asyncio.sleep(0.033)  # ~30fps


def run_websocket():
    async def main_async():
        await asyncio.gather(
            websocket_server(),
            broadcast_loop()
        )

    asyncio.run(main_async())


# ==============================
# KIỂM SOÁT COOLDOWN
# ==============================

def apply_cooldown(gesture):
    global last_click_time, last_scroll_time, last_swipe_time

    now = time.time()

    if gesture == "CLICK":
        if now - last_click_time >= CLICK_COOLDOWN:
            last_click_time = now
            return "CLICK"
        return "NONE"

    if gesture in ["SCROLL_DOWN", "SCROLL_UP"]:
        if now - last_scroll_time >= SCROLL_COOLDOWN:
            last_scroll_time = now
            return gesture
        return "NONE"

    if gesture in ["NEXT", "PREV"]:
        if now - last_swipe_time >= SWIPE_COOLDOWN:
            last_swipe_time = now
            return gesture
        return "NONE"

    # Ignore all other gestures
    return "NONE"


# ==============================
# NHẬN DIỆN GESTURE
# ==============================

def recognize_gesture(hand_landmarks, handedness, frame_w, frame_h):
    """Hybrid gesture recognition: rule-based + ML fallback"""
    fingers = count_fingers(hand_landmarks, handedness)
    thumb_point = get_landmark_point(hand_landmarks, 4, frame_w, frame_h)
    index_point = get_landmark_point(hand_landmarks, 8, frame_w, frame_h)
    rule_gesture = detect_rule_based_gesture(fingers, thumb_point, index_point)
    if rule_gesture not in ["NONE", "CLICK", "SCROLL_DOWN", "SCROLL_UP"]:
        rule_gesture = "NONE"
    if rule_gesture != "NONE":
        return rule_gesture, 1.0

    if model is not None:
        try:
            features = extract_landmark_features(hand_landmarks)
            proba = model.predict_proba([features])[0]
            max_proba = max(proba)
            prediction = model.classes_[proba.argmax()]
            mapped = label_map.get(int(prediction), "NONE")
            if mapped not in ["NONE", "CLICK", "SCROLL_DOWN", "SCROLL_UP"]:
                mapped = "NONE"
            if max_proba >= CONFIDENCE_THRESHOLD:
                return mapped, max_proba
        except Exception as e:
            print(f"ML prediction error: {e}")

    return "NONE", 0.0


# ==============================
# CAMERA + NHẬN DIỆN
# ==============================

def run_camera():
    global latest_data

    hands = mp_hands.Hands(
        max_num_hands=2,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )

    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("📷 Đang chạy camera...")
    print("🛑 Nhấn 'q' để thoát.")

    frame_count = 0
    start_time = time.time()

    # Multi-hand state
    right_cursor = [0.5, 0.5]
    left_cursor = [0.5, 0.5]

    # Cursor smoother (keep for interaction stability)
    right_pos_smoother = MovingAverageSmoother(window=5)


    right_gesture = "NONE"
    left_gesture = "NONE"
    right_conf = 0.0
    left_conf = 0.0
    active_hand = "NONE"

    while True:
        success, frame = cap.read()
        if not success:
            print("❌ Không mở được camera.")
            break
        frame = cv2.flip(frame, 1)
        frame_h, frame_w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result: Any = hands.process(rgb)

        # Reset per frame
        right_gesture = "NONE"
        left_gesture = "NONE"
        right_conf = 0.0
        left_conf = 0.0
        right_cursor = [0.5, 0.5]
        left_cursor = [0.5, 0.5]
        active_hand = "NONE"

        if result.multi_hand_landmarks and result.multi_handedness:
            for idx, (hand_landmarks, handness) in enumerate(zip(result.multi_hand_landmarks, result.multi_handedness)):
                handedness = handness.classification[0].label  # 'Right' or 'Left'
                mp_draw.draw_landmarks(frame, hand_landmarks, list(mp_hands.HAND_CONNECTIONS))
                index_tip = hand_landmarks.landmark[8]
                wrist = hand_landmarks.landmark[0]
                x_history[handedness].append(wrist.x)
                # Detect swipe for left hand only
                swipe_gesture = detect_swipe(x_history[handedness]) if handedness == "Left" else None
                gesture, conf = recognize_gesture(hand_landmarks, handedness, frame_w, frame_h)
                gesture = smooth_gesture(gesture, handedness)
                if handedness == "Right":
                    right_cursor = [index_tip.x, index_tip.y]
                    if gesture == "CLICK":
                        right_gesture = gesture
                        right_conf = conf
                    else:
                        right_gesture = "NONE"
                        right_conf = conf
                elif handedness == "Left":
                    left_cursor = [index_tip.x, index_tip.y]
                    if swipe_gesture in ["NEXT", "PREV"]:
                        left_gesture = swipe_gesture
                        left_conf = 1.0
                    elif gesture in ["SCROLL_UP", "SCROLL_DOWN"]:
                        left_gesture = gesture
                        left_conf = conf
                    else:
                        left_gesture = "NONE"
                        left_conf = conf
                # Draw cursor
                color = (0,0,255) if handedness=="Right" else (0,255,0)
                pt = get_landmark_point(hand_landmarks, 8, frame_w, frame_h)
                cv2.circle(frame, pt, 12, color, -1)
                cv2.putText(frame, f"{handedness} hand", (pt[0]-30, pt[1]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        else:
            gesture_buffer["Right"].clear()
            gesture_buffer["Left"].clear()
            x_history["Right"].clear()
            x_history["Left"].clear()

        # Priority: right CLICK, left SCROLL/NEXT/PREV
        gesture = "NONE"
        confidence = 0.0
        if right_gesture == "CLICK":
            gesture = "CLICK"
            confidence = right_conf
            active_hand = "Right"
        elif left_gesture in ["SCROLL_UP", "SCROLL_DOWN", "NEXT", "PREV"]:
            gesture = left_gesture
            confidence = left_conf
            active_hand = "Left"

        # Apply cooldown to prevent gesture spam
        gesture = apply_cooldown(gesture)

        # Smooth cursor position for more stable hover/click
        right_sx, right_sy = right_pos_smoother.update(right_cursor[0], right_cursor[1])
        right_cursor[0], right_cursor[1] = right_sx, right_sy

        # Encode frame to base64 for frontend display


        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frame_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')

        # Calculate FPS

        frame_count += 1
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0

        latest_data = {
            "gesture": gesture,
            "right_cursor_x": right_cursor[0],
            "right_cursor_y": right_cursor[1],
            "left_cursor_x": left_cursor[0],
            "left_cursor_y": left_cursor[1],
            "active_hand": active_hand,
            "confidence": confidence,
            "camera_frame": frame_base64,
            "fps": fps,
        }
        # Draw info on frame (show both cursors, gestures, confidence)
        cv2.putText(
            frame,
            f"Right: ({right_cursor[0]:.2f},{right_cursor[1]:.2f}) {right_gesture} {right_conf:.2f}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )
        cv2.putText(
            frame,
            f"Left: ({left_cursor[0]:.2f},{left_cursor[1]:.2f}) {left_gesture} {left_conf:.2f}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 200, 255),
            2
        )
        cv2.putText(
            frame,
            f"Send: {gesture} ({active_hand}) {confidence:.2f}",
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2
        )
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (20, 160),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (200, 200, 200),
            2
        )

        cv2.imshow("Hand Gesture Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


# ==============================
# MAIN
# ==============================

if __name__ == "__main__":
    ws_thread = threading.Thread(target=run_websocket, daemon=True)
    ws_thread.start()

    run_camera()

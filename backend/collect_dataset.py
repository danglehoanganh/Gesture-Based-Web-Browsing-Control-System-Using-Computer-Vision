import cv2
import os
import time
from typing import Any
from mediapipe.python.solutions import hands as mp_hands
from mediapipe.python.solutions import drawing_utils as mp_draw

DATASET_DIR = "dataset_images"

LABELS = {
    0: "NONE",
    1: "CLICK",
    2: "SCROLL_DOWN",
    3: "SCROLL_UP",
    
}

print("Danh sách nhãn:")
for key, value in LABELS.items():
    print(key, "=", value)

label = int(input("Nhập label muốn thu: "))

if label not in LABELS:
    print("Label không hợp lệ.")
    exit()

label_name = LABELS[label]
save_dir = os.path.join(DATASET_DIR, label_name)
os.makedirs(save_dir, exist_ok=True)

hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

cap = cv2.VideoCapture(0)

count = 0
save_delay = 0.15
last_save_time = 0

print("Nhấn S để bắt đầu/dừng lưu ảnh")
print("Nhấn Q để thoát")

is_saving = False

while True:
    success, frame = cap.read()

    if not success:
        print("Không mở được camera.")
        break

    frame = cv2.flip(frame, 1)
    display_frame = frame.copy()

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result: Any = hands.process(rgb)

    hand_detected = False

    if result.multi_hand_landmarks:
        hand_detected = True

        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(
                display_frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS  # type: ignore[reportArgumentType]
            )

    now = time.time()

    if is_saving and hand_detected and now - last_save_time >= save_delay:
        filename = f"{label_name}_{count:05d}.jpg"
        save_path = os.path.join(save_dir, filename)

        # Lưu ảnh gốc, chưa vẽ landmark
        cv2.imwrite(save_path, frame)

        count += 1
        last_save_time = now

    status = "SAVING" if is_saving else "PAUSED"

    cv2.putText(
        display_frame,
        f"Label: {label_name}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 0),
        2
    )

    cv2.putText(
        display_frame,
        f"Status: {status} | Images: {count}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 255),
        2
    )

    cv2.imshow("Collect Image Dataset", display_frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("s"):
        is_saving = not is_saving

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

print("Đã lưu", count, "ảnh vào thư mục:", save_dir)
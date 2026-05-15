import cv2
import pandas as pd
import joblib
import os
from typing import Any
from mediapipe.python.solutions import hands as mp_hands

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score

DATASET_DIR = "dataset_images"
MODEL_FILE = "gesture_model.pkl"

LABELS = {
    "NONE": 0,
    "CLICK": 1,
    "SCROLL_DOWN": 2,
    "SCROLL_UP": 3,
    "NEXT": 4,
    "PREV": 5
}

label_names = {
    0: "NONE",
    1: "CLICK",
    2: "SCROLL_DOWN",
    3: "SCROLL_UP",
    4: "NEXT",
    5: "PREV"
}

hands = mp_hands.Hands(
    static_image_mode=True,
    max_num_hands=1,
    min_detection_confidence=0.6
)


def extract_landmark_features(hand_landmarks):
    features = []

    wrist = hand_landmarks.landmark[0]

    for lm in hand_landmarks.landmark:
        features.append(lm.x - wrist.x)
        features.append(lm.y - wrist.y)
        features.append(lm.z - wrist.z)

    return features


X = []
y = []

if not os.path.exists(DATASET_DIR):
    print("Chưa có thư mục dataset_images.")
    exit()

for label_name, label_id in LABELS.items():
    folder_path = os.path.join(DATASET_DIR, label_name)

    if not os.path.exists(folder_path):
        print("Thiếu thư mục:", folder_path)
        continue

    for file_name in os.listdir(folder_path):
        if not file_name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        image_path = os.path.join(folder_path, file_name)

        image = cv2.imread(image_path)

        if image is None:
            continue

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        result: Any = hands.process(rgb)

        if result.multi_hand_landmarks:
            hand_landmarks = result.multi_hand_landmarks[0]
            features = extract_landmark_features(hand_landmarks)

            X.append(features)
            y.append(label_id)

print("Tổng số mẫu hợp lệ:", len(X))

if len(X) == 0:
    print("Không trích xuất được landmark từ ảnh.")
    exit()

X = pd.DataFrame(X)
y = pd.Series(y)

print("Số feature:", X.shape[1])
print("Số label:", y.nunique())

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=25,
    random_state=42
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)

print("Accuracy:", accuracy)
print(classification_report(
    y_test,
    y_pred,
    target_names=[label_names[i] for i in sorted(y.unique())]
))

joblib.dump(model, MODEL_FILE)

print("Đã lưu model:", MODEL_FILE)
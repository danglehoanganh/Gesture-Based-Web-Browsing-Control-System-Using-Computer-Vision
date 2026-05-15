import numpy as np


def distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))


def get_landmark_point(hand_landmarks, index, frame_width, frame_height):
    lm = hand_landmarks.landmark[index]
    return int(lm.x * frame_width), int(lm.y * frame_height)


def extract_landmark_features(hand_landmarks):
    features = []

    wrist = hand_landmarks.landmark[0]

    for lm in hand_landmarks.landmark:
        features.append(lm.x - wrist.x)
        features.append(lm.y - wrist.y)
        features.append(lm.z - wrist.z)

    return features


def count_fingers(hand_landmarks, handedness):
    fingers = []

    tip_ids = [4, 8, 12, 16, 20]
    pip_ids = [3, 6, 10, 14, 18]

    # Ngón cái
    if handedness == "Right":
        if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
            fingers.append(1)
        else:
            fingers.append(0)
    else:
        if hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x:
            fingers.append(1)
        else:
            fingers.append(0)

    # 4 ngón còn lại
    for tip, pip in zip(tip_ids[1:], pip_ids[1:]):
        if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[pip].y:
            fingers.append(1)
        else:
            fingers.append(0)

    return fingers


def detect_rule_based_gesture(fingers, thumb_point, index_point):
    thumb, index, middle, ring, pinky = fingers

    pinch_distance = distance(thumb_point, index_point)

    if pinch_distance < 35:
        return "CLICK"

    if fingers == [0, 1, 0, 0, 0]:
        return "SCROLL_DOWN"

    if fingers == [0, 1, 1, 0, 0]:
        return "SCROLL_UP"

    if fingers == [1, 1, 1, 1, 1]:
        return "NONE"

    if fingers == [0, 0, 0, 0, 0]:
        return "PAUSE"

    return "NONE"


def detect_swipe(history):
    if len(history) < 8:
        return None

    start_x = history[0]
    end_x = history[-1]
    movement = end_x - start_x

    if movement > 0.18:
        history.clear()
        return "NEXT"

    if movement < -0.18:
        history.clear()
        return "PREV"

    return None
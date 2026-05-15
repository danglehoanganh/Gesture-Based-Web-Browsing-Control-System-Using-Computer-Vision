// Gesture News Control (single, unified implementation)

const demoWindow = document.getElementById("demoWindow");
const topicCards = document.querySelectorAll(".topic-card");
const newsCards = document.querySelectorAll(".news-card");

const gestureText = document.getElementById("gestureText");
const actionText = document.getElementById("actionText");
const activeHandText = document.getElementById("activeHand");
const confidenceText = document.getElementById("confidence");
const topicText = document.getElementById("topicText");
const newsText = document.getElementById("newsText");
const logList = document.getElementById("logList");
const cameraFrame = document.getElementById("cameraFrame");
const cameraStatus = document.getElementById("cameraStatus");

const themeBtn = document.getElementById("themeBtn");
const rightCursor = document.getElementById("rightCursor");
const leftCursor = document.getElementById("leftCursor");

// Hover cursor effect (click gesture uses rightCursor)
const buttonsToHover = document.querySelectorAll(
  "button, .like-btn, .save-btn, .read-btn, .gesture-actions button, .menu-item, .topic-card"
);
buttonsToHover.forEach((btn) => {
  btn.addEventListener("mouseenter", () => rightCursor.classList.add("hovering-btn"));
  btn.addEventListener("mouseleave", () => rightCursor.classList.remove("hovering-btn"));
});

let currentTopicIndex = 0;
let currentNewsIndex = 0;
let visibleNews = Array.from(newsCards);
let lastNonNoneGesture = "";

let socket = null;
let reconnectInterval = null;

// ==============================
// Voice Assistant (SpeechSynthesis)
// ==============================
const voiceText = document.getElementById("voiceText");

const gestureVoiceMap = {
  CLICK: "Clicked",
  SCROLL_DOWN: "Scrolling down",
  SCROLL_UP: "Scrolling up",
  NEXT: "Next topic",
  PREV: "Previous topic",
};

let lastVoiceGesture = "";
let lastVoiceTime = 0;
const VOICE_COOLDOWN_MS = 1200;
let isSpeaking = false;

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  if (!text) return;

  try {
    window.speechSynthesis.cancel();
  } catch (e) {}

  if (!('SpeechSynthesisUtterance' in window)) return;

  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "en-US";
  // If your system doesn't have en-US voices, browser will fallback to default installed language.
  utter.rate = 1;
  utter.pitch = 1;

  const voiceBox = document.querySelector(".voice-box");

  isSpeaking = true;
  if (voiceBox) voiceBox.classList.add("reading");

  utter.onend = () => {
    isSpeaking = false;
    if (voiceBox) voiceBox.classList.remove("reading");
  };

  utter.onerror = () => {
    isSpeaking = false;
    if (voiceBox) voiceBox.classList.remove("reading");
  };

  window.speechSynthesis.speak(utter);
}

function handleGestureVoice(gesture) {
  if (!voiceText) return;
  if (!gesture || gesture === "NONE") return;

  const now = Date.now();
  const gestureChanged = gesture !== lastVoiceGesture;
  const cooldownOk = now - lastVoiceTime >= VOICE_COOLDOWN_MS;

  // If gesture didn't change and still within cooldown -> skip
  if (!gestureChanged && !cooldownOk) return;
  // If currently speaking -> avoid interrupt spam unless gesture changed and cooldown OK
  if (isSpeaking && !gestureChanged) return;
  if (!cooldownOk && gestureChanged && isSpeaking) return;

  const msg = gestureVoiceMap[gesture];
  if (!msg) return;

  lastVoiceGesture = gesture;
  lastVoiceTime = now;

  voiceText.innerText = msg;
  speak(msg);

}

function setAction(text) {
  actionText.innerText = text;
}

function addLog(type, message) {
  const li = document.createElement("li");
  const time = new Date().toLocaleTimeString();

  if (type === "GESTURE") {
    // message: { gesture, text }
    const t = message?.text ?? message?.gesture ?? "";
    li.innerText = `[${time}] ${message.gesture} → ${t}`;
  } else {
    li.innerText = `[${time}] ${type}: ${message}`;
  }

  logList.prepend(li);
  while (logList.children.length > 30) logList.removeChild(logList.lastChild);
}

function toggleTheme() {
  document.body.classList.toggle("dark");
  setAction("Đổi giao diện sáng/tối");
  addLog("ACTION", "Đổi giao diện");
}

function updateCursor(cursorElem, x, y) {
  // x/y are normalized [0..1]
  const rect = demoWindow.getBoundingClientRect();
  const cursorX = x * rect.width;
  const cursorY = y * rect.height;
  cursorElem.style.left = `${cursorX}px`;
  cursorElem.style.top = `${cursorY}px`;
  cursorElem.style.display = "block";
}




function clickAtCursor(cursorElem) {
  const cursorRect = cursorElem.getBoundingClientRect();
  const x = cursorRect.left + cursorRect.width / 2;
  const y = cursorRect.top + cursorRect.height / 2;

  // Hide temporarily so elementFromPoint doesn't hit cursor itself
  cursorElem.style.display = "none";
  const element = document.elementFromPoint(x, y);
  cursorElem.style.display = "block";

  if (!element) {
    setAction("Không có phần tử để click");
    return;
  }

  element.click();

  if (element.classList.contains("like-btn")) return setAction("Click nút Like");
  if (element.classList.contains("topic-card")) return setAction("Click chọn chủ đề");
  if (element.id === "themeBtn") return setAction("Click đổi giao diện");
  setAction("Click trong giao diện");
}

function scrollNewsDown() {
  if (currentNewsIndex < visibleNews.length - 1) {
    currentNewsIndex++;
    focusNews(currentNewsIndex);
    setAction("Lướt xuống tin tiếp theo");
  } else {
    setAction("Đang ở tin cuối");
  }
}

function scrollNewsUp() {
  if (currentNewsIndex > 0) {
    currentNewsIndex--;
    focusNews(currentNewsIndex);
    setAction("Lướt lên tin trước");
  } else {
    setAction("Đang ở tin đầu");
  }
}

function focusNews(index) {
  visibleNews.forEach((card) => card.classList.remove("active-news"));
  const card = visibleNews[index];
  if (!card) return;

  card.classList.add("active-news");
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  newsText.innerText = `${index + 1} / ${visibleNews.length}`;
}

function selectTopic(index) {
  topicCards.forEach((card) => card.classList.remove("active"));

  const selectedCard = topicCards[index];
  if (!selectedCard) return;

  selectedCard.classList.add("active");
  selectedCard.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });

  const topic = selectedCard.dataset.topic;
  const topicName = selectedCard.innerText;
  topicText.innerText = topicName;

  visibleNews = [];
  newsCards.forEach((card) => {
    const match = topic === "all" || card.dataset.topic === topic;
    if (match) {
      card.classList.remove("hide");
      visibleNews.push(card);
    } else {
      card.classList.add("hide");
      card.classList.remove("active-news");
    }
  });

  currentNewsIndex = 0;
  focusNews(currentNewsIndex);
  addLog("TOPIC", `Chọn chủ đề: ${topicName}`);
}

function nextTopic() {
  if (currentTopicIndex < topicCards.length - 1) {
    currentTopicIndex++;
    selectTopic(currentTopicIndex);
    setAction("Vuốt sang phải: đổi chủ đề tiếp theo");
  } else {
    setAction("Đang ở chủ đề cuối");
  }
}

function prevTopic() {
  if (currentTopicIndex > 0) {
    currentTopicIndex--;
    selectTopic(currentTopicIndex);
    setAction("Vuốt sang trái: quay lại chủ đề trước");
  } else {
    setAction("Đang ở chủ đề đầu");
  }
}

function handleGesture(data) {
  const gesture = data.gesture || "NONE";

  gestureText.innerText = gesture;



  // Voice feedback realtime (frontend only)
  handleGestureVoice(gesture);

  activeHandText.innerText = data.active_hand || "NONE";
  confidenceText.innerText =
    typeof data.confidence === "number" ? data.confidence.toFixed(2) : "0.00";

  // Update cursors
  if (typeof data.right_cursor_x === "number" && typeof data.right_cursor_y === "number") {
    updateCursor(rightCursor, data.right_cursor_x, data.right_cursor_y);
  } else {
    rightCursor.style.display = "none";
  }

  if (typeof data.left_cursor_x === "number" && typeof data.left_cursor_y === "number") {
    updateCursor(leftCursor, data.left_cursor_x, data.left_cursor_y);
  } else {
    leftCursor.style.display = "none";
  }

  // Highlight active hand
  rightCursor.classList.toggle("active", data.active_hand === "Right");
  leftCursor.classList.toggle("active", data.active_hand === "Left");

  // Camera
  if (data.camera_frame) {
    cameraFrame.style.display = "block";
    document.querySelector(".camera-placeholder").style.display = "none";
    cameraFrame.src = `data:image/jpeg;base64,${data.camera_frame}`;
    cameraStatus.innerText = "Camera đang hoạt động";
    cameraStatus.classList.add("connected");
  }

  // Log gestures (debounce NONE and same gesture)
  if (gesture !== "NONE" && gesture !== lastNonNoneGesture) {
    const text = gestureVoiceMap[gesture] || gesture;
    addLog("GESTURE", { gesture, text });
    lastNonNoneGesture = gesture;
  }


  switch (gesture) {
    case "SCROLL_DOWN":
      scrollNewsDown();
      break;
    case "SCROLL_UP":
      scrollNewsUp();
      break;
    case "NEXT":
      nextTopic();
      break;
    case "PREV":
      prevTopic();
      break;
    case "CLICK":
      clickAtCursor(rightCursor);
      break;
    case "CHANGE_THEME":
      toggleTheme();
      break;
  }
}

function connectWebSocket() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;

  setAction("Đang kết nối WebSocket...");

  socket = new WebSocket("ws://localhost:8765");

  socket.onopen = function () {
    setAction("Đã kết nối Python");
    cameraStatus.innerText = "Đã kết nối - chờ camera...";
    cameraStatus.classList.remove("connected");
    addLog("SYSTEM", "Frontend đã kết nối WebSocket");

    if (reconnectInterval) {
      clearInterval(reconnectInterval);
      reconnectInterval = null;
    }
  };

  socket.onclose = function () {
    setAction("Mất kết nối Python - đang thử kết nối lại...");
    cameraStatus.innerText = "Mất kết nối";
    cameraStatus.classList.remove("connected");
    addLog("SYSTEM", "WebSocket đã ngắt kết nối");
    startReconnect();
  };

  socket.onerror = function () {
    setAction("Lỗi WebSocket");
  };

  socket.onmessage = function (event) {
    const data = JSON.parse(event.data);
    handleGesture(data);
  };
}

function startReconnect() {
  if (!reconnectInterval) {
    reconnectInterval = setInterval(() => connectWebSocket(), 3000);
  }
}

// UI events
connectWebSocket();

themeBtn.onclick = function () {
  toggleTheme();
};

// Topic cards
topicCards.forEach((card, index) => {
  card.onclick = function () {
    currentTopicIndex = index;
    selectTopic(index);
  };
});

// Like buttons
newsCards.forEach((card) => {
  const btn = card.querySelector(".like-btn");
  if (!btn) return;

  btn.onclick = function () {
    btn.classList.toggle("liked");
    btn.innerText = btn.classList.contains("liked") ? "Liked" : "Like";
    setAction(btn.classList.contains("liked") ? "Đã thích tin" : "Đã bỏ thích");
  };
});

// Initial state
selectTopic(0);
focusNews(0);


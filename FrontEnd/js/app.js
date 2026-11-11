const connectButton = document.querySelector("#connect-button");
const disconnectButton = document.querySelector("#disconnect-button");
const sensorState = document.querySelector("#sensor-state");
const sensorReading = document.querySelector("#sensor-reading");
const sensorReadingTitle = document.querySelector("#sensor-reading-title");
const sensorReadingDetail = document.querySelector("#sensor-reading-detail");
const connectionMessage = document.querySelector("#connection-message");
const connectionDetail = document.querySelector("#connection-detail");
const lecturerName = document.querySelector("#lecturer-name");
const logoutButton = document.querySelector("#logout-button");
const arrivalCount = document.querySelector("#arrival-count");
const presentList = document.querySelector("#present-list");
const lateCount = document.querySelector("#late-count");
const lateList = document.querySelector("#late-list");
const currentTime = document.querySelector("#current-time");
const timeLimit = document.querySelector("#time-limit");
const timeRemaining = document.querySelector("#time-remaining");
const startTimer = document.querySelector("#start-timer");
const savedTimeLimit = Number.parseInt(localStorage.getItem("attendance-window-minutes"), 10);
const defaultTimeLimit = Number.isInteger(savedTimeLimit) && savedTimeLimit >= 1 && savedTimeLimit <= 1440
  ? savedTimeLimit
  : 30;
let attendanceWindowEndsAt = null;
let sensorConnected = false;

function updateCurrentTime() {
  currentTime.textContent = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date());
}

function updateTimeRemaining() {
  if (attendanceWindowEndsAt === null) {
    timeRemaining.textContent = "00:00";
    return;
  }
  const remainingSeconds = Math.max(
    0,
    Math.ceil((attendanceWindowEndsAt - Date.now()) / 1000),
  );
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  timeRemaining.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  if (remainingSeconds === 0) {
    startTimer.textContent = "Start timer";
  }
}

function getAttendanceTimestamp(value) {
  return Date.parse(`${value}Z`);
}

timeLimit.value = String(defaultTimeLimit);
timeLimit.addEventListener("change", () => {
  const minutes = Number.parseInt(timeLimit.value, 10);
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) {
    timeLimit.value = "30";
    localStorage.setItem("attendance-window-minutes", "30");
  } else {
    localStorage.setItem("attendance-window-minutes", String(minutes));
  }
  attendanceWindowEndsAt = null;
  startTimer.textContent = "Start timer";
  updateTimeRemaining();
});

startTimer.addEventListener("click", () => {
  let minutes = Number.parseInt(timeLimit.value, 10);
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) {
    minutes = 30;
    timeLimit.value = "30";
    localStorage.setItem("attendance-window-minutes", "30");
  }
  attendanceWindowEndsAt = Date.now() + minutes * 60 * 1000;
  startTimer.textContent = "Restart timer";
  updateTimeRemaining();
});

async function loadLecturer() {
  const response = await fetch("/api/me", { cache: "no-store" });
  if (!response.ok) {
    window.location.href = "/auth.html";
    return;
  }
  const lecturer = await response.json();
  lecturerName.textContent = lecturer.full_name;
}

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  const response = await fetch("/api/logout", { method: "POST" });
  if (response.ok) {
    window.location.href = "/auth.html";
    return;
  }
  logoutButton.disabled = false;
});

async function updateAttendance() {
  const response = await fetch("/api/attendance", { cache: "no-store" });
  if (!response.ok) {
    return;
  }
  const students = await response.json();
  arrivalCount.textContent = students.length;
  presentList.replaceChildren(...students.map((student) => {
    const item = document.createElement("li");
    item.textContent = `${student.full_name} (${student.student_id})`;
    return item;
  }));

  const timerEnded = attendanceWindowEndsAt !== null
    && Date.now() >= attendanceWindowEndsAt;
  const lateStudents = timerEnded
    ? students.filter((student) => getAttendanceTimestamp(student.detected_at) > attendanceWindowEndsAt)
    : [];
  lateCount.textContent = lateStudents.length;
  lateList.replaceChildren(...lateStudents.map((student) => {
    const item = document.createElement("li");
    item.textContent = `${student.full_name} (${student.student_id})`;
    return item;
  }));
}

async function scanForStudent() {
  if (!sensorConnected) {
    return;
  }
  const response = await fetch("/api/recognition/scan", {
    method: "POST",
    cache: "no-store",
  });
  if (response.ok) {
    await updateAttendance();
  }
}

function showDisconnectedState() {
  sensorConnected = false;
  sensorState.textContent = "Not connected";
  sensorReading.classList.remove("sensor-reading--active");
  sensorReadingTitle.textContent = "Sensor unavailable";
  sensorReadingDetail.textContent = "Unable to read movement status.";
  connectionMessage.textContent = "Motion sensor not connected";
  connectionDetail.textContent = "Press Connect to check the PIR sensor on GPIO 4.";
  disconnectButton.disabled = true;
}

async function updateSensorStatus() {
  try {
    const response = await fetch("/api/sensor", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Sensor API returned an error");
    }

    const sensor = await response.json();
    if (sensor.connected !== true) {
      throw new Error("Sensor is not connected");
    }

    sensorConnected = true;
    disconnectButton.disabled = false;
    const motionDetected = sensor.motion === true;
    sensorState.textContent = motionDetected ? "Motion detected" : "Connected";
    sensorReading.classList.toggle("sensor-reading--active", motionDetected);
    sensorReadingTitle.textContent = motionDetected ? "Motion detected" : "Ready to detect";
    sensorReadingDetail.textContent = motionDetected
      ? "Movement detected near the door."
      : "Waiting for movement near the door";
    connectionMessage.textContent = "Motion sensor connected";
    connectionDetail.textContent = motionDetected
      ? "Motion is currently being detected."
      : "PIR sensor is ready and waiting for movement.";
  } catch (error) {
    showDisconnectedState();
  }
}

async function setSensorConnection(action) {
  connectButton.disabled = true;
  disconnectButton.disabled = true;
  connectionMessage.textContent = action === "connect"
    ? "Connecting to motion sensor..."
    : "Disconnecting motion sensor...";

  try {
    const response = await fetch("/api/sensor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (!response.ok) {
      throw new Error("Sensor connection request failed");
    }
    await updateSensorStatus();
  } catch (error) {
    showDisconnectedState();
  } finally {
    connectButton.disabled = false;
    connectButton.textContent = sensorConnected ? "Connected" : "Try again";
  }
}

connectButton.addEventListener("click", () => setSensorConnection("connect"));
disconnectButton.addEventListener("click", () => setSensorConnection("disconnect"));
loadLecturer();
updateAttendance();
updateCurrentTime();
updateTimeRemaining();

setInterval(() => {
  if (sensorConnected) {
    updateSensorStatus();
  }
}, 1000);

setInterval(updateCurrentTime, 1000);
setInterval(updateTimeRemaining, 1000);
setInterval(updateAttendance, 2000);
setInterval(scanForStudent, 3000);

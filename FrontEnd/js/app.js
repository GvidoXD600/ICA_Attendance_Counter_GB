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
let sensorConnected = false;

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

setInterval(() => {
  if (sensorConnected) {
    updateSensorStatus();
  }
}, 1000);

setInterval(updateAttendance, 2000);
setInterval(scanForStudent, 3000);

# ICA: IoT Attendance Counter

## Introduction
For this Individual Continuous Assessment (ICA), I am developing an automated attendance counter using a **Raspberry Pi 5** and a **PIR motion sensor**. 

The system helps lecturers track attendance effortlessly as students walk into the classroom.

## How It Works
1. **Motion Detection:** The PIR sensor placed at the entrance connects to the Raspberry Pi 5 GPIO pins to detect when a student walks into the classroom.
2. **Web Dashboard Alert:** A lightweight Python web server running on the Pi sends an alert to a web dashboard, prompting the lecturer with a "Motion detected: Add student?" notification.
3. **Present vs. Late Tracking:** The lecturer can set a class start time on the website.
   - Students entering before the cutoff are marked **Present**.
   - Students entering after the cutoff are automatically categorized as **Late**.
4. **Attendance Log:** All records are saved locally on the Pi's database so the lecturer can view or export the final attendance list easily.

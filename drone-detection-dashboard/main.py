import serial
import threading
import tkinter as tk
from datetime import datetime
from PIL import Image, ImageTk
import io
import time
import glob

# === SERIAL CONFIG ===
def find_openmv_port():
    ports = glob.glob('/dev/tty.usbmodem*')
    return ports[0] if ports else None

SERIAL_PORT = find_openmv_port()
BAUD_RATE = 115200

if not SERIAL_PORT:
    raise RuntimeError("❌ OpenMV port not found!")

detection_times = []

# === UI SETUP ===
root = tk.Tk()
root.title("Drone Detection Dashboard")
root.geometry("650x700")
root.configure(bg='white')

status_var = tk.StringVar(value="Status: Clear")
count_var = tk.StringVar(value="Detections: 0")

tk.Label(root, textvariable=status_var, font=("Helvetica", 16), bg='white').pack(pady=10)
tk.Label(root, textvariable=count_var, font=("Helvetica", 14), bg='white').pack(pady=5)

log_box = tk.Listbox(root, height=8, width=50)
log_box.pack(pady=10)

# Snapshot preview
image_label = tk.Label(root)
image_label.pack(pady=10)

def read_jpeg(ser):
    data = b""
    while True:
        byte = ser.read(1)
        if not byte:
            break
        data += byte
        if data[-2:] == b'\xFF\xD9':
            break

    return data

def update_ui_with_detection(timestamp, image_data=None, detections=[]):
    from PIL import Image, ImageDraw, ImageFilter, ImageTk

    detection_times.append(timestamp)
    status_var.set("Status: Drone Detected")
    count_var.set(f"Detections: {len(detection_times)}")
    log_box.insert(tk.END, timestamp.strftime("%Y-%m-%d %H:%M:%S"))

    if not image_data:
        return

    img = Image.open(io.BytesIO(image_data)).convert("RGBA")
    img = img.resize((320, 240))

    if detections:
        heatmap = Image.new("L", (320, 240), 0)
        draw = ImageDraw.Draw(heatmap)
        for x, y, score in detections:
            intensity = int(min(score * 255, 255))
            draw.ellipse((x-20, y-20, x+20, y+20), fill=intensity)
        heatmap = heatmap.filter(ImageFilter.GaussianBlur(radius=10)).convert("RGBA")

        draw = ImageDraw.Draw(img)
        for x, y, score in detections:
            size = 24  # size of bounding box
            left = x - size // 2
            top = y - size // 2
            right = x + size // 2
            bottom = y + size // 2
            draw.rectangle((left, top, right, bottom), outline="red", width=2)

        # Red-tint the grayscale
        for y in range(heatmap.height):
            for x in range(heatmap.width):
                alpha = heatmap.getpixel((x, y))[0]
                heatmap.putpixel((x, y), (255, 0, 0, alpha))

        final = Image.alpha_composite(img, heatmap)
    else:
        final = img

    final_tk = ImageTk.PhotoImage(final)
    image_label.configure(image=final_tk)
    image_label.image = final_tk

    root.after(5000, lambda: status_var.set("Status: Clear"))

# === Serial Listener Thread ===
def serial_reader():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
        while True:
            line = ser.readline().decode(errors='ignore').strip()
            if "DRONE DETECTED" in line:
                print("[INFO] Detection received")
                timestamp = datetime.now()
                detections = []
                img_data = None

                while True:
                    marker = ser.readline().decode(errors='ignore').strip()

                    if marker.startswith("x "):
                        parts = marker.split()
                        try:
                            x = int(parts[1])
                            y = int(parts[3])
                            score = float(parts[5])
                            detections.append((x, y, score))
                        except Exception as e:
                            print("[WARN] Failed to parse:", marker, "|", e)

                    elif marker == "IMG_START":
                        print("[INFO] Receiving image...")
                        img_data = read_jpeg(ser)
                        print(f"[INFO] Image received ({len(img_data)} bytes)")

                    elif marker == "END_FRAME":
                        break  # all done

                update_ui_with_detection(timestamp, img_data, detections)

    except serial.SerialException as e:
        print("[ERROR] Serial Error:", e)


# Start serial listener
threading.Thread(target=serial_reader, daemon=True).start()

# Start GUI
root.mainloop()
import cv2
import numpy as np
import tensorflow as tf
import os

# --- CONFIGURATION ---
model_path = "trained.tflite"
video_path = "new.mp4"
output_path = "output_fomo.mp4"
min_conf = 0.5  # Confidence threshold

# --- Load the TFLite model ---
interpreter = tf.lite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

input_height, input_width = input_details[0]['shape'][1:3]

# --- Open video ---
if not os.path.exists(video_path):
    raise FileNotFoundError(f"Video file not found: {video_path}")

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)
orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# --- Setup video writer ---
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_path, fourcc, fps, (orig_width, orig_height))

# --- Main loop ---
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Resize and convert to grayscale
    resized = cv2.resize(frame, (input_width, input_height))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # Prepare input tensor (quantize)
    gray = gray.astype(np.int16) - 128
    gray = np.clip(gray, -128, 127)
    gray_input = np.expand_dims(gray, axis=(0, -1)).astype(np.int8)

    # Inference
    interpreter.set_tensor(input_details[0]['index'], gray_input)
    interpreter.invoke()
    output = interpreter.get_tensor(output_details[0]['index'])[0]  # [H, W, C]

    # Process detections
    for class_id in range(1, output.shape[2]):  # skip background class 0
        heatmap = output[:, :, class_id]
        ys, xs = np.where(heatmap > min_conf)

        for x, y in zip(xs, ys):
            # Scale from model space → input space
            cx_input = (x + 0.5) * (input_width / output.shape[1])
            cy_input = (y + 0.5) * (input_height / output.shape[0])

            # Scale input → original image size
            cx = int(cx_input * (orig_width / input_width))
            cy = int(cy_input * (orig_height / input_height))

            # Draw rectangle centered at detection point
            # Draw rectangle centered at detection point
            box_size = 80  # adjust as needed
            top_left = (cx - box_size, cy - box_size)
            bottom_right = (cx + box_size, cy + box_size)
            cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)

    # Write frame to output video
    out.write(frame)

# --- Cleanup ---
cap.release()
out.release()
print(f"[✓] Detection complete. Output saved to: {output_path}")

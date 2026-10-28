import cv2, sys, json, statistics

src, start, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
cap = cv2.VideoCapture(src)
W = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
H = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

xs, t = [], start
while t < start + dur:

    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        break
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    side = int(H * 0.08)
    faces = casc.detectMultiScale(gray, 1.1, 5, minSize=(side, side))
    if len(faces):
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])  # largest face = speaker
        xs.append(x + w / 2)
    t += 0.5  # sample 2x per second

crop_w = int(H * 9 / 16) // 2 * 2
vertical = W <= crop_w
cx = statistics.median(xs) if xs else W / 2
crop_x = 0 if vertical else int(min(max(cx - crop_w / 2, 0), W - crop_w)) // 2 * 2
print(json.dumps({"crop_w": crop_w, "crop_x": crop_x, "faces_found": len(xs),
                  "vertical_already": vertical, "src_w": int(W), "src_h": int(H)}))

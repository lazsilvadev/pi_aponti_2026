import math
import os
import struct
import wave

OUT = os.path.join(os.path.dirname(__file__), "..", "beep_demo.wav")
OUT = os.path.normpath(OUT)
SAMPLE_RATE = 44100
DURATION_MS = 100
VOLUME = 0.5

# two tones: 320Hz then 400Hz, with 80ms gap
tones = [320, 400]
pauses = [0.08]

frames = []
for i, freq in enumerate(tones):
    duration = DURATION_MS / 1000.0
    for n in range(int(SAMPLE_RATE * duration)):
        t = n / SAMPLE_RATE
        sample = VOLUME * math.sin(2 * math.pi * freq * t)
        frames.append(sample)
    if i < len(pauses):
        pause_len = int(SAMPLE_RATE * pauses[i])
        for n in range(pause_len):
            frames.append(0.0)

# write WAV
with wave.open(OUT, "w") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)  # 16 bits
    wf.setframerate(SAMPLE_RATE)
    for s in frames:
        val = int(s * 32767.0)
        data = struct.pack("<h", val)
        wf.writeframesraw(data)

print(f"WAV gerado: {OUT}")

# tentar tocar no Windows
try:
    import winsound

    winsound.PlaySound(OUT, winsound.SND_FILENAME)
    print("Áudio reproduzido via winsound.")
except Exception:
    print("Não foi possível reproduzir automaticamente; arquivo salvo.")

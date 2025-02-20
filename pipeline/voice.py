import sounddevice as sd
import numpy as np
import queue
import threading
import whisper
import warnings
import scipy.io.wavfile as wav

warnings.simplefilter(action='ignore', category=FutureWarning)

class VoiceRecognition:
    def __init__(self):
        self.model = whisper.load_model("medium")
        self.q = queue.Queue()
        self.recording = threading.Event()
        self.audio_data = np.array([], dtype=np.float32)

    def toggle_recording(self, button):
        if self.recording.is_set():
            self.stop_recording()
            button.config(text="Commencer l'enregistrement")
        else:
            button.config(text="Arrêter l'enregistrement")
            threading.Thread(target=self.start_recording, daemon=True).start()

    def start_recording(self):
        self.recording.set()
        self.audio_data = np.array([], dtype=np.float32)

        def callback(indata, frames, time, status):
            if self.recording.is_set():
                self.q.put(indata.copy())

        with sd.InputStream(callback=callback, channels=1, samplerate=16000, dtype='float32'):
            while self.recording.is_set():
                sd.sleep(100)

    def stop_recording(self):
        self.recording.clear()
        audio_list = []
        while not self.q.empty():
            audio_chunk = self.q.get()
            audio_list.append(audio_chunk)
        if audio_list:
            self.audio_data = np.concatenate(audio_list, axis=0).flatten()
            print(self.audio_data)
            file_path = "test_audio.wav"
            wav.write(file_path, 16000, self.audio_data)
            print("Enregistrement terminé. Fichier sauvegardé :", file_path)
            return file_path
        return None

    def transcribe_audio(self, audio_data):
        if audio_data is not None and audio_data.size > 0:
            result = self.model.transcribe(audio_data, fp16=False)
            with open("output.txt", "w") as f:
                f.write(f"1,{result['text']}")  # id, transcription
            return "output.txt"
        return None

    def process_audio_file(self, file_path):
        result = self.model.transcribe(file_path, fp16=False)
        print(result['text'])
        # enlever les espaces en début et fin de la transcription
        result = result['text'].strip()
        with open("output.txt", "w") as f:
                f.write(f"1,{result}")  # id, transcription
        return "output.txt"

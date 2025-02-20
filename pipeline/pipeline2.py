from voice import VoiceRecognition
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from nlp_processor import NLPProcessor
from ner_processor import NERProcessor
from graph_maker import load_or_create_graph, find_path_with_stops

class Pipeline:
    def __init__(self):
        self.voice = VoiceRecognition()
        self.nlp = NLPProcessor()
        self.ner = NERProcessor()
        self.graph = load_or_create_graph()

    def process_voice_query(self, button):
        if self.voice.recording.is_set():
            print("Arrêt de l'enregistrement...")

            file_path = self.voice.stop_recording()
            print("Fichier enregistré :", file_path)

            if file_path:
                print("Transcription en cours...")
                transcription = self.voice.process_audio_file(file_path)

                if transcription:
                    self.handle_file(transcription)
                    return {'success': True, 'transcription': transcription}
            return {'success': False, 'error': "Erreur d'enregistrement"}

        else:
            print("Démarrage de l'enregistrement...")
            self.voice.toggle_recording(button)

    def handle_file(self, file_path):
        ext = Path(file_path).suffix.lower()
        if ext in {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}:
            transcription = self.voice.process_audio_file(file_path)
            ext = Path(transcription).suffix.lower()
            file_path = transcription
        if ext == ".txt":
            with open(file_path, 'r') as f:
                text_file = f.readlines()
                for line in text_file:
                    line = line.strip()
                    if "," in line:
                        id, query = line.split(",")
                        print(f"Query {id}: {query}")
                        result = self.process_query(query)
                        print("\n" + format_result(result))
                    else:
                        messagebox.showerror("Error", "Format incorrect dans le fichier texte.")
        else:
            messagebox.showerror("Erreur", "Type de fichier non pris en charge.")

    def process_text(self, text):
        nlp_result = self.nlp.process_query(text)
        if not nlp_result:
            messagebox.showerror("Erreur", "Requête non valide")
            return

        ner_result = self.ner.process_text(text)
        if not ner_result['depart'] or not ner_result['arrivee']:
            messagebox.showerror("Erreur", "Gares de départ et/ou d'arrivée introuvables")
            return

        path = find_path_with_stops(self.graph, ner_result['depart'], ner_result['arrivee'], ner_result.get('etape'))
        if not path:
            messagebox.showerror("Erreur", "Aucun itinéraire trouvé")
            return

        self.save_to_file(text)
        messagebox.showinfo("Succès", "Traitement terminé et fichier sauvegardé !")

    def save_to_file(self, content):
        with open("output.txt", "w") as f:
            # f.write(content)
            f.write(f"1,{content}")
            return "output.txt"


    def process_query(self, query: str):
        """
        Traite une requête utilisateur de bout en bout

        Args:
            query (str): La requête en langage naturel

        Returns:
            dict: Les résultats du traitement
        """
        # 1. Vérifier si la requête est valide avec le NLP
        nlp_result = self.nlp.process_query(query)
        if not nlp_result:
            return {
                'success': False,
                'error': "La requête n'est pas une demande d'itinéraire valide"
            }

        # 2. Extraire les entités (gares) avec le NER
        ner_result = self.ner.process_text(query)
        if not ner_result['depart'] or not ner_result['arrivee']:
            return {
                'success': False,
                'error': "Impossible d'identifier les gares de départ et/ou d'arrivée",
                'entities': ner_result
            }

        print(ner_result)

        # 3. Rechercher l'itinéraire dans le graphe
        try:
            path = find_path_with_stops(
                self.graph,
                ner_result['depart'],
                ner_result['arrivee'],
                ner_result['etape'] if ner_result['etape'] else None
            )

            if not path:
                return {
                    'success': False,
                    'error': "Aucun itinéraire trouvé",
                    'entities': ner_result
                }

            # 4. Formater la réponse
            return {
                'success': True,
                'path': path,
                'entities': ner_result
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"Erreur lors de la recherche d'itinéraire: {str(e)}",
                'entities': ner_result
            }

def format_duration(minutes):
    """Formate une durée en minutes en format heures/minutes"""
    hours = int(minutes) // 60
    mins = int(minutes) % 60
    if hours > 0:
        return f"{hours}h{mins:02d}"
    return f"{mins}min"

def format_result(result):
    """Formate le résultat pour l'affichage"""
    if not result['success']:
        return f"❌ Erreur : {result['error']}"

    path = result['path']
    entities = result['entities']

    output = []
    output.append(f"✅ Itinéraire trouvé !")
    output.append(f"🚉 De : {entities['depart']}")
    output.append(f"🏁 À : {entities['arrivee']}")

    if entities['etape']:
        output.append(f"🔄 Étapes : {entities['etape']}")

    output.append(f"\n⏱️ Durée totale : {format_duration(path['duree_totale'])}")

    output.append("\n📍 Détails du trajet :")
    for step in path['details']:
        duration = format_duration(step['duree'])
        if step.get('changement'):
            output.append("⚠️  Changement de train")
        output.append(f"{step['type']} {step['de']} → {step['vers']} ({duration})")

    return "\n".join(output)


def main():
    pipeline = Pipeline()
    root = tk.Tk()
    root.title("Interface de traitement audio et texte")

    def on_open_file():
        file_path = filedialog.askopenfilename()
        if file_path:
            pipeline.handle_file(file_path)

    def on_record_toggle():
        pipeline.process_voice_query(record_button)

    def on_submit_text():
        query = text_input.get()

        if query:
            path = pipeline.save_to_file(query)
            pipeline.handle_file(path)


    tk.Button(root, text="Ouvrir un fichier", command=on_open_file).pack(pady=5)
    record_button = tk.Button(root, text="Commencer l'enregistrement", command=on_record_toggle)
    record_button.pack(pady=5)
    text_input = tk.Entry(root)
    text_input.pack(pady=5)
    tk.Button(root, text="Envoyer", command=on_submit_text).pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    main()

from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

class NLPProcessor:
    def __init__(self):
        """Initialise le modèle NLP et le tokenizer"""
        self.model = AutoModelForSequenceClassification.from_pretrained("queenVdu13/NLPF")
        self.tokenizer = AutoTokenizer.from_pretrained("queenVdu13/NLPF")

    def predict_sentence(self, sentence):
        self.model.eval()
        inputs = self.tokenizer(sentence, return_tensors='pt', truncation=True, padding='max_length', max_length=128)
        with torch.no_grad():
            outputs = self.model(**inputs)
            prediction = torch.argmax(outputs.logits, dim=-1).item()
        return prediction           

    def process_query(self, query: str):
        """
        Traite une requête en langage naturel pour déterminer si c'est une requête de trajet valide
        
        Args:
            query (str): La requête en langage naturel (ex: "Je veux aller de Paris à Marseille")
            
        Returns:
            bool: True si la requête est valide, False sinon
        """
        # Utilise la méthode predict_sentence existante
        prediction = self.predict_sentence(query)
        return bool(prediction)

def main():
    # Exemple d'utilisation
    processor = NLPProcessor()
    
    sentences = [
        "Je veux aller à Lyon Part Dieu depuis Montpellier Saint-Roch",
        "Train de Paris Gare de Lyon à Marseille Saint Charles",
        "Emmène moi à Nice en partant de Montpellier",
        "Quel temps fait-il aujourd'hui ?",
        "Je veux aller à Lyon Part Dieu depuis Saint-Gaudens"
    ]
    for sentence in sentences:
        print(sentence, processor.process_query(sentence))
    

if __name__ == "__main__":
    main() 
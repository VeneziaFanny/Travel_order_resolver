from transformers import AutoModelForTokenClassification, AutoTokenizer
import torch

class NERProcessor:
    def __init__(self):
        """Initialise le modèle NER et le tokenizer"""
        self.model = AutoModelForTokenClassification.from_pretrained("PampX/haineux-air")
        self.tokenizer = AutoTokenizer.from_pretrained("PampX/haineux-air")
        self.id2label = self.model.config.id2label

    def process_text(self, content: str):
        """
        Traite un texte pour en extraire les entités nommées
        
        Args:
            content (str): Le texte à analyser (ex: "Je veux aller à Marseille en partant de Paris")
            
        Returns:
            dict: Dictionnaire contenant le départ, l'arrivée et les étapes
        """
        # Tokenisation du texte en mots
        words = content.split()
        inputs = self.tokenizer(words, return_tensors="pt", is_split_into_words=True)
        
        # Prédiction
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Obtenir les logits et les prédictions
        logits = outputs.logits
        predicted_class_indices = torch.argmax(logits, dim=2).squeeze().tolist()
        
        # Convertir les indices en labels
        predicted_labels = [self.id2label[idx] for idx in predicted_class_indices]
        
        # Récupération des tokens
        tokens = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"].squeeze().tolist())
        word_ids = inputs.word_ids()
        
        # Reconstruction des mots et leurs labels
        results = []
        current_word = ""
        current_label = None
        previous_word_id = None
        
        for token, label, word_id in zip(tokens, predicted_labels, word_ids):
            if word_id is None:
                continue
            if word_id != previous_word_id:
                if current_word != "":
                    results.append((current_word, current_label))
                current_word = token.replace("▁", "") if token.startswith("▁") else token
                current_label = label
            else:
                current_word += token.replace("▁", "") if token.startswith("▁") else token
            previous_word_id = word_id
        
        # Ajouter le dernier mot
        if current_word != "":
            results.append((current_word, current_label))
        
        # Organisation des entités
        return self.parse_entities(results)

    def parse_entities(self, results):
        """
        Organise les entités trouvées par type (départ, arrivée, étapes)
        
        Args:
            results: Liste de tuples (mot, label)
            
        Returns:
            dict: Dictionnaire contenant le départ, l'arrivée et les étapes
        """
        depart = []
        etape = []
        arrivee = []
        
        for word, label in results:
            if label in ["LABEL_1", "LABEL_2"]:  # Labels pour Départ
                depart.append(word)
            elif label in ["LABEL_3", "LABEL_4"]:  # Labels pour Arrivée
                arrivee.append(word)
            elif label in ["LABEL_5", "LABEL_6"]:  # Labels pour Etape
                etape.append(word)
        
        return {
            'depart': " ".join(depart) if depart else None,
            'arrivee': " ".join(arrivee) if arrivee else None,
            'etape': " ".join(etape) if etape else None
        }

def main():
    # Exemple d'utilisation
    processor = NERProcessor()
    
    result = processor.process_text("emmène moi à Lyon Part Dieu en passant par Paris Gare de Lyon depuis Montpellier Saint Roch")
    print(result)

if __name__ == "__main__":
    main()
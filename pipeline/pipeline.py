from nlp_processor import NLPProcessor
from ner_processor import NERProcessor
from graph_maker import load_or_create_graph, find_path_with_stops

class Pipeline:
    def __init__(self):
        """Initialise tous les composants du pipeline"""
        print("Initialisation du pipeline...")
        self.nlp = NLPProcessor()
        self.ner = NERProcessor()
        self.graph = load_or_create_graph()
        print("Pipeline initialisé !")

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
    # Exemple d'utilisation
    pipeline = Pipeline()
    
    # Test avec différentes requêtes
    queries = [
        "Je veux aller à Lyon Part Dieu depuis Montpellier Saint-Roch",
        "Train de Paris Gare de Lyon à Marseille Saint Charles",
        "Emmène moi à Nice en partant de Montpellier",
        "Quel temps fait-il aujourd'hui ?",
        "Je veux aller à Lyon Part Dieu depuis Saint-Gaudens"
    ]
    
    for query in queries:
        print("\n" + "="*50)
        print(f"Requête : {query}")
        result = pipeline.process_query(query)
        print("\n" + format_result(result))

if __name__ == "__main__":
    main() 
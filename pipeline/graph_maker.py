import networkx as nx
import pandas as pd
from pathlib import Path
import unicodedata
import os
from tqdm import tqdm

def create_railway_network(data_files):
    """
    Crée un graphe du réseau ferroviaire en combinant les données de tous les types de transport.
    Les trajets sont déjà optimisés pour regrouper les gares proches.
    """
    # Création d'un graphe dirigé pondéré
    G = nx.DiGraph()
    
    # Fonction helper pour traiter chaque dataset
    def add_connections(data, transport_type):
        for _, row in tqdm(data.iterrows(), total=len(data), desc=f"Ajout des connexions {transport_type}"):
            origin = row['station_depart']
            destination = row['station_arrivee']
            duration = row['duree_minutes']
            trip_id = row['trip_id']
            
            # Ajoute l'arête au graphe principal
            if G.has_edge(origin, destination):
                current_duration = G[origin][destination]['weight']
                if duration < current_duration:
                    G[origin][destination].update({
                        'weight': duration,
                        'type': transport_type,
                        'trip_id': trip_id
                    })
            else:
                G.add_edge(origin, destination, 
                          weight=duration,
                          type=transport_type,
                          trip_id=trip_id)
    
    # Ajout des connexions pour chaque type de transport
    for transport_type, file_path in data_files.items():
        print(f"\nTraitement des données {transport_type}...")
        data = pd.read_csv(file_path)
        add_connections(data, transport_type.upper())
    
    print(f"\nGraphe créé avec {G.number_of_nodes()} gares et {G.number_of_edges()} connexions")
    return G

def load_or_create_graph():
    """
    Charge le graphe existant ou en crée un nouveau si nécessaire
    """
    print("Création d'un nouveau graphe...")
    
    # Détection des fichiers CSV optimisés dans les sous-dossiers de gtfs
    gtfs_path = Path('gtfs')
    data_files = {}
    
    for dossier in os.listdir(gtfs_path):
        csv_path = gtfs_path / dossier / f'{dossier}_data_optimized.csv'
        if csv_path.is_file():
            data_files[dossier] = str(csv_path)
    
    if not data_files:
        raise Exception("Aucun fichier CSV de données ferroviaires optimisées trouvé!")
    
    print("\nFichiers de données optimisés détectés:")
    for transport_type, file_path in data_files.items():
        print(f"- {transport_type.upper()}: {file_path}")
    
    G = create_railway_network(data_files)
    
    # Sauvegarde du nouveau graphe avec les attributs correctement typés
    nx.write_gexf(G, 'railway_network_optimized.gexf', version='1.2draft')
    print("Nouveau graphe sauvegardé en railway_network_optimized.gexf")
    return G

def find_direct_connections(G, station):
    """
    Trouve toutes les connexions directes possibles depuis une gare donnée.
    Retourne un dictionnaire {destination: {trip_id, duration, path}}.
    """
    direct_connections = {}
    
    # Récupère tous les successeurs directs de la gare
    for neighbor in G.successors(station):
        edge_data = G[station][neighbor]
        trip_id = edge_data['trip_id']
        
        # Suit le même trip_id aussi loin que possible
        current = neighbor
        path = [station, current]
        duration = edge_data['weight']
        
        while True:
            found_next = False
            for next_station in G.successors(current):
                next_edge = G[current][next_station]
                if next_edge['trip_id'] == trip_id:
                    current = next_station
                    path.append(current)
                    duration += next_edge['weight']
                    found_next = True
                    break
            if not found_next:
                break
        
        # Enregistre toutes les destinations possibles sur ce trajet
        for i in range(1, len(path)):
            dest = path[i]
            if dest not in direct_connections or direct_connections[dest]['duration'] > duration:
                direct_connections[dest] = {
                    'trip_id': trip_id,
                    'duration': duration,
                    'path': path[:i+1]
                }
    
    return direct_connections

def optimize_path_connections(G, path_details):
    """
    Optimise un chemin en essayant de réduire le nombre de correspondances.
    Vérifie si des segments peuvent être remplacés par des trajets directs existants.
    """
    if not path_details:
        return None
        
    # Extrait tous les trip_id uniques du chemin
    trip_ids = set()
    for detail in path_details['details']:
        trip_ids.add(detail['trip_id'])
    
    # Pour chaque trip_id, trouve toutes les connexions directes possibles
    direct_routes = {}
    for trip_id in trip_ids:
        # Trouve toutes les gares de ce trip_id dans le chemin
        stations = []
        for detail in path_details['details']:
            if detail['trip_id'] == trip_id:
                if not stations or stations[-1] != detail['de']:
                    stations.append(detail['de'])
                if detail['vers'] not in stations:
                    stations.append(detail['vers'])
        
        # Pour chaque gare, trouve toutes les connexions directes possibles
        for station in stations:
            for neighbor in G.successors(station):
                edge = G[station][neighbor]
                current_trip = edge['trip_id']
                if current_trip == trip_id:
                    # Suit le même trip_id
                    current = neighbor
                    path = [station, current]
                    duration = edge['weight']
                    
                    while True:
                        found_next = False
                        for next_station in G.successors(current):
                            next_edge = G[current][next_station]
                            if next_edge['trip_id'] == trip_id:
                                current = next_station
                                path.append(current)
                                duration += next_edge['weight']
                                found_next = True
                                break
                        if not found_next:
                            break
                    
                    # Enregistre toutes les connexions directes trouvées
                    for i in range(len(path)):
                        for j in range(i + 1, len(path)):
                            start, end = path[i], path[j]
                            key = (start, end, trip_id)
                            if key not in direct_routes:
                                direct_routes[key] = {
                                    'path': path[i:j+1],
                                    'duration': sum(G[path[k]][path[k+1]]['weight'] for k in range(i, j))
                                }
    
    # Essaie d'optimiser le chemin en remplaçant des segments par des trajets directs
    optimized_details = []
    i = 0
    while i < len(path_details['details']):
        detail = path_details['details'][i]
        best_replacement = None
        best_duration = float('inf')
        
        # Cherche le plus long segment direct possible
        for j in range(i, len(path_details['details'])):
            start = path_details['details'][i]['de']
            end = path_details['details'][j]['vers']
            
            # Vérifie tous les trip_id disponibles
            for trip_id in trip_ids:
                key = (start, end, trip_id)
                if key in direct_routes:
                    duration = direct_routes[key]['duration']
                    if duration < best_duration:
                        best_duration = duration
                        best_replacement = {
                            'start_idx': i,
                            'end_idx': j,
                            'trip_id': trip_id,
                            'path': direct_routes[key]['path'],
                            'duration': duration
                        }
        
        if best_replacement:
            # Crée les détails pour le segment direct
            path = best_replacement['path']
            for k in range(len(path)-1):
                u, v = path[k], path[k+1]
                edge_data = G[u][v]
                optimized_details.append({
                    'de': u,
                    'vers': v,
                    'type': edge_data['type'],
                    'duree': edge_data['weight'],
                    'trip_id': best_replacement['trip_id'],
                    'changement': k == 0 and optimized_details and optimized_details[-1]['trip_id'] != best_replacement['trip_id']
                })
            i = best_replacement['end_idx'] + 1
        else:
            optimized_details.append(detail)
            i += 1
    
    # Calcule les nouvelles statistiques
    total_duration = 0
    nb_changements = 0
    current_trip = None
    
    for detail in optimized_details:
        if current_trip is not None and detail['trip_id'] != current_trip:
            nb_changements += 1
        current_trip = detail['trip_id']
        total_duration += detail['duree']
    
    # Ajoute la pénalité pour les changements
    total_duration += nb_changements * 30
    
    # Regroupe les segments par trip_id
    segments = []
    current_segment = []
    for detail in optimized_details:
        if not current_segment or current_segment[0]['trip_id'] == detail['trip_id']:
            current_segment.append(detail)
        else:
            segments.append(current_segment)
            current_segment = [detail]
    if current_segment:
        segments.append(current_segment)
    
    return {
        'duree_totale': total_duration,
        'nb_changements': nb_changements,
        'details': optimized_details,
        'segments': segments
    }

def find_fastest_path(G, start_station, end_station):
    """
    Trouve le chemin le plus rapide entre deux gares dans le réseau ferroviaire.
    Cherche dans les deux sens (départ->arrivée et arrivée->départ) et prend le meilleur résultat.
    """
    def find_path_in_direction(G, start, end, reverse=False):
        """
        Cherche un chemin dans une direction donnée.
        Si reverse=True, cherche de la fin vers le début.
        """
        # Première étape : chercher un trajet direct
        direct_path = None
        min_duration = float('inf')
        
        # Fonction pour obtenir les voisins selon la direction
        get_neighbors = G.predecessors if reverse else G.successors
        
        # Parcourir tous les voisins de la gare de départ
        for neighbor in get_neighbors(start):
            edge = G[neighbor][start] if reverse else G[start][neighbor]
            current_trip = edge['trip_id']
            
            # Suivre le même trip_id
            current = neighbor
            path = [start, current]
            duration = edge['weight']
            
            while True:
                found_next = False
                for next_station in get_neighbors(current):
                    next_edge = G[next_station][current] if reverse else G[current][next_station]
                    if next_edge['trip_id'] == current_trip:
                        if next_station == end:
                            # Chemin direct trouvé !
                            path.append(next_station)
                            duration += next_edge['weight']
                            if duration < min_duration:
                                min_duration = duration
                                details = []
                                # Inverse le chemin si on cherchait en arrière
                                final_path = list(reversed(path)) if reverse else path
                                for i in range(len(final_path)-1):
                                    u, v = final_path[i], final_path[i+1]
                                    edge_data = G[u][v]
                                    details.append({
                                        'de': u,
                                        'vers': v,
                                        'type': edge_data['type'],
                                        'duree': edge_data['weight'],
                                        'trip_id': edge_data['trip_id'],
                                        'changement': False
                                    })
                                direct_path = {
                                    'duree_totale': duration,
                                    'nb_changements': 0,
                                    'details': details,
                                    'segments': [details]
                                }
                            found_next = True
                            break
                        elif next_station not in path:
                            current = next_station
                            path.append(current)
                            duration += next_edge['weight']
                            found_next = True
                            break
                if not found_next:
                    break
        
        if direct_path:
            return direct_path
        
        # Si aucun trajet direct n'est trouvé, chercher avec des correspondances
        try:
            if reverse:
                # Pour le chemin inverse, on utilise un graphe inversé
                path = nx.shortest_path(G.reverse(), start, end, weight='weight')
                path = list(reversed(path))  # On inverse le chemin trouvé
            else:
                path = nx.shortest_path(G, start, end, weight='weight')
                
            details = []
            total_duration = 0
            current_trip = None
            nb_changements = 0
            
            for i in range(len(path)-1):
                u = path[i]
                v = path[i+1]
                edge_data = G[u][v]
                
                # Détecte un changement de train
                if current_trip is not None and edge_data['trip_id'] != current_trip:
                    nb_changements += 1
                current_trip = edge_data['trip_id']
                
                details.append({
                    'de': u,
                    'vers': v,
                    'type': edge_data['type'],
                    'duree': edge_data['weight'],
                    'trip_id': edge_data['trip_id'],
                    'changement': i > 0 and details[i-1]['trip_id'] != edge_data['trip_id']
                })
                total_duration += edge_data['weight']
            
            # Regroupe les segments par trip_id
            segments = []
            current_segment = []
            for detail in details:
                if not current_segment or current_segment[0]['trip_id'] == detail['trip_id']:
                    current_segment.append(detail)
                else:
                    segments.append(current_segment)
                    current_segment = [detail]
            if current_segment:
                segments.append(current_segment)
            
            # Ajoute une pénalité de 30 minutes par changement
            total_duration += nb_changements * 30
            
            return {
                'duree_totale': total_duration,
                'nb_changements': nb_changements,
                'details': details,
                'segments': segments
            }
            
        except nx.NetworkXNoPath:
            return None
    
    # Cherche dans les deux sens
    forward_path = find_path_in_direction(G, start_station, end_station, reverse=False)
    backward_path = find_path_in_direction(G, end_station, start_station, reverse=True)
    
    # Compare les résultats et retourne le meilleur
    if not forward_path and not backward_path:
        return None
    elif not forward_path:
        return backward_path
    elif not backward_path:
        return forward_path
    else:
        # Retourne le chemin avec le moins de changements, ou le plus rapide en cas d'égalité
        if forward_path['nb_changements'] < backward_path['nb_changements']:
            return forward_path
        elif backward_path['nb_changements'] < forward_path['nb_changements']:
            return backward_path
        else:
            return forward_path if forward_path['duree_totale'] <= backward_path['duree_totale'] else backward_path

def find_stations(G, name):
    """
    Trouve toutes les gares qui contiennent le nom recherché.
    Retourne une liste de noms de gares correspondantes.
    """
    def normalize_string(s):
        # Supprime les accents et met en minuscules
        s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
        # Remplace les caractères spéciaux par des espaces
        s = ''.join(c if c.isalnum() else ' ' for c in s if c.isalnum() or c.isspace())
        # Normalise les espaces et met en minuscules
        return ' '.join(s.lower().split())
    
    # Normalise le terme de recherche
    normalized_name = normalize_string(name)
    # Sépare les mots de recherche
    search_words = normalized_name.split()
    
    matches = []
    for station in G.nodes():
        normalized_station = normalize_string(station)
        # Vérifie si tous les mots de recherche sont présents dans le nom de la gare
        if all(word in normalized_station for word in search_words):
            matches.append(station)
    
    # Trie les résultats par longueur pour avoir les correspondances les plus précises en premier
    return sorted(matches, key=len)

def find_closest_station(G, name):
    """
    Trouve la gare la plus proche du nom donné.
    Retourne le nom exact de la gare ou None si aucune correspondance.
    """
    matches = find_stations(G, name)
    return matches[0] if matches else None

def find_path_with_stops(G, start_station, end_station, stops=None):
    """
    Trouve le chemin le plus rapide entre deux gares en passant par des étapes obligatoires.
    Essaie de minimiser les changements de train.
    Permet l'utilisation de noms approximatifs des gares.
    """
    try:
        # Conversion des noms approximatifs en noms exacts de gares
        real_start = find_closest_station(G, start_station)
        real_end = find_closest_station(G, end_station)
        
        if not real_start or not real_end:
            return None
            
        real_stops = []
        if stops:
            for stop in stops:
                real_stop = find_closest_station(G, stop)
                if not real_stop:
                    return None
                real_stops.append(real_stop)
        
        # Si pas d'étapes, utiliser le chemin direct
        if not real_stops:
            return find_fastest_path(G, real_start, real_end)
        
        # Ajouter le départ et l'arrivée à la liste des étapes
        waypoints = [real_start] + real_stops + [real_end]
        
        # Initialisation des résultats
        total_path = []
        total_duration = 0
        all_details = []
        
        # Calcul du chemin entre chaque paire d'étapes consécutives
        for i in range(len(waypoints)-1):
            current = waypoints[i]
            next_stop = waypoints[i+1]
            
            segment = find_fastest_path(G, current, next_stop)
            if not segment:
                return None  # Si un segment est impossible, le trajet entier est impossible
            
            # Ajouter le chemin (sans dupliquer la gare de connexion)
            if total_path:
                total_path.extend(segment['details'][1:])  # Éviter de dupliquer la gare
            else:
                total_path.extend(segment['details'])
                
            total_duration += segment['duree_totale']
            all_details.extend(segment['details'])
        
        return {
            'chemin': total_path,
            'duree_totale': total_duration,
            'details': all_details
        }
        
    except nx.NetworkXNoPath:
        return None

def format_journey_details(result):
    """
    Formate les détails d'un trajet pour l'affichage.
    Met en évidence les segments utilisant le même train.
    """
    if not result:
        return ["Aucun chemin trouvé"]
    
    formatted_lines = [
        f"Durée totale: {result['duree_totale']:.1f} minutes",
        f"Nombre de changements: {result['nb_changements']}",
        "\nDétail du trajet:"
    ]
    
    # Affichage par segment (même train)
    for segment in result['segments']:
        stations = " → ".join(step['de'] for step in segment)
        stations += f" → {segment[-1]['vers']}"
        
        duree_segment = sum(step['duree'] for step in segment)
        trip_id = segment[0]['trip_id']
        train_type = segment[0]['type']
        
        formatted_lines.append(
            f"🚂 Train {trip_id} ({train_type})"
        )
        formatted_lines.append(
            f"➡️ {stations} ({duree_segment:.1f} min)"
        )
        
        if segment != result['segments'][-1]:
            formatted_lines.append(
                f"🔄 Changement de train"
            )
    
    return formatted_lines

def main():
    # Chargement ou création du graphe
    G = load_or_create_graph()
    
    # Recherche des gares de départ et d'arrivée
    depart = "lunel"
    arrivee = "Lyon part dieu"
    
    stations_depart = find_stations(G, depart)
    stations_arrivee = find_stations(G, arrivee)
    
    if not stations_depart:
        print(f"Aucune gare trouvée pour '{depart}'")
        return
    if not stations_arrivee:
        print(f"Aucune gare trouvée pour '{arrivee}'")
        return
        
    # On prend la première correspondance pour chaque gare
    start = stations_depart[0]
    end = stations_arrivee[0]
    stops = [ ]
    
    print(f"\nGare de départ sélectionnée: {start}")
    print(f"Gare d'arrivée sélectionnée: {end}")
    
    result = find_path_with_stops(G, start, end, stops)
    if result:
        print(f"\nChemin le plus rapide de {start} à {end}:")
        if stops:
            print(f"Passage par les gares suivantes: {', '.join(stops)}")
        for line in format_journey_details(result):
            print(line)
    else:
        print(f"\nAucun chemin trouvé entre {start} et {end}")

if __name__ == "__main__":
    main()

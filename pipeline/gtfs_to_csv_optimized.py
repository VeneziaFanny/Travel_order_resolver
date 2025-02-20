import pandas as pd
from pathlib import Path
from tqdm import tqdm

def time_to_minutes(time_str: str) -> float:
    """Convertit une chaîne de temps HH:MM:SS en minutes."""
    h, m, s = map(int, time_str.split(':'))
    return h * 60 + m + s/60

def process_gtfs_data_optimized(gtfs_folder: str, output_path: Path) -> pd.DataFrame:
    """
    Traite les données GTFS pour extraire les connexions entre gares.
    
    Args:
        gtfs_folder: Chemin vers le dossier contenant les fichiers GTFS
        output_path: Chemin pour le fichier CSV de sortie
    
    Returns:
        DataFrame contenant les connexions optimisées
    """
    print(f"\nTraitement des données {output_path.stem}...")
    
    # Lecture des fichiers GTFS nécessaires
    gtfs_path = Path(gtfs_folder)
    stops = pd.read_csv(gtfs_path / 'stops.txt')
    stop_times = pd.read_csv(gtfs_path / 'stop_times.txt')
    
    # Création du dictionnaire des noms d'arrêts
    stops_dict = stops.set_index('stop_id')['stop_name'].to_dict()
    
    # Conversion des temps en minutes
    stop_times['arrival_minutes'] = stop_times['arrival_time'].apply(time_to_minutes)
    stop_times['departure_minutes'] = stop_times['departure_time'].apply(time_to_minutes)
    
    # Tri des données par trip_id et sequence
    stop_times_sorted = stop_times.sort_values(['trip_id', 'stop_sequence'])
    
    # Liste pour stocker toutes les connexions
    connections = []
    
    print("Analyse des connexions entre gares...")
    
    # Collecter toutes les connexions directes
    for _, group in tqdm(stop_times_sorted.groupby('trip_id')):
        stops_in_trip = list(group['stop_id'])
        times_in_trip = list(group['arrival_minutes'])
        trip_id = group['trip_id'].iloc[0]
        
        for i in range(len(stops_in_trip) - 1):
            start_station = stops_dict[stops_in_trip[i]]
            end_station = stops_dict[stops_in_trip[i + 1]]
            start_time = times_in_trip[i]
            end_time = times_in_trip[i + 1]
            duration = end_time - start_time
            
            if duration <= 0:
                continue
                
            connections.append({
                'station_depart': start_station,
                'station_arrivee': end_station,
                'duree_minutes': duration,
                'trip_id': trip_id
            })
    
    # Création du DataFrame final
    routes_df = pd.DataFrame(connections)
    
    # Tri par durée pour chaque paire de stations
    routes_df = routes_df.sort_values(['station_depart', 'station_arrivee', 'duree_minutes'])
    
    # Sauvegarde
    routes_df.to_csv(output_path, index=False)
    
    print(f"Nombre de connexions trouvées : {len(routes_df)}")
    return routes_df

def main():
    """Fonction principale pour le traitement des dossiers GTFS."""
    gtfs_path = Path('gtfs')
    if not gtfs_path.exists():
        raise FileNotFoundError("Le dossier 'gtfs' n'existe pas.")
    
    # Recherche des sous-dossiers GTFS
    dossiers = [d for d in gtfs_path.iterdir() if d.is_dir()]
    if not dossiers:
        raise FileNotFoundError("Aucun sous-dossier trouvé dans 'gtfs'.")
    
    resultats = {}
    for dossier in dossiers:
        print(f"\nTraitement du dossier {dossier.name}")
        output_path = dossier / f"{dossier.name}_data_optimized.csv"
        
        try:
            data = process_gtfs_data_optimized(dossier, output_path)
            resultats[dossier.name] = len(data)
        except Exception as e:
            print(f"Erreur lors du traitement de {dossier.name}: {str(e)}")
            continue

    # Affichage du résumé
    print("\nRésumé des connexions trouvées:")
    for dossier, nombre in resultats.items():
        print(f"- {dossier.upper()}: {nombre} connexions")

if __name__ == "__main__":
    main() 
import os
import requests
import zipfile
from pathlib import Path

class GTFSDownloader:
    def __init__(self):
        self.base_dir = Path("gtfs")
        self.urls = {
            "tgv": "https://eu.ftp.opendatasoft.com/sncf/plandata/export_gtfs_voyages.zip",
            "ter": "https://eu.ftp.opendatasoft.com/sncf/gtfs/export-ter-gtfs-last.zip",
            "intercites": "https://eu.ftp.opendatasoft.com/sncf/plandata/export-intercites-gtfs-last.zip"
        }
        self._create_directories()

    def _create_directories(self):
        """Crée les dossiers nécessaires s'ils n'existent pas déjà."""
        for dir_name in self.urls.keys():
            dir_path = self.base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

    def download_and_extract(self, service_type):
        """Télécharge et extrait les données GTFS pour un service spécifique."""
        if service_type not in self.urls:
            raise ValueError(f"Type de service invalide: {service_type}")

        url = self.urls[service_type]
        target_dir = self.base_dir / service_type
        zip_path = target_dir / "temp.zip"

        try:
            print(f"Téléchargement des données {service_type}...")
            response = requests.get(url, stream=True)
            response.raise_for_status()

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"Extraction des données {service_type}...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)

            print(f"Nettoyage...")
            zip_path.unlink()  # Supprime le fichier ZIP temporaire
            print(f"Données {service_type} téléchargées et extraites avec succès.")

        except requests.exceptions.RequestException as e:
            print(f"Erreur lors du téléchargement des données {service_type}: {e}")
        except zipfile.BadZipFile:
            print(f"Erreur lors de l'extraction du fichier ZIP {service_type}")
            if zip_path.exists():
                zip_path.unlink()
        except Exception as e:
            print(f"Erreur inattendue pour {service_type}: {e}")

    def download_all(self):
        """Télécharge et extrait les données GTFS pour tous les services."""
        for service_type in self.urls.keys():
            self.download_and_extract(service_type)

if __name__ == "__main__":
    downloader = GTFSDownloader()
    downloader.download_all()

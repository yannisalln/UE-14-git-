import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
import contextily as ctx
import requests
import os

# Configuration pour ignorer les erreurs de géométrie
os.environ["GML_SKIP_CORRUPTED_FEATURES"] = "YES"

class BuildingSelectorNotebook:
    def __init__(self, lat, lon, side_length=100):
        self.center_wgs84 = Point(lon, lat)
        self.side_length = side_length
        self.gdf_buildings = None
        self.selected_building = None
        self.wfs_url = "https://data.geopf.fr/wfs/ows"
        self.layer_name = "BDTOPO_V3:batiment"
        
        # On garde les références pour éviter que le Garbage Collector ne les supprime
        self.fig = None
        self.ax = None
        self.cid = None 

    def fetch_data(self):
        point_df = gpd.GeoDataFrame(geometry=[self.center_wgs84], crs="EPSG:4326")
        point_l93 = point_df.to_crs(epsg=2154)
        center_point = point_l93.geometry[0]
        bbox = center_point.buffer(self.side_length / 2).envelope.bounds
        
        params = {
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
            "TYPENAME": self.layer_name, "SRSNAME": "EPSG:2154",
            "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:2154",
            "OUTPUTFORMAT": "application/json"
        }
        
        try:
            print("⏳ Récupération des données IGN...")
            req = requests.Request('GET', self.wfs_url, params=params)
            self.gdf_buildings = gpd.read_file(req.prepare().url)
            
            if self.gdf_buildings.crs is None:
                self.gdf_buildings.set_crs(epsg=2154, inplace=True)
            
            print(f"✅ {len(self.gdf_buildings)} bâtiments chargés.")
            return True
        except Exception as e:
            print(f"❌ Erreur : {e}")
            return False

    def on_click(self, event):
        if event.inaxes != self.ax: return
        
        click_point = Point(event.xdata, event.ydata)
        distances = self.gdf_buildings.distance(click_point)
        
        if distances.min() < 15:
            nearest_idx = distances.idxmin()
            self.selected_building = self.gdf_buildings.loc[[nearest_idx]]
            target = self.gdf_buildings.loc[nearest_idx]
            
            # Update graphique
            self.ax.clear()
            self._plot_base()
            self.selected_building.plot(ax=self.ax, color='red', edgecolor='yellow', linewidth=2, zorder=10)
            
            self.ax.set_title(f"Sélection : {target.get('usage1', 'Inconnu')} (ID: {target.get('cleabs')})")
            
            # IMPORTANT : draw_idle est plus léger et stable que draw()
            self.fig.canvas.draw_idle()
            print(f"📍 Bâtiment sélectionné : {target.get('cleabs')}")

    def _plot_base(self):
        self.gdf_buildings.plot(ax=self.ax, color='lightgray', edgecolor='#444', alpha=0.8)
        try:
            ctx.add_basemap(self.ax, crs=self.gdf_buildings.crs.to_string(), source=ctx.providers.OpenStreetMap.Mapnik)
        except: pass
        self.ax.set_axis_off()

    def create_map(self):
        """
        Crée la figure et la retourne, mais NE L'AFFICHE PAS.
        C'est le notebook qui s'occupera de l'afficher.
        """
        if self.gdf_buildings is None: return None
        
        # Si une figure existe déjà pour cet objet, on la ferme proprement
        if self.fig is not None:
            plt.close(self.fig)
            
        # Création de la figure
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        self._plot_base()
        self.ax.set_title("Cliquez sur un bâtiment")
        
        # On stocke l'ID de connexion (cid) dans l'objet pour qu'il survive
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        
        # ON RETOURNE la figure, on ne fait pas de display() ni de show() ici
        return self.fig

    def get_selection(self):
        return self.selected_building
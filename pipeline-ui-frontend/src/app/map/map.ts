import { Component, AfterViewInit, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../api';
import { Deck } from '@deck.gl/core';
import { GeoJsonLayer, BitmapLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="map-container">
      <div class="ui-panel">
        <h2>Demo</h2>
        <p>MongoDB Job ID:</p>
        <input #jobInput type="text" placeholder="Paste Job ID here..." />
        <button (click)="loadDigitalTwin(jobInput.value)">Render 3D Map</button>
        <div class="status-box">{{ statusMessage }}</div>
      </div>

      <canvas #deckCanvas id="deck-canvas"></canvas>
    </div>
  `,
  styles: [`
    .map-container { position: relative; width: 100vw; height: 100vh; background-color: #121212; overflow: hidden; }
    #deck-canvas { width: 100%; height: 100%; position: absolute; top: 0; left: 0; z-index: 1; }
    .ui-panel { position: absolute; top: 20px; left: 20px; z-index: 10; background: rgba(20,20,20,0.95); color: #fff; padding: 25px; border-radius: 12px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; box-shadow: 0 4px 20px rgba(0,0,0,0.5); border: 1px solid #333; width: 300px; }
    h2 { margin-top: 0; font-size: 1.4rem; color: #00ffcc; border-bottom: 1px solid #333; padding-bottom: 10px; }
    input { width: 100%; padding: 12px; margin: 10px 0; box-sizing: border-box; background: #222; border: 1px solid #444; color: #fff; border-radius: 6px; }
    button { width: 100%; padding: 12px; background: #00ffcc; color: #000; border: none; font-weight: bold; font-size: 1rem; cursor: pointer; border-radius: 6px; transition: 0.2s; }
    button:hover { background: #00cca3; }
    .status-box { margin-top: 15px; font-size: 0.9rem; color: #aaa; font-style: italic; }
  `]
})
export class MapComponent implements AfterViewInit {
  @ViewChild('deckCanvas') deckCanvas!: ElementRef<HTMLCanvasElement>;
  
  private deckInstance: any;
  statusMessage = 'Awaiting Job ID...';

  constructor(private apiService: ApiService) {}


  ngAfterViewInit() {
    this.deckInstance = new Deck({
      canvas: this.deckCanvas.nativeElement,
      initialViewState: {
        longitude: 5.714,
        latitude: 7.613,
        zoom: 17,
        pitch: 60,
        bearing: 30
      },
      controller: true,
      layers: []
    });
  }

  loadDigitalTwin(jobId: string) {
      if (!jobId) {
        this.statusMessage = 'Please enter a valid Job ID.';
        return;
      }

      this.statusMessage = 'Fetching Digital Twin from MongoDB...';
      
      this.apiService.getJobResult(jobId).subscribe({
        next: (response) => {
          if (response.status === 'completed') {
            this.statusMessage = `Success! Rendering 3D Trees...`;

            let mapData = response.result;
          
            if (typeof mapData === 'string') {
              mapData = JSON.parse(mapData);
            }
            
            if (typeof mapData === 'string') {
              mapData = JSON.parse(mapData);
            }

            if (mapData && mapData.data && mapData.data.type === 'FeatureCollection') {
              mapData = mapData.data;
            } else if (mapData && mapData.features && !mapData.type) {
              mapData = { type: 'FeatureCollection', features: mapData.features };
            }

            console.log("FINAL GEOJSON PAYLOAD:", mapData);

            this.render3DLayers(mapData);
          } else {
            this.statusMessage = `Job is currently: ${response.status}`;
          }
        },
        error: (err) => {
          this.statusMessage = 'Error connecting to API.';
          console.error(err);
        }
      });
  }

  render3DLayers(payload: any) {
      const treesGeoJson = payload.trees;
      const powerlineGeoJson = payload.powerline;

      const baseMapLayer = new TileLayer({
        // // Streams a dark-mode real-world map underneath everything
        // id: 'carto-dark-basemap',
        // data: 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        // satellite basemap (Esri's World Imagery tiles)
        id: 'esri-satellite-basemap',
        data: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        minZoom: 0,
        maxZoom: 19,
        tileSize: 256,
        renderSubLayers: (props) => {
          const bbox = props.tile.bbox as { west: number; south: number; east: number; north: number };
          const { west, south, east, north } = bbox;

          return new BitmapLayer(props, {
            data: undefined,
            image: props.data,
            bounds: [west, south, east, north]
          });
        }
      });

      // The 3D Trees Layer
      const treeLayer = new GeoJsonLayer({
        id: '3d-tree-layer',
        data: treesGeoJson,
        pickable: true,
        extruded: true, 
        wireframe: true,
        getElevation: (feature: any) => feature.properties.Max_Height_m || 10,
        getFillColor: (feature: any) => {
          const height = feature.properties.Max_Height_m || 0;
          return height > 25 ? [255, 60, 60, 200] : [0, 200, 100, 200];
        },
        getLineColor: [255, 255, 255, 50],
      });

      // The Powerline Layer
      const powerlineLayer = new GeoJsonLayer({
        id: 'powerline-layer',
        data: powerlineGeoJson,
        pickable: true,
        stroked: true,
        getLineColor: [255, 204, 0, 255], 
        getLineWidth: 5,
        lineWidthMinPixels: 4,
      });

      // Push ALL layers onto our map (Basemap MUST be first so it sits on the bottom)
      this.deckInstance.setProps({
        layers: [baseMapLayer, powerlineLayer, treeLayer]
      });
  }
}
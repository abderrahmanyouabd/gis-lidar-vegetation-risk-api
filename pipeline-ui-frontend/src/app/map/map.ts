import { Component, AfterViewInit, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../api';
import { Deck, AmbientLight, DirectionalLight, LightingEffect } from '@deck.gl/core';
import { GeoJsonLayer} from '@deck.gl/layers';
import { TerrainLayer } from '@deck.gl/geo-layers';
import { _TerrainExtension } from '@deck.gl/extensions';

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
    .map-container { position: relative; width: 100vw; height: 100vh; background-color: #000; overflow: hidden; }
    #deck-canvas { width: 100%; height: 100%; position: absolute; top: 0; left: 0; z-index: 1; }
    .ui-panel { position: absolute; top: 20px; left: 20px; z-index: 10; background: rgba(10,10,10,0.8); backdrop-filter: blur(10px); color: #fff; padding: 25px; border-radius: 12px; font-family: 'Segoe UI', sans-serif; box-shadow: 0 10px 30px rgba(0,0,0,0.8); border: 1px solid #333; width: 300px; }
    h2 { margin-top: 0; font-size: 1.4rem; color: #fff; border-bottom: 1px solid #333; padding-bottom: 10px; text-transform: uppercase; letter-spacing: 1px;}
    input { width: 100%; padding: 12px; margin: 10px 0; box-sizing: border-box; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 6px; }
    button { width: 100%; padding: 12px; background: #fff; color: #000; border: none; font-weight: bold; font-size: 1rem; cursor: pointer; border-radius: 6px; transition: 0.3s; text-transform: uppercase; }
    button:hover { background: #ccc; }
    .status-box { margin-top: 15px; font-size: 0.9rem; color: #aaa; font-style: italic; }
  `]
})
export class MapComponent implements AfterViewInit {
  @ViewChild('deckCanvas') deckCanvas!: ElementRef<HTMLCanvasElement>;
  
  private deckInstance: any;
  statusMessage = 'Awaiting Job ID...';

  constructor(private apiService: ApiService) {}

  ngAfterViewInit() {
    const ambientLight = new AmbientLight({ color: [255, 255, 255], intensity: 0.4 });
    const directionalLight = new DirectionalLight({
      color: [255, 255, 255],
      intensity: 1.5,
      direction: [-1, -2, -3]
    });
    const lightingEffect = new LightingEffect({ ambientLight, directionalLight });

    this.deckInstance = new Deck({
      canvas: this.deckCanvas.nativeElement,
      initialViewState: {
        longitude: 5.714,
        latitude: 7.613,
        zoom: 16.5,
        pitch: 65,
        bearing: 120
      },
      controller: true,
      effects: [lightingEffect],
      layers: []
    });
  }

  loadDigitalTwin(jobId: string) {
    if (!jobId) return;
    this.statusMessage = 'Fetching Digital Twin from MongoDB...';
    
    this.apiService.getJobResult(jobId).subscribe({
      next: (response) => {
        if (response.status === 'completed') {
          this.statusMessage = 'Success! Rendering Photorealistic 3D...';
          
          let mapData = response.result;
          if (typeof mapData === 'string') mapData = JSON.parse(mapData);
          if (typeof mapData === 'string') mapData = JSON.parse(mapData);
          if (mapData && mapData.data && mapData.data.type === 'FeatureCollection') {
            mapData = mapData.data;
          } else if (mapData && mapData.features && !mapData.type) {
            mapData = { type: 'FeatureCollection', features: mapData.features };
          }
          this.render3DLayers(mapData);
        }
      }
    });
  }

  render3DLayers(payload: any) {
    const treesGeoJson = payload.trees;
    const powerlineGeoJson = payload.powerline;

    // THE 3D EARTH: Amazon AWS Elevation Data + Esri Satellite Dirt
    const terrainLayer = new TerrainLayer({
      id: '3d-terrain',
      minZoom: 0,
      maxZoom: 23,
      elevationDecoder: {
        rScaler: 256,
        gScaler: 1,
        bScaler: 1 / 256,
        offset: -32768
      },
      elevationData: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
      texture: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    });

    // THE TREES
    const treeLayer = new GeoJsonLayer({
      id: '3d-tree-layer',
      data: treesGeoJson,
      pickable: true,
      extruded: true, 
      wireframe: false,
      extensions: [new _TerrainExtension()],
      getElevation: (feature: any) => feature.properties.Max_Height_m || 10,
      getFillColor: (feature: any) => {
        const height = feature.properties.Max_Height_m || 0;
        return height > 25 ? [200, 40, 40, 255] : [30, 150, 60, 255];
      },
      material: {
        ambient: 0.3,
        diffuse: 0.8,
        shininess: 32.0,
        specularColor: [60, 60, 60]
      }
    });

    // THE POWERLINE
    const powerlineLayer = new GeoJsonLayer({
      id: 'powerline-layer',
      data: powerlineGeoJson,
      stroked: true,
      extensions: [new _TerrainExtension()],
      getLineColor: [255, 204, 0, 255], 
      getLineWidth: 6,
      lineWidthMinPixels: 4,
    });

    this.deckInstance.setProps({
      layers: [terrainLayer, powerlineLayer, treeLayer]
    });
  }
}
import { Component, AfterViewInit, ElementRef, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../api';
import { Deck, AmbientLight, DirectionalLight, LightingEffect } from '@deck.gl/core';
import { GeoJsonLayer} from '@deck.gl/layers';
import { _TerrainExtension } from '@deck.gl/extensions';
import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';

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
        <button (click)="loadData(jobInput.value)">Render 3D Map</button>
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

  loadData(jobId: string) {
    if (!jobId) return;
    this.statusMessage = 'Fetching data from MongoDB...';
    
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

    // THE BASEMAP
    const baseMapLayer = new TileLayer({
      id: 'esri-satellite-basemap',
      data: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      minZoom: 0,
      maxZoom: 19,
      tileSize: 256,
      renderSubLayers: (props) => {
        const bbox = props.tile.bbox as any;
        const { west, south, east, north } = bbox;
        return new BitmapLayer(props, {
          data: undefined,
          image: props.data,
          bounds: [west, south, east, north]
        });
      }
    });

    // THE TREES
    const treeLayer = new GeoJsonLayer({
      id: '3d-tree-layer',
      data: treesGeoJson,
      pickable: true,
      extruded: true, 
      wireframe: false,    
      getElevation: (feature: any) => feature.properties.Max_Height_m || 10,
      getFillColor: (feature: any) => {
      const risk = feature.properties.Risk_Level;
      return risk === 'CRITICAL' ? [255, 40, 40, 255] : [30, 150, 60, 255]; 
      },
      material: {
        ambient: 0.3,
        diffuse: 0.9,
        shininess: 32.0,
        specularColor: [80, 80, 80]
      }
    });

    // THE POWERLINE
    const powerlineLayer = new GeoJsonLayer({
      id: 'powerline-layer',
      data: powerlineGeoJson,
      stroked: true,
      getLineColor: [255, 204, 0, 255], 
      getLineWidth: 6,
      lineWidthMinPixels: 4,
      getPolygonOffset: ({layerIndex}) => [0, -layerIndex * 100], 
    });

    this.deckInstance.setProps({
      layers: [baseMapLayer, powerlineLayer, treeLayer]
    });
  }
}
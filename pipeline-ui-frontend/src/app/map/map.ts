import { Component, AfterViewInit, ElementRef, ViewChild, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../api';
import { Deck, AmbientLight, DirectionalLight, LightingEffect, FlyToInterpolator } from '@deck.gl/core';
import { GeoJsonLayer} from '@deck.gl/layers';
import { _TerrainExtension } from '@deck.gl/extensions';
import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';

interface JobStatus {
  job_id: string;
  status: string;
  message?: string;
}

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
        <div class="status-box">
          <span *ngIf="isLoading" class="loader"></span>
          {{ statusMessage }}
        </div>
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
    .status-box { margin-top: 15px; font-size: 0.95rem; color: #00ffaa; font-family: 'Courier New', monospace; display: flex; align-items: center; gap: 10px; min-height: 24px; }
    .loader {
      width: 16px;
      height: 16px;
      border: 3px solid #00ffaa;
      border-bottom-color: transparent;
      border-radius: 50%;
      display: inline-block;
      animation: rotation 0.8s linear infinite;
    }
    @keyframes rotation {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    .dots { color: #00ffaa; }
  `]
})
export class MapComponent implements AfterViewInit, OnDestroy {
  @ViewChild('deckCanvas') deckCanvas!: ElementRef<HTMLCanvasElement>;
  
  private deckInstance: any;
  private websocket: WebSocket | null = null;
  private currentJobId: string = '';
  private reconnectInterval: any = null;
  private isConnected: boolean = false;
  isLoading: boolean = false;
  statusMessage = 'Awaiting Job ID...';

  constructor(
    private apiService: ApiService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnDestroy() {
    this.disconnectWebSocket();
    if (this.reconnectInterval) {
      clearInterval(this.reconnectInterval);
    }
  }

  private connectWebSocket(jobId: string) {
    this.disconnectWebSocket();
    this.currentJobId = jobId;
    this.isLoading = true;
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//localhost:8000/ws/${jobId}`;
    
    this.websocket = new WebSocket(wsUrl);
    
    this.websocket.onopen = () => {
      this.isConnected = true;
      this.statusMessage = `Connected - waiting for updates...`;
      this.cdr.detectChanges();
    };
    
    this.websocket.onmessage = (event) => {
      try {
        const status: JobStatus = JSON.parse(event.data);
        this.handleStatusUpdate(status);
        this.cdr.detectChanges();
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
    
    this.websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.isLoading = false;
      this.statusMessage = 'Connection error - trying to reconnect...';
      this.cdr.detectChanges();
    };
    
    this.websocket.onclose = () => {
      this.isConnected = false;
      this.isLoading = false;
      console.log('WebSocket disconnected');
      
      if (this.currentJobId && this.statusMessage.indexOf('complete') === -1 && this.statusMessage.indexOf('error') === -1) {
        this.statusMessage = 'Connection lost - attempting to reconnect...';
        this.cdr.detectChanges();
        this.startReconnect();
      }
    };
  }

  private startReconnect() {
    if (this.reconnectInterval) return;
    
    this.reconnectInterval = setInterval(() => {
      if (this.currentJobId && !this.isConnected) {
        console.log('Attempting to reconnect WebSocket...');
        this.connectWebSocket(this.currentJobId);
      }
    }, 3000);
  }

  private disconnectWebSocket() {
    if (this.reconnectInterval) {
      clearInterval(this.reconnectInterval);
      this.reconnectInterval = null;
    }
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
    this.isConnected = false;
  }

  private dotAnimationInterval: any = null;
  private dotCount: number = 0;
  private currentBaseMessage: string = '';

  private startDotAnimation() {
    this.stopDotAnimation();
    this.dotCount = 0;
    
    this.dotAnimationInterval = setInterval(() => {
      this.dotCount = (this.dotCount + 1) % 4;
      const dots = '.'.repeat(this.dotCount);
      this.statusMessage = `${this.currentBaseMessage}${dots}`;
      this.cdr.detectChanges();
    }, 400);
  }

  private stopDotAnimation() {
    if (this.dotAnimationInterval) {
      clearInterval(this.dotAnimationInterval);
      this.dotAnimationInterval = null;
    }
  }

  private handleStatusUpdate(status: JobStatus) {
    console.log('WebSocket received:', status);
    
    this.stopDotAnimation();
    
    switch (status.status) {
      case 'queued':
        this.statusMessage = `Queued - ${status.message || 'waiting for worker'}`;
        this.isLoading = true;
        break;
      case 'processing':
        this.isLoading = true;
        // Show the stage message immediately with animated dots
        this.currentBaseMessage = status.message || 'Processing';
        this.statusMessage = this.currentBaseMessage;
        this.startDotAnimation();
        break;
      case 'completed':
        this.isLoading = false;
        this.statusMessage = 'Complete! Loading 3D map...';
        this.stopDotAnimation();
        this.disconnectWebSocket();
        this.fetchJobResult(status.job_id);
        break;
      case 'failed':
        this.isLoading = false;
        this.statusMessage = `Error: ${status.message || 'Job failed'}`;
        this.stopDotAnimation();
        this.disconnectWebSocket();
        break;
    }
    this.cdr.detectChanges();
  }

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
        zoom: 4,
        pitch: 0,
        bearing: 0
      },
      controller: true,
      effects: [lightingEffect],
      layers: [],
      getTooltip: ({object}) => {
        if (!object) return null;
        
        // If they hover over a tree
        if (object.properties && object.properties.Max_Height_m) {
          return {
            html: `
              <div style="font-family: 'Segoe UI', sans-serif; padding: 5px;">
                <strong style="color: #00ffcc; font-size: 1.1em;">TREE ID: ${object.properties.Tree_ID}</strong><br/>
                <hr style="border: 0.5px solid #333; margin: 5px 0;" />
                <b>Height:</b> ${object.properties.Max_Height_m.toFixed(2)} m<br/>
                <b>Clearance:</b> ${object.properties.Distance_to_Line_m.toFixed(2)} m<br/>
                <b style="color: ${object.properties.Risk_Level === 'CRITICAL' ? '#ff3333' : '#33cc33'};">
                  STATUS: ${object.properties.Risk_Level}
                </b>
              </div>
            `,
            style: {
              backgroundColor: 'rgba(20, 20, 20, 0.95)',
              color: '#fff',
              border: '1px solid #444',
              borderRadius: '6px',
              boxShadow: '0 4px 15px rgba(0,0,0,0.5)'
            }
          };
        }
        return null;
      }
    });
  }

  loadData(jobId: string) {
    if (!jobId) return;
    
    this.connectWebSocket(jobId);
    this.statusMessage = 'Connecting to real-time status...';
    this.isLoading = true;
    this.cdr.detectChanges();
  }

  private fetchJobResult(jobId: string) {
    this.statusMessage = 'Complete! Loading 3D map...';
    this.cdr.detectChanges();
    
    this.apiService.getJobResult(jobId).subscribe({
      next: (response) => {
        this.statusMessage = 'Job complete! Rendering 3D map...';
        this.isLoading = false;
        this.cdr.detectChanges();
        
        let mapData = response.result;
        if (typeof mapData === 'string') mapData = JSON.parse(mapData);
        if (typeof mapData === 'string') mapData = JSON.parse(mapData);
        if (mapData && mapData.data && mapData.data.type === 'FeatureCollection') {
          mapData = mapData.data;
        } else if (mapData && mapData.features && !mapData.type) {
          mapData = { type: 'FeatureCollection', features: mapData.features };
        }
        this.render3DLayers(mapData);
      },
      error: (err) => {
        this.statusMessage = `Error loading result: ${err.message || 'Unknown error'}`;
        this.isLoading = false;
        this.cdr.detectChanges();
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

    // The Transparent Clearance Zone
    const clearanceZoneLayer = new GeoJsonLayer({
      id: 'clearance-zone-layer',
      data: powerlineGeoJson,
      stroked: true,
      getLineColor: [255, 60, 60, 60],
      // We physically draw the safety radius (example: 25 meters wide)
      getLineWidth: 25,
      lineWidthUnits: 'meters',
      
      getPolygonOffset: ({layerIndex}) => [0, -layerIndex * 100],
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
      layers: [baseMapLayer, clearanceZoneLayer, powerlineLayer, treeLayer],
      initialViewState: {
        longitude: 5.714,
        latitude: 7.613,
        zoom: 16.5,
        pitch: 65,
        bearing: 120,
        transitionDuration: 4000,
        transitionInterpolator: new FlyToInterpolator()
      }
    });
  }
}
import { Component, AfterViewInit, ElementRef, ViewChild, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../api';
import { Deck, AmbientLight, DirectionalLight, LightingEffect, FlyToInterpolator } from '@deck.gl/core';
import { GeoJsonLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';

interface JobStatus {
  job_id: string;
  status: string;
  message?: string;
}

interface TreeFeature {
  tree_id: string;
  height: number;
  distance: number;
  risk: string;
}

interface RiskStats {
  score: number;
  label: string;
  total: number;
  critical: number;
  high: number;
  moderate: number;
  low: number;
  safe: number;
  trees: TreeFeature[];
  totalPoints: number;
  totalAreaHa: number;
}

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="map-container">

      <!-- CONTROL PANEL -->
      <div class="ui-panel">
        <h2>LiDAR Risk Engine</h2>
        <p class="label">Job ID</p>
        <input #jobInput type="text" placeholder="Paste job ID..." />
        <button (click)="loadData(jobInput.value)">Analyze</button>
        <div class="status-box">
          <span *ngIf="isLoading" class="loader"></span>
          {{ statusMessage }}
        </div>
      </div>

      <!-- PULL TAB — visible only when panel is hidden -->
      <div class="risk-tab" *ngIf="riskStats && !panelOpen" (click)="panelOpen = true">
        <span>RISK ASSESSMENT</span>
      </div>

      <!-- RISK PANEL -->
      <div class="risk-panel" *ngIf="riskStats" [class.open]="panelOpen">

        <div class="rp-header">
          <span class="rp-title">RISK ASSESSMENT</span>
          <button class="rp-close" (click)="panelOpen = false">✕</button>
        </div>

        <!-- Score -->
        <div class="rp-score-row">
          <span class="rp-score-num">{{ riskStats.score }}</span>
          <span class="rp-score-denom">/ 100</span>
          <div class="rp-score-right">
            <div class="rp-score-label" [ngClass]="getRiskClass(riskStats.label)">{{ riskStats.label }}</div>
            <div class="rp-score-bar-track">
              <div class="rp-score-bar-fill" [style.width.%]="riskStats.score" [ngClass]="getRiskClass(riskStats.label)"></div>
            </div>
          </div>
        </div>

        <!-- Classification -->
        <div class="rp-section-label">CLASSIFICATION</div>
        <div class="rp-classification">
          <div class="rp-class-item crit">
            <span class="rp-class-count">{{ riskStats.critical }}</span>
            <span class="rp-class-name">CRIT</span>
            <span class="rp-class-pct">{{ pct(riskStats.critical, riskStats.total) }}%</span>
          </div>
          <div class="rp-class-item high">
            <span class="rp-class-count">{{ riskStats.high }}</span>
            <span class="rp-class-name">HIGH</span>
            <span class="rp-class-pct">{{ pct(riskStats.high, riskStats.total) }}%</span>
          </div>
          <div class="rp-class-item mod">
            <span class="rp-class-count">{{ riskStats.moderate }}</span>
            <span class="rp-class-name">MOD</span>
            <span class="rp-class-pct">{{ pct(riskStats.moderate, riskStats.total) }}%</span>
          </div>
          <div class="rp-class-item low">
            <span class="rp-class-count">{{ riskStats.low }}</span>
            <span class="rp-class-name">LOW</span>
            <span class="rp-class-pct">{{ pct(riskStats.low, riskStats.total) }}%</span>
          </div>
          <div class="rp-class-item safe">
            <span class="rp-class-count">{{ riskStats.safe }}</span>
            <span class="rp-class-name">SAFE</span>
            <span class="rp-class-pct">{{ pct(riskStats.safe, riskStats.total) }}%</span>
          </div>
        </div>

        <!-- Proximity Readout -->
        <div class="rp-section-label">
          PROXIMITY READOUT
          <span class="rp-object-count">{{ riskStats.total }} objects</span>
        </div>
        <div class="rp-table-header">
          <span class="col-id">ID</span>
          <span class="col-ht">HT</span>
          <span class="col-dist">DIST</span>
        </div>
        <div class="rp-table-body">
          <div
            class="rp-row"
            *ngFor="let t of riskStats.trees"
            [ngClass]="getRowClass(t.risk)"
            (click)="flyToTree(t)"
          >
            <span class="col-id">{{ t.tree_id }}</span>
            <span class="col-ht">{{ t.height | number:'1.0-0' }}m</span>
            <span class="col-dist" [ngClass]="getDistClass(t.distance)">{{ t.distance | number:'1.1-1' }}m</span>
          </div>
        </div>

        <!-- Export -->
        <button class="rp-export" (click)="exportGeoJson()">
          ↓ &nbsp; EXPORT GEOJSON
        </button>

        <!-- Footer -->
        <div class="rp-footer">
          <span>⬡ {{ riskStats.total }} trees</span>
          <span>◈ {{ (riskStats.totalPoints / 1000000) | number:'1.1-1' }}M pts</span>
          <span>▣ {{ riskStats.totalAreaHa | number:'1.1-1' }} ha</span>
        </div>
      </div>

      <canvas #deckCanvas id="deck-canvas"></canvas>
    </div>
  `,
  styles: [`
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&family=DM+Serif+Display&display=swap');

    :host {
      --bg:          #0e0c0a;
      --bg-panel:    #121009;
      --border:      #252018;
      --border-soft: #1a1810;

      --ink:         #e2d6be;
      --ink-mid:     #9a8c74;
      --ink-dim:     #fff;
      --ink-faint:   orange;

      --accent:      #c07a32;

      --crit:        #c44236;
      --high:        #c07a32;
      --mod:         #a49228;
      --low:         #688e44;
      --safe:        #3a785a;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    .map-container {
      position: relative; width: 100vw; height: 100vh;
      background: var(--bg); overflow: hidden;
      font-family: 'IBM Plex Mono', monospace;
    }

    #deck-canvas {
      width: 100%; height: 100%;
      position: absolute; top: 0; left: 0; z-index: 1;
    }

    /* ── CONTROL PANEL ─────────────────────── */
    .ui-panel {
      position: absolute; top: 24px; left: 24px; z-index: 10;
      background: var(--bg-panel);
      color: var(--ink);
      padding: 20px;
      border-radius: 2px;
      border: 1px solid var(--border);
      border-top: 2px solid var(--accent);
      width: 268px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.65);
    }

    .ui-panel h2 {
      font-size: 0.65rem; font-weight: 500;
      color: var(--accent);
      letter-spacing: 3px; text-transform: uppercase;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px; margin-bottom: 14px;
    }

    .label {
      font-size: 0.58rem; color: var(--ink-dim);
      letter-spacing: 2px; text-transform: uppercase; margin-bottom: 6px;
    }

    input {
      width: 100%; padding: 9px 11px;
      background: #0a0806;
      border: 1px solid var(--border);
      color: var(--ink);
      border-radius: 2px;
      font-family: 'IBM Plex Mono', monospace; font-size: 0.73rem;
      margin-bottom: 9px; outline: none;
      transition: border-color 0.15s;
    }
    input:focus { border-color: var(--accent); }
    input::placeholder { color: var(--ink-faint); }

    button {
      width: 100%; padding: 9px;
      background: var(--accent); color: #0a0806;
      border: none;
      font-family: 'IBM Plex Mono', monospace;
      font-weight: 500; font-size: 0.7rem;
      cursor: pointer; border-radius: 2px;
      letter-spacing: 2px; text-transform: uppercase;
      transition: opacity 0.15s;
    }
    button:hover { opacity: 0.82; }

    .status-box {
      margin-top: 13px; font-size: 0.68rem;
      color: var(--ink-mid);
      display: flex; align-items: center; gap: 8px;
      min-height: 18px; line-height: 1.5;
    }

    .loader {
      flex-shrink: 0; width: 10px; height: 10px;
      border: 1.5px solid var(--accent);
      border-bottom-color: transparent;
      border-radius: 50%;
      animation: spin 0.9s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ── PULL TAB ──────────────────────────── */
    .risk-tab {
      position: absolute; right: 0; top: 50%;
      transform: translateY(-50%);
      z-index: 10;
      background: var(--bg-panel);
      border: 1px solid var(--border);
      border-right: none;
      border-top: 2px solid var(--accent);
      border-radius: 2px 0 0 2px;
      padding: 16px 9px;
      cursor: pointer;
      transition: background 0.15s;
      box-shadow: -4px 0 20px rgba(0,0,0,0.5);
    }
    .risk-tab:hover { background: #1a1610; }
    .risk-tab span {
      writing-mode: vertical-rl;
      text-orientation: mixed;
      transform: rotate(180deg);
      font-size: 0.56rem; letter-spacing: 3px;
      color: var(--accent); text-transform: uppercase;
      user-select: none; display: block;
    }

    /* ── RISK PANEL ────────────────────────── */
    .risk-panel {
      position: absolute; top: 0; right: 0;
      width: 308px; height: 100%;
      background: var(--bg-panel);
      border-left: 1px solid var(--border);
      z-index: 10;
      display: flex; flex-direction: column;
      transform: translateX(100%);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: -6px 0 32px rgba(0,0,0,0.55);
    }
    .risk-panel.open { transform: translateX(0); }

    .rp-header {
      display: flex; align-items: center;
      justify-content: space-between;
      padding: 13px 18px;
      border-bottom: 1px solid var(--border-soft);
      flex-shrink: 0;
    }
    .rp-title {
      font-size: 0.58rem; letter-spacing: 3px;
      color: var(--accent); text-transform: uppercase;
    }
    .rp-close {
      width: auto; padding: 3px 8px;
      background: transparent; color: var(--ink-dim);
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.62rem; letter-spacing: 0;
      border: 1px solid var(--border);
      border-radius: 2px; cursor: pointer;
      transition: color 0.15s, border-color 0.15s;
    }
    .rp-close:hover { color: var(--ink); border-color: var(--ink-dim); background: transparent; }

    /* Score */
    .rp-score-row {
      display: flex; align-items: center; gap: 10px;
      padding: 16px 18px 10px; flex-shrink: 0;
    }
    .rp-score-num {
      font-family: 'DM Serif Display', serif;
      font-size: 4rem; line-height: 1;
      color: var(--ink); letter-spacing: -2px;
    }
    .rp-score-denom {
      font-size: 0.68rem; color: var(--ink-dim); margin-top: 20px;
    }
    .rp-score-right {
      flex: 1; display: flex; flex-direction: column;
      gap: 7px; margin-top: 18px;
    }
    .rp-score-label {
      font-size: 0.7rem; font-weight: 500;
      letter-spacing: 3px; text-transform: uppercase;
    }
    .rp-score-bar-track {
      height: 2px; background: var(--border);
      border-radius: 1px; overflow: hidden;
    }
    .rp-score-bar-fill {
      height: 100%;
      transition: width 1.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* Risk colour tokens */
    .risk-critical, .risk-high, .risk-elevated,
    .risk-moderate, .risk-low, .risk-safe { font-weight: 500; }
    .risk-critical { color: var(--crit); }
    .risk-high,
    .risk-elevated  { color: var(--high); }
    .risk-moderate  { color: var(--mod);  }
    .risk-low       { color: var(--low);  }
    .risk-safe      { color: var(--safe); }

    .rp-score-bar-fill.risk-critical { background: var(--crit); }
    .rp-score-bar-fill.risk-high,
    .rp-score-bar-fill.risk-elevated { background: var(--high); }
    .rp-score-bar-fill.risk-moderate { background: var(--mod);  }
    .rp-score-bar-fill.risk-low      { background: var(--low);  }
    .rp-score-bar-fill.risk-safe     { background: var(--safe); }

    /* Section label */
    .rp-section-label {
      font-size: 0.56rem; letter-spacing: 2px;
      color: var(--ink-dim); text-transform: uppercase;
      padding: 10px 18px 6px;
      border-top: 1px solid var(--border-soft);
      display: flex; justify-content: space-between;
      flex-shrink: 0;
    }
    .rp-object-count { color: var(--ink-faint); }

    /* Classification row */
    .rp-classification {
      display: flex; padding: 0 18px 12px; gap: 2px;
      flex-shrink: 0;
    }
    .rp-class-item {
      flex: 1; display: flex; flex-direction: column;
      align-items: center; gap: 3px; padding: 8px 2px;
      border-bottom: 1px solid var(--border);
    }
    .rp-class-item.crit { border-color: var(--crit); }
    .rp-class-item.high { border-color: var(--high); }
    .rp-class-item.mod  { border-color: var(--mod);  }
    .rp-class-item.low  { border-color: var(--low);  }
    .rp-class-item.safe { border-color: var(--safe); }

    .rp-class-count {
      font-family: 'DM Serif Display', serif;
      font-size: 1.55rem; line-height: 1; color: var(--ink);
    }
    .rp-class-name { font-size: 0.5rem; letter-spacing: 1px; color: var(--ink-dim); }
    .rp-class-pct  { font-size: 0.56rem; color: var(--ink-faint); }

    .rp-class-item.crit .rp-class-count { color: var(--crit); }
    .rp-class-item.high .rp-class-count { color: var(--high); }
    .rp-class-item.mod  .rp-class-count { color: var(--mod);  }
    .rp-class-item.low  .rp-class-count { color: var(--low);  }
    .rp-class-item.safe .rp-class-count { color: var(--safe); }

    /* Table */
    .rp-table-header {
      display: flex; padding: 5px 18px;
      font-size: 0.53rem; letter-spacing: 2px;
      color: var(--ink-faint);
      border-bottom: 1px solid var(--border-soft);
      flex-shrink: 0;
    }
    .rp-table-body {
      overflow-y: auto; flex: 1; min-height: 0;
      scrollbar-width: thin;
      scrollbar-color: var(--border) transparent;
    }
    .rp-table-body::-webkit-scrollbar { width: 2px; }
    .rp-table-body::-webkit-scrollbar-thumb { background: var(--border); }

    .col-id   { flex: 1.5; font-size: 0.69rem; color: var(--ink-mid); }
    .col-ht   { flex: 1;   font-size: 0.69rem; color: var(--ink-dim); }
    .col-dist { flex: 1;   font-size: 0.69rem; text-align: right; font-weight: 500; }

    .rp-row {
      display: flex; align-items: center;
      padding: 6px 18px;
      cursor: pointer;
      border-bottom: 1px solid rgba(255,255,255,0.012);
      transition: background 0.1s;
      border-left: 2px solid transparent;
    }
    .rp-row:hover { background: rgba(255,255,255,0.025); }
    .rp-row:hover .col-id { color: var(--ink); }

    .rp-row.row-crit { border-left-color: var(--crit); }
    .rp-row.row-high { border-left-color: var(--high); }
    .rp-row.row-mod  { border-left-color: var(--mod);  }
    .rp-row.row-low  { border-left-color: var(--low);  }

    .dist-crit { color: var(--crit); }
    .dist-high { color: var(--high); }
    .dist-mod  { color: var(--mod);  }
    .dist-low  { color: var(--low);  }
    .dist-safe { color: var(--safe); }

    /* Export */
    .rp-export {
      margin: 10px 18px 6px;
      width: calc(100% - 36px);
      padding: 9px;
      background: white;
      border: 1px solid var(--border);
      color: var(--ink-mid);
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.64rem; letter-spacing: 2px;
      cursor: pointer; border-radius: 2px;
      transition: color 0.15s, border-color 0.15s;
      flex-shrink: 0;
    }
    .rp-export:hover { color: var(--ink); border-color: var(--ink-mid); }

    /* Footer */
    .rp-footer {
      display: flex; justify-content: space-between;
      padding: 8px 18px 12px;
      font-size: 0.58rem; color: var(--ink-faint);
      border-top: 1px solid var(--border-soft);
      letter-spacing: 1px; flex-shrink: 0;
    }
  `]
})
export class MapComponent implements AfterViewInit, OnDestroy {
  @ViewChild('deckCanvas') deckCanvas!: ElementRef<HTMLCanvasElement>;

  private deckInstance: any;
  private websocket: WebSocket | null = null;
  private currentJobId: string = '';
  private reconnectInterval: any = null;
  private isConnected: boolean = false;
  private jobDone: boolean = false;
  private rawGeoJson: any = null;

  isLoading: boolean = false;
  statusMessage = 'Awaiting job ID...';
  riskStats: RiskStats | null = null;
  panelOpen: boolean = true;

  private dotAnimationInterval: any = null;
  private dotCount: number = 0;
  private currentBaseMessage: string = '';

  constructor(private apiService: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnDestroy() {
    this.disconnectWebSocket();
    this.stopDotAnimation();
    if (this.reconnectInterval) clearInterval(this.reconnectInterval);
  }

  // RISK STATS

  private computeRiskStats(payload: any): void {
    const features = payload?.trees?.features ?? [];

    const trees: TreeFeature[] = features.map((f: any) => ({
      tree_id: f.properties.Tree_ID ?? '—',
      height: f.properties.Max_Height_m ?? 0,
      distance: f.properties.Distance_to_Line_m ?? 999,
      risk: f.properties.Risk_Level ?? 'SAFE',
    })).sort((a: TreeFeature, b: TreeFeature) => a.distance - b.distance);

    const count = (level: string) => trees.filter((t: TreeFeature) => t.risk === level).length;

    const critical = count('CRITICAL');
    const high = count('HIGH');
    const moderate = count('MODERATE');
    const low = count('LOW');
    const safe = count('SAFE');
    const total = trees.length;

    const score = total === 0 ? 0 : Math.min(100, Math.round(
      (critical * 20 + high * 10 + moderate * 5 + low * 2) / total * 5
    ));

    const label = score >= 75 ? 'CRITICAL'
                : score >= 55 ? 'HIGH'
                : score >= 40 ? 'ELEVATED'
                : score >= 25 ? 'MODERATE'
                : score >= 10 ? 'LOW'
                : 'SAFE';

    const totalPoints = features.reduce(
      (acc: number, f: any) => acc + (f.properties.Point_Count ?? 0), 0
    );

    this.riskStats = {
      score, label, total, critical, high, moderate, low, safe,
      trees, totalPoints,
      totalAreaHa: this.estimateAreaHa(payload?.trees)
    };
    this.panelOpen = true;
  }

  private estimateAreaHa(geojson: any): number {
    if (!geojson?.features?.length) return 0;
    let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
    for (const f of geojson.features) {
      const flat = (f.geometry?.coordinates ?? []).flat(3);
      for (let i = 0; i < flat.length - 1; i += 2) {
        minLng = Math.min(minLng, flat[i]);   maxLng = Math.max(maxLng, flat[i]);
        minLat = Math.min(minLat, flat[i+1]); maxLat = Math.max(maxLat, flat[i+1]);
      }
    }
    const dLng = (maxLng - minLng) * 111320 * Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);
    const dLat = (maxLat - minLat) * 110540;
    return parseFloat(((dLng * dLat) / 10000).toFixed(1));
  }

  // HELPERS

  pct(n: number, total: number): string {
    return total === 0 ? '0' : Math.round((n / total) * 100).toString();
  }

  getRiskClass(label: string): string {
    const map: Record<string, string> = {
      CRITICAL: 'risk-critical', HIGH: 'risk-high', ELEVATED: 'risk-elevated',
      MODERATE: 'risk-moderate', LOW: 'risk-low', SAFE: 'risk-safe'
    };
    return map[label] ?? 'risk-safe';
  }

  getRowClass(risk: string): string {
    const map: Record<string, string> = {
      CRITICAL: 'row-crit', HIGH: 'row-high', MODERATE: 'row-mod', LOW: 'row-low', SAFE: 'row-safe'
    };
    return map[risk] ?? '';
  }

  getDistClass(distance: number): string {
    if (distance < 5)  return 'dist-crit';
    if (distance < 10) return 'dist-high';
    if (distance < 20) return 'dist-mod';
    if (distance < 35) return 'dist-low';
    return 'dist-safe';
  }

  flyToTree(tree: TreeFeature): void {
    const feature = (this.rawGeoJson?.trees?.features ?? [])
      .find((f: any) => f.properties.Tree_ID === tree.tree_id);
    if (!feature) return;
    const coords = feature.geometry?.coordinates;
    if (!coords) return;
    const ring = Array.isArray(coords[0][0]) ? coords[0] : coords;
    const lng = ring.reduce((s: number, c: any) => s + c[0], 0) / ring.length;
    const lat = ring.reduce((s: number, c: any) => s + c[1], 0) / ring.length;
    this.deckInstance.setProps({
      initialViewState: {
        longitude: lng, latitude: lat,
        zoom: 19, pitch: 60, bearing: 0,
        transitionDuration: 1500,
        transitionInterpolator: new FlyToInterpolator()
      }
    });
  }

  exportGeoJson(): void {
    if (!this.rawGeoJson) return;
    const blob = new Blob([JSON.stringify(this.rawGeoJson.trees, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `risk_${this.currentJobId.slice(0, 8)}.geojson`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // WEBSOCKET

  private connectWebSocket(jobId: string) {
    this.disconnectWebSocket();
    this.currentJobId = jobId;
    this.isLoading = true;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.websocket = new WebSocket(`${proto}//localhost:8000/ws/${jobId}`);

    this.websocket.onopen = () => {
      this.isConnected = true;
      this.statusMessage = 'Connected — waiting for updates...';
      this.cdr.detectChanges();
    };
    this.websocket.onmessage = (event) => {
      try { this.handleStatusUpdate(JSON.parse(event.data)); this.cdr.detectChanges(); }
      catch (e) { console.error('WS parse error:', e); }
    };
    this.websocket.onerror = () => {
      this.isLoading = false;
      this.statusMessage = 'Connection error — retrying...';
      this.cdr.detectChanges();
    };
    this.websocket.onclose = () => {
      this.isConnected = false; this.isLoading = false;
      if (this.currentJobId && !this.jobDone) {
        this.statusMessage = 'Connection lost — reconnecting...';
        this.cdr.detectChanges();
        this.startReconnect();
      }
    };
  }

  private startReconnect() {
    if (this.reconnectInterval) return;
    this.reconnectInterval = setInterval(() => {
      if (this.currentJobId && !this.isConnected)
        this.connectWebSocket(this.currentJobId);
    }, 3000);
  }

  private disconnectWebSocket() {
    if (this.reconnectInterval) { clearInterval(this.reconnectInterval); this.reconnectInterval = null; }
    if (this.websocket) { this.websocket.close(); this.websocket = null; }
    this.isConnected = false;
  }

  private startDotAnimation() {
    this.stopDotAnimation();
    this.dotCount = 0;
    this.dotAnimationInterval = setInterval(() => {
      this.dotCount = (this.dotCount + 1) % 4;
      this.statusMessage = `${this.currentBaseMessage}${'.'.repeat(this.dotCount)}`;
      this.cdr.detectChanges();
    }, 400);
  }

  private stopDotAnimation() {
    if (this.dotAnimationInterval) { clearInterval(this.dotAnimationInterval); this.dotAnimationInterval = null; }
  }

  private handleStatusUpdate(status: JobStatus) {
    this.stopDotAnimation();
    switch (status.status) {
      case 'queued':
        this.isLoading = true;
        this.statusMessage = `Queued — ${status.message || 'waiting for worker'}`;
        break;
      case 'processing':
        this.isLoading = true;
        this.currentBaseMessage = status.message || 'Processing';
        this.statusMessage = this.currentBaseMessage;
        this.startDotAnimation();
        break;
      case 'completed':
        this.jobDone = true; this.isLoading = false;
        this.statusMessage = '✓ Complete — loading map...';
        this.disconnectWebSocket();
        this.fetchJobResult(status.job_id);
        break;
      case 'failed':
        this.jobDone = true; this.isLoading = false;
        this.statusMessage = `✗ ${status.message || 'Job failed'}`;
        this.disconnectWebSocket();
        break;
    }
    this.cdr.detectChanges();
  }

  //  LIFECYCLE

  ngAfterViewInit() {
    const ambientLight     = new AmbientLight({ color: [255, 255, 255], intensity: 0.4 });
    const directionalLight = new DirectionalLight({ color: [255, 255, 255], intensity: 1.5, direction: [-1, -2, -3] });

    this.deckInstance = new Deck({
      canvas: this.deckCanvas.nativeElement,
      initialViewState: { longitude: 5.714, latitude: 7.613, zoom: 4, pitch: 0, bearing: 0 },
      controller: true,
      effects: [new LightingEffect({ ambientLight, directionalLight })],
      layers: [],
      getTooltip: ({ object }) => {
        if (!object?.properties?.Max_Height_m) return null;
        const r = object.properties.Risk_Level;
        const col = r === 'CRITICAL' ? '#c44236'
                  : r === 'HIGH'     ? '#c07a32'
                  : r === 'MODERATE' ? '#a49228'
                  : r === 'LOW'      ? '#688e44' : '#3a785a';
        return {
          html: `<div style="font-family:'IBM Plex Mono',monospace;padding:10px 13px;font-size:0.71rem;line-height:1.9">
            <div style="color:${col};letter-spacing:2px;margin-bottom:2px">${object.properties.Tree_ID}</div>
            <div style="color:#584e3c">HT &nbsp;&nbsp;<span style="color:#e2d6be">${object.properties.Max_Height_m.toFixed(1)} m</span></div>
            <div style="color:#584e3c">DIST <span style="color:${col}">${object.properties.Distance_to_Line_m.toFixed(1)} m</span></div>
            <div style="color:${col};letter-spacing:1px;margin-top:3px;font-size:0.66rem">${r}</div>
          </div>`,
          style: {
            backgroundColor: 'rgba(12,10,8,0.97)',
            border: '1px solid #252018',
            borderRadius: '2px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.75)'
          }
        };
      }
    });
  }

  loadData(jobId: string) {
    if (!jobId) return;
    this.jobDone = false;
    this.riskStats = null;
    this.connectWebSocket(jobId);
    this.statusMessage = 'Connecting...';
    this.isLoading = true;
    this.cdr.detectChanges();
  }

  private fetchJobResult(jobId: string) {
    this.apiService.getJobResult(jobId).subscribe({
      next: (response) => {
        let mapData = response.result;
        if (typeof mapData === 'string') mapData = JSON.parse(mapData);
        if (typeof mapData === 'string') mapData = JSON.parse(mapData);
        if (mapData?.data?.type === 'FeatureCollection') mapData = mapData.data;
        else if (mapData?.features && !mapData.type)
          mapData = { type: 'FeatureCollection', features: mapData.features };

        this.rawGeoJson = response.result;
        this.computeRiskStats(response.result);
        this.statusMessage = `✓ ${this.riskStats?.total} trees rendered`;
        this.isLoading = false;
        this.cdr.detectChanges();
        this.render3DLayers(mapData);
      },
      error: (err) => {
        this.statusMessage = `Error: ${err.message || 'Unknown'}`;
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  render3DLayers(payload: any) {
    const treesGeoJson     = payload.trees;
    const powerlineGeoJson = payload.powerline;
    // TO BE REMOVED LATER ...
    const powerlineFixed = {
      ...powerlineGeoJson,
      features: (powerlineGeoJson.features ?? []).map((f: any) => ({
      ...f,
      geometry: {
      ...f.geometry,
      coordinates: f.geometry.coordinates.map((c: number[]) => [c[0], c[1], 35]) // hardcoded to 35m until I figure out the issue :/
      }
      }))
    };
    // ...

    const baseMap = new TileLayer({
      id: 'basemap',
      data: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      minZoom: 0, maxZoom: 19, tileSize: 256,
      renderSubLayers: (props: any) => {
        const { west, south, east, north } = props.tile.bbox as any;
        return new BitmapLayer(props, { data: undefined, image: props.data, bounds: [west, south, east, north] });
      }
    });

    const treeLayer = new GeoJsonLayer({
      id: 'trees',
      data: treesGeoJson,
      pickable: true, extruded: true, wireframe: false,
      getElevation: (f: any) => f.properties.Max_Height_m ?? 10,
      // getElevation: (f: any) => f.properties.top_z_m ?? f.properties.Max_Height_m,
      getFillColor: (f: any) => {
        const r = f.properties.Risk_Level;
        return r === 'CRITICAL' ? [196,  66,  54, 255]
             : r === 'HIGH'     ? [192, 122,  50, 255]
             : r === 'MODERATE' ? [164, 146,  40, 255]
             : r === 'LOW'      ? [104, 142,  68, 255]
             :                    [ 58, 120,  90, 255];
      },
      material: { ambient: 0.3, diffuse: 0.9, shininess: 28, specularColor: [50, 44, 36] }
    });

    const clearanceLayer = new GeoJsonLayer({
      id: 'clearance',
      data: powerlineFixed,
      stroked: true,
      getLineColor: [196, 66, 54, 22],
      getLineWidth: 25, lineWidthUnits: 'meters',
      getPolygonOffset: ({ layerIndex }: any) => [0, -layerIndex * 100],
    });

    const powerlineLayer = new GeoJsonLayer({
      id: 'powerline',
      data: powerlineFixed,
      stroked: true,
      getLineColor: [192, 122, 50, 255],
      getLineWidth: 6, lineWidthMinPixels: 4,
      getPolygonOffset: ({ layerIndex }: any) => [0, -layerIndex * 100],
    });

    this.deckInstance.setProps({
      layers: [baseMap, clearanceLayer, powerlineLayer, treeLayer],
      initialViewState: {
        longitude: 5.714, latitude: 7.613,
        zoom: 16.5, pitch: 65, bearing: 120,
        transitionDuration: 4000,
        transitionInterpolator: new FlyToInterpolator()
      }
    });
  }
}
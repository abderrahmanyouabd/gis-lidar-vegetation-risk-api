import { Component } from '@angular/core';
import { MapComponent } from './map/map';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [MapComponent],
  template: `<app-map></app-map>`,
  styles: [`
    :host { display: block; width: 100vw; height: 100vh; margin: 0; padding: 0; }
  `]
})
export class App {}